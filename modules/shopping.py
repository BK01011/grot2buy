"""Einkaufslisten-Modul: Grocy + Buy Me a Pie + Lokaler Speicher + Synchronisation."""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from .shopping_sync import shopping_sync
from .buymeapie import BuyMeAPieClient, create_client

DATA_DIR = Path(__file__).parent.parent / "data"
SHOPPING_FILE = DATA_DIR / "shopping.json"


class ShoppingItem:
    def __init__(self, name: str, quantity: int = 1, category: str = "", purchased: bool = False):
        self.name = name
        self.quantity = quantity
        self.category = category
        self.purchased = purchased
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "quantity": self.quantity,
            "category": self.category,
            "purchased": self.purchased,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ShoppingItem":
        item = cls(
            name=data["name"],
            quantity=data.get("quantity", 1),
            category=data.get("category", ""),
            purchased=data.get("purchased", False),
        )
        item.created_at = data.get("created_at", datetime.now().isoformat())
        return item


class LocalShoppingList:
    """Lokale Einkaufsliste."""

    def __init__(self):
        self._items: list[ShoppingItem] = []
        self._list_name: str = "Einkaufsliste"
        self.load()

    def load(self):
        if SHOPPING_FILE.exists():
            try:
                raw = SHOPPING_FILE.read_text()
                if raw.startswith("gAAAAA"):
                    from .config import decrypt
                    raw = decrypt(raw)
                data = json.loads(raw)
                self._list_name = data.get("name", "Einkaufsliste")
                self._items = [ShoppingItem.from_dict(i) for i in data.get("items", [])]
            except Exception:
                self._items = []

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            from .config import encrypt
            SHOPPING_FILE.write_text(encrypt(json.dumps({
                "name": self._list_name,
                "items": [i.to_dict() for i in self._items],
            }, ensure_ascii=False)))
        except Exception:
            pass

    @property
    def open_items(self) -> list[ShoppingItem]:
        return [i for i in self._items if not i.purchased]

    @property
    def purchased_items(self) -> list[ShoppingItem]:
        return [i for i in self._items if i.purchased]

    def add_item(self, name: str, quantity: int = 1, category: str = "") -> ShoppingItem:
        for item in self._items:
            if item.name.lower() == name.lower() and not item.purchased:
                item.quantity += quantity
                self.save()
                return item
        item = ShoppingItem(name, quantity, category)
        self._items.append(item)
        self.save()
        return item

    def remove_item(self, name: str) -> bool:
        for i, item in enumerate(self._items):
            if item.name.lower() == name.lower():
                self._items.pop(i)
                self.save()
                return True
        return False

    def mark_purchased(self, name: str) -> bool:
        for item in self._items:
            if item.name.lower() == name.lower():
                item.purchased = True
                self.save()
                return True
        return False

    def clear_purchased(self):
        self._items = [i for i in self._items if not i.purchased]
        self.save()

    def to_text(self) -> str:
        if not self.open_items:
            return "🛒 Einkaufsliste ist leer."
        lines = [f"🛒 **{self._list_name}** ({len(self.open_items)} Artikel):\n"]
        for item in self.open_items:
            qty = f" x{item.quantity}" if item.quantity > 1 else ""
            cat = f" [{item.category}]" if item.category else ""
            lines.append(f"  • {item.name}{qty}{cat}")
        if self.purchased_items:
            lines.append(f"\n✅ Erledigt ({len(self.purchased_items)}):")
            for item in self.purchased_items:
                lines.append(f"  • ~~{item.name}~~")
        return "\n".join(lines)


class GrocyClient:
    """Grocy API Client — Einkaufsliste + Bestand."""

    def __init__(self, base_url: str, api_key: str):
        import httpx
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._headers = {"GROCY-API-KEY": api_key}
        self._client = httpx.Client(timeout=10)

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

    def get_shopping_list(self, list_id: int = 1, include_done: bool = False) -> list:
        try:
            items = self._get("objects/shopping_list")
            if not isinstance(items, list):
                return []
            # Nach Liste filtern, optional done-Filter
            filtered = [i for i in items if i.get("shopping_list_id", 1) == list_id]
            if not include_done:
                filtered = [i for i in filtered if i.get("done", 0) == 0]
            
            # Produktdaten nachladen
            products = {}
            try:
                all_products = self._get("objects/products")
                if isinstance(all_products, list):
                    products = {p["id"]: p for p in all_products}
            except Exception:
                pass
            
            # Product-Objekte anhängen
            for item in filtered:
                pid = item.get("product_id")
                if pid and pid in products:
                    item["product"] = products[pid]
            
            return filtered
        except Exception as e:
            print(f"❌ Grocy Shopping List Fehler: {e}")
            return []

    def add_to_shopping_list(self, product_name: str, amount: int = 1, list_id: int = 1) -> str:
        try:
            # First find or create the product
            products = self._get("objects/products")
            product = next((p for p in products if p.get("name", "").lower() == product_name.lower()), None)

            if not product:
                # Create product
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

            # Insert into shopping_list directly
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
        """Markiert einen Einkaufslisten-Artikel als erledigt."""
        try:
            resp = self._client.put(f"{self.base_url}/api/objects/shopping_list/{item_id}",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"done": 1})
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def revert_done(self, item_id: int) -> bool:
        """Setzt den 'erledigt'-Status eines Einkaufslisten-Artikels zurück."""
        try:
            resp = self._client.put(f"{self.base_url}/api/objects/shopping_list/{item_id}",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"done": 0})
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def get_stock(self) -> list:
        try:
            return self._get("stock") or []
        except Exception:
            return []

    def get_low_stock(self) -> list:
        stock = self.get_stock()
        return [s for s in stock if s.get("amount", 0) <= s.get("product", {}).get("min_stock_amount", 0)]

    def to_shopping_text(self, list_id: int = 1) -> str:
        items = self.get_shopping_list(list_id)
        if not items:
            return "🛒 Grocy Einkaufsliste ist leer."
        lines = [f"🛒 **Grocy Einkaufsliste** ({len(items)} Artikel):\n"]
        for item in items:
            name = item.get("product", {}).get("name", item.get("note", "?"))
            qty = item.get("amount", 1)
            lines.append(f"  • {name} x{qty}" if qty > 1 else f"  • {name}")
        return "\n".join(lines)

    def to_stock_text(self) -> str:
        stock = self.get_stock()
        if not stock:
            return "📦 Kein Bestand vorhanden."
        low = self.get_low_stock()
        lines = [f"📦 **Bestand** ({len(stock)} Produkte):\n"]
        if low:
            lines.append(f"⚠️ **Niedriger Bestand ({len(low)}):**")
            for item in low:
                name = item.get("product", {}).get("name", "?")
                amt = item.get("amount", 0)
                lines.append(f"  • {name}: {amt}")
        return "\n".join(lines)


class ShoppingManager:
    """Einheitlicher Manager: Grocy, Buy Me a Pie oder Lokal."""

    def __init__(self):
        self._local = LocalShoppingList()
        self._grocy: Optional[GrocyClient] = None
        self._bap: Optional[BuyMeAPieClient] = None

    def configure_grocy(self, base_url: str, api_key: str) -> bool:
        try:
            self._grocy = GrocyClient(base_url, api_key)
            self._grocy.get_stock()
            return True
        except Exception as e:
            print(f"Grocy Verbindung fehlgeschlagen: {e}")
            self._grocy = None
            return False

    def configure_buymeapie(self, username: str, password: str) -> bool:
        """Konfiguriert Buy Me a Pie Verbindung."""
        try:
            self._bap = create_client(username, password)
            return self._bap is not None
        except Exception as e:
            print(f"Buy Me a Pie Verbindung fehlgeschlagen: {e}")
            self._bap = None
            return False

    @property
    def backend(self) -> str:
        if self._bap:
            return "buymeapie"
        if self._grocy:
            return "grocy"
        return "local"

    def get_items_as_text(self) -> str:
        if self._bap:
            return self._bap.get_items_as_text()
        if self._grocy:
            return self._grocy.to_shopping_text()
        return self._local.to_text()

    def get_stock_text(self) -> str:
        if self._grocy:
            return self._grocy.to_stock_text()
        return "📦 Bestand nur bei Grocy verfügbar."

    def add_item(self, name: str, quantity: int = 1, category: str = "") -> str:
        if self._bap:
            lists = self._bap.get_lists()
            # Bevorzugt konfigurierte Liste finden, sonst erste Liste
            from .config import config
            target_name = config.get("bap_list_name", "Einkaufsliste").lower()
            list_id = None
            for lst in lists:
                if target_name in lst.get("name", "").lower():
                    list_id = lst.get("id")
                    break
            if not list_id and lists:
                list_id = lists[0].get("id")
            if list_id:
                if self._bap.add_item(list_id, name, quantity):
                    return f"✅ '{name}' zur Einkaufsliste hinzugefügt."
        if self._grocy:
            return self._grocy.add_to_shopping_list(name, quantity)
        self._local.add_item(name, quantity, category)
        return f"✅ '{name}' zur Einkaufsliste hinzugefügt."

    def remove_item(self, name: str) -> str:
        if self._bap:
            lists = self._bap.get_lists()
            name_lower = name.lower()
            for lst in lists:
                items = self._bap.get_list_items(lst.get("id"))
                for item in items:
                    item_name = item.get("title", item.get("name", "")).lower()
                    # Exakter Treffer ODER Teilübereinstimmung
                    if item_name == name_lower or name_lower in item_name or item_name in name_lower:
                        self._bap.delete_item(lst.get("id"), item.get("id"))
                        return f"✅ '{item.get('title', name)}' entfernt."
        if self._grocy:
            items = self._grocy.get_shopping_list()
            name_lower = name.lower()
            for item in items:
                item_name = item.get("product", {}).get("name", "").lower()
                if item_name == name_lower or name_lower in item_name or item_name in name_lower:
                    self._grocy.remove_from_shopping_list(item["id"])
                    return f"✅ '{item.get('product', {}).get('name', name)}' entfernt."
            return f"❌ '{name}' nicht gefunden."
        if self._local.remove_item(name):
            return f"✅ '{name}' entfernt."
        return f"❌ '{name}' nicht gefunden."

    def mark_purchased(self, name: str) -> str:
        if self._bap:
            lists = self._bap.get_lists()
            name_lower = name.lower()
            for lst in lists:
                items = self._bap.get_list_items(lst.get("id"))
                for item in items:
                    item_name = item.get("title", item.get("name", "")).lower()
                    if item_name == name_lower or name_lower in item_name or item_name in name_lower:
                        self._bap.mark_purchased(lst.get("id"), item.get("id"))
                        return f"✅ '{item.get('title', name)}' als gekauft markiert."
        if self._grocy:
            items = self._grocy.get_shopping_list()
            name_lower = name.lower()
            for item in items:
                item_name = item.get("product", {}).get("name", "").lower()
                if item_name == name_lower or name_lower in item_name or item_name in name_lower:
                    try:
                        self._grocy._post(f"shopping-list/remove-product/{item['id']}", {"amount": item.get("amount", 1)})
                        return f"✅ '{name}' aus Liste entfernt."
                    except Exception:
                        return f"✅ '{name}' markiert."
            return f"❌ '{name}' nicht gefunden."
        if self._local.mark_purchased(name):
            return f"✅ '{name}' als gekauft markiert."
        return f"❌ '{name}' nicht gefunden."

    def sync_lists(self) -> str:
        """Synchronisiert alle Listen: Grocy ↔ BAP ↔ Lokal."""
        results = []
        
        if self._bap:
            results.append("📱 Buy Me a Pie: Verbunden")
        if self._grocy:
            results.append("📦 Grocy: Verbunden")
        
        if self._grocy and self._bap:
            # Vollständige bidirektionale Synchronisation
            sync_result = shopping_sync.sync_full(self._grocy, self._bap)
            results.append(sync_result)
        elif self._grocy:
            results.append("⚠️ Buy Me a Pie nicht konfiguriert — nur Grocy verfügbar")
        elif self._bap:
            # Nur BAP anzeigen + synced
            push_result = shopping_sync.push_to_buymeapie(self._bap)
            results.append(push_result)
        else:
            results.append("⚠️ Keine Verbindung konfiguriert — nur lokale Liste")
        
        return "\n".join(results)

    def get_synced_text(self) -> str:
        """Zeigt die synchronisierte Liste an."""
        return shopping_sync.get_merged_text()

    def export_for_buymeapie(self) -> str:
        """Exportiert die Liste für Buy Me a Pie."""
        return shopping_sync.export_for_buymeapie()

    def add_to_synced(self, name: str, quantity: int = 1, category: str = "") -> str:
        """Fügt einen Artikel zur synchronisierten Liste hinzu."""
        return shopping_sync.add_item(name, quantity, category)

    def remove_from_synced(self, name: str) -> str:
        """Entfernt einen Artikel aus der synchronisierten Liste."""
        return shopping_sync.remove_item(name)

    def clear_synced(self) -> str:
        """Leert die synchronisierte Liste."""
        return shopping_sync.clear_purchased()

    def update_quantity(self, name: str, quantity: int) -> str:
        """Aktualisiert die Menge eines Artikels."""
        return shopping_sync.update_quantity(name, quantity)


shopping_manager = ShoppingManager()
