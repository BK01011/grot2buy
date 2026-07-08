"""Buy Me a Pie API Client — korrigierte Version mit is_purchased + deleted."""
import requests
import logging
from typing import Optional

logger = logging.getLogger("shopping")


class BuyMeAPieClient:
    """Client für Buy Me a Pie Einkaufslisten-App."""

    BASE_URL = "https://app.buymeapie.com"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "Origin": "https://app.buymeapie.com",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
        })
        self.session.auth = (username, password)
        self._logged_in = False

    def login(self) -> bool:
        """Login bei Buy Me a Pie."""
        try:
            resp = self.session.get(f"{self.BASE_URL}/bauth")
            if resp.status_code == 200:
                self._logged_in = True
                return True
            return False
        except Exception as e:
            print(f"❌ BAP Login fehlgeschlagen: {e}")
            return False

    def _ensure_login(self):
        if not self._logged_in:
            self.login()

    def get_lists(self) -> list:
        """Holt alle Einkaufslisten."""
        self._ensure_login()
        try:
            resp = self.session.get(f"{self.BASE_URL}/lists")
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            print(f"❌ BAP Listen-Fehler: {e}")
            return []

    def get_list_items(self, list_id: str) -> list:
        """Holt alle Artikel einer Liste."""
        self._ensure_login()
        try:
            resp = self.session.get(f"{self.BASE_URL}/lists/{list_id}/items")
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            print(f"❌ BAP Artikel-Fehler: {e}")
            return []

    def get_active_items(self, list_id: str) -> list:
        """Holt nur aktive Artikel (nicht gekauft, nicht gelöscht)."""
        items = self.get_list_items(list_id)
        return [i for i in items if not i.get("is_purchased") and not i.get("deleted")]

    def get_default_list_id(self) -> Optional[str]:
        """Findet die Standard-Einkaufsliste (namens 'Einkaufsliste')."""
        lists = self.get_lists()
        for lst in lists:
            if "einkauf" in lst.get("name", "").lower():
                return lst.get("id")
        # Falls keine gefunden, nimm die erste
        return lists[0].get("id") if lists else None

    def add_item(self, list_id: str, name: str, quantity: int = 1) -> str:
        """Fügt einen Artikel zur Liste hinzu. Gibt 'added', 'exists' oder 'error' zurück."""
        self._ensure_login()
        try:
            # Prüfe ob Artikel bereits existiert
            existing = self.get_active_items(list_id)
            for item in existing:
                if item.get("title", "").lower() == name.lower():
                    return "exists"

            data = {
                "title": name,
                "amount": f"{quantity}×" if quantity > 1 else "",
            }
            resp = self.session.post(f"{self.BASE_URL}/lists/{list_id}/items", json=data)
            return "added" if resp.status_code in (200, 201) else "error"
        except Exception as e:
            print(f"❌ BAP Hinzufügen fehlgeschlagen: {e}")
            return "error"

    def add_items_bulk(self, items: list[dict], list_id: Optional[str] = None) -> tuple[int, int]:
        """Fügt mehrere Artikel hinzu. Gibt (hinzugefügt, übersprungen) zurück."""
        if not list_id:
            list_id = self.get_default_list_id()
        if not list_id:
            return 0, 0

        added = 0
        skipped = 0
        for item in items:
            name = item.get("name", "")
            qty = item.get("quantity", 1)
            if not name:
                skipped += 1
                continue
            result = self.add_item(list_id, name, qty)
            if result == "added":
                added += 1
            else:
                skipped += 1
        return added, skipped

    def delete_item(self, list_id: str, item_id: str) -> bool:
        """Löscht einen Artikel."""
        self._ensure_login()
        try:
            resp = self.session.delete(f"{self.BASE_URL}/lists/{list_id}/items/{item_id}")
            return resp.status_code in (200, 204)
        except Exception as e:
            print(f"❌ BAP Löschen fehlgeschlagen: {e}")
            return False

    def mark_purchased(self, list_id: str, item_id: str) -> bool:
        """Markiert einen Artikel als gekauft."""
        self._ensure_login()
        try:
            url = f"{self.BASE_URL}/lists/{list_id}/items/{item_id}"
            resp = self.session.put(url, json={"is_purchased": True})
            return resp.status_code in (200, 204)
        except Exception as e:
            print(f"❌ BAP Kauf-Markierung fehlgeschlagen: {e}")
            return False

    def close(self):
        """Schließt die Session und gibt Verbindungen frei."""
        try:
            self.session.close()
        except Exception:
            pass

    def get_items_as_text(self, list_id: Optional[str] = None) -> str:
        """Holt die Einkaufsliste als formatierten Text — nur offene Artikel."""
        lists = self.get_lists()
        if not lists:
            return "🛒 Keine Buy Me a Pie Listen gefunden."

        lines = []

        for lst in lists:
            if list_id and lst.get("id") != list_id:
                continue

            list_name = lst.get("name", "Liste")
            active = self.get_active_items(lst.get("id"))
            purchased_count = lst.get("items_purchased", 0)

            if active:
                lines.append(f"📋 **{list_name}** ({len(active)} offen):")
                for item in active[:20]:
                    name = item.get("title", "")
                    amount = item.get("amount", "")
                    qty_str = f" ({amount})" if amount else ""
                    lines.append(f"  • {name}{qty_str}")
                if len(active) > 20:
                    lines.append(f"  ... und {len(active) - 20} weitere")
                lines.append("")

        if not lines:
            return "🛒 Alle Artikel erledigt! 🎉"

        return "\n".join(lines).strip()


def create_client(username: str, password: str) -> Optional[BuyMeAPieClient]:
    """Erstellt einen Buy Me a Pie Client."""
    client = BuyMeAPieClient(username, password)
    if client.login():
        return client
    return None
