"""Einkaufslisten-Modul: Grocy + Buy Me a Pie + Synchronisation."""
import httpx
import logging
from typing import Optional
from .buymeapie import BuyMeAPieClient, create_client

logger = logging.getLogger("shopping")


class GrocyClient:
    """Grocy API Client — Einkaufsliste + Bestand."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._headers = {"GROCY-API-KEY": api_key}
        self._client = httpx.Client(timeout=10)

    def close(self):
        try:
            self._client.close()
        except Exception as e:
            logger.debug(f"GrocyClient close: {e}")

    def _get(self, endpoint: str):
        resp = self._client.get(f"{self.base_url}/api/{endpoint}", headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, data: dict):
        resp = self._client.post(f"{self.base_url}/api/{endpoint}", headers=self._headers, json=data)
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def _delete(self, endpoint: str) -> bool:
        resp = self._client.delete(f"{self.base_url}/api/{endpoint}", headers=self._headers)
        return resp.status_code in (200, 204)

    def _put(self, endpoint: str, data: dict):
        resp = self._client.put(f"{self.base_url}/api/{endpoint}",
                                headers={**self._headers, "Content-Type": "application/json"}, json=data)
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def _get_main_list_id(self) -> int:
        try:
            lists = self._get("objects/shopping_lists")
            if isinstance(lists, list) and lists:
                return int(lists[0]["id"])
        except Exception:
            pass
        return 1

    def get_shopping_list(self, list_id: Optional[int] = None, include_done: bool = False) -> list:
        try:
            if list_id is None:
                list_id = self._get_main_list_id()
            items = self._get("objects/shopping_list")
            if not isinstance(items, list):
                return []
            filtered = [i for i in items if i.get("shopping_list_id", 1) == list_id]
            if not include_done:
                filtered = [i for i in filtered if i.get("done", 0) == 0]

            products = {}
            try:
                all_products = self._get("objects/products")
                if isinstance(all_products, list):
                    products = {p["id"]: p for p in all_products}
            except Exception:
                pass

            for item in filtered:
                pid = item.get("product_id")
                if pid and pid in products:
                    item["product"] = products[pid]

            return filtered
        except Exception as e:
            logger.error(f"Grocy Shopping List Fehler: {e}")
            return []

    def get_stock(self) -> dict[str, float]:
        """Returns dict of {product_name_lower: stock_amount}."""
        try:
            stock_entries = self._get("stock")
            if not isinstance(stock_entries, list):
                return {}
            products = self._get("objects/products")
            prod_map = {}
            if isinstance(products, list):
                prod_map = {p["id"]: p.get("name", "") for p in products}
            result = {}
            for entry in stock_entries:
                pid = entry.get("product_id")
                amount = entry.get("amount", 0)
                name = prod_map.get(pid, "")
                if name:
                    result[name.lower().strip()] = float(amount)
            return result
        except Exception as e:
            logger.error(f"Grocy Stock Fehler: {e}")
            return {}

    def add_to_shopping_list(self, product_name: str, amount: int = 1, list_id: Optional[int] = None) -> str:
        try:
            if list_id is None:
                list_id = self._get_main_list_id()
            products = self._get("objects/products")
            product = next((p for p in products if p.get("name", "").lower() == product_name.lower()), None)

            if not product:
                locations = self._get("objects/locations")
                loc_id = locations[0]["id"] if locations else 1
                qu = self._get("objects/quantity_units")
                qu_id = qu[0]["id"] if qu else 1
                resp = self._client.post(f"{self.base_url}/api/objects/products",
                    headers={**self._headers, "Content-Type": "application/json"},
                    json={"name": product_name, "qu_id_purchase": qu_id, "qu_id_stock": qu_id, "location_id": loc_id})
                resp.raise_for_status()
                product_id = resp.json()["created_object_id"]
            else:
                product_id = product["id"]

            resp = self._client.post(f"{self.base_url}/api/objects/shopping_list",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"product_id": int(product_id), "amount": amount, "shopping_list_id": list_id, "done": 0, "qu_id": 1})
            resp.raise_for_status()
            return f"✅ '{product_name}' zu Grocy hinzugefügt."
        except Exception as e:
            return f"❌ Grocy: {e}"

    def remove_from_shopping_list(self, item_id: int) -> bool:
        try:
            self._delete(f"objects/shopping_list/{item_id}")
            return True
        except Exception:
            return False

    def mark_done(self, item_id: int) -> bool:
        try:
            resp = self._client.put(f"{self.base_url}/api/objects/shopping_list/{item_id}",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"done": 1})
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def revert_done(self, item_id: int) -> bool:
        try:
            resp = self._client.put(f"{self.base_url}/api/objects/shopping_list/{item_id}",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"done": 0})
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def update_shopping_list_item(self, item_id: int, amount: int) -> bool:
        try:
            self._put(f"objects/shopping_list/{item_id}", {"amount": amount})
            return True
        except Exception as e:
            logger.error(f"Grocy update item Fehler: {e}")
            return False


class ShoppingManager:
    """Einheitlicher Manager: Grocy, Buy Me a Pie oder Lokal."""

    def __init__(self):
        self._grocy: Optional[GrocyClient] = None
        self._bap: Optional[BuyMeAPieClient] = None

    def configure_grocy(self, base_url: str, api_key: str) -> bool:
        try:
            if self._grocy:
                self._grocy.close()
            client = GrocyClient(base_url, api_key)
            client.get_shopping_list()
            self._grocy = client
            return True
        except Exception as e:
            logger.error(f"Grocy Verbindung fehlgeschlagen: {e}")
            self._grocy = None
            return False

    def configure_buymeapie(self, username: str, password: str) -> bool:
        try:
            self._bap = create_client(username, password)
            return self._bap is not None
        except Exception as e:
            logger.error(f"Buy Me a Pie Verbindung fehlgeschlagen: {e}")
            self._bap = None
            return False

    @property
    def backend(self) -> str:
        if self._bap:
            return "buymeapie"
        if self._grocy:
            return "grocy"
        return "local"


shopping_manager = ShoppingManager()
