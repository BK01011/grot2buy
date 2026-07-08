"""Shopping Sync v5 — Zentrale Liste als Quelle der Wahrheit."""
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger("shopping")
DATA_DIR = Path(__file__).parent.parent / "data"
SYNC_FILE = DATA_DIR / "shopping_sync.json"


class ShoppingSync:
    def __init__(self):
        self._synced_items: list[dict] = []
        self._removed: list[str] = []
        self._removed_set: set[str] = set()
        self.load()

    def load(self):
        if SYNC_FILE.exists():
            try:
                raw = SYNC_FILE.read_text()
                if raw.startswith("gAAAAA"):
                    from .config import decrypt
                    raw = decrypt(raw)
                data = json.loads(raw)
                if isinstance(data, list):
                    self._synced_items = data
                    self._removed = []
                else:
                    self._synced_items = data.get("items", [])
                    self._removed = data.get("removed", [])
                self._removed_set = {self._norm(r) for r in self._removed}
            except Exception:
                self._synced_items = []
                self._removed = []
                self._removed_set = set()

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            from .config import encrypt
            self._removed_set = {self._norm(r) for r in self._removed}
            payload = {"items": self._synced_items, "removed": self._removed}
            SYNC_FILE.write_text(encrypt(json.dumps(payload, ensure_ascii=False)))
        except Exception:
            pass

    def _norm(self, name: str) -> str:
        return name.lower().strip()

    def _find(self, name: str) -> Optional[dict]:
        nn = self._norm(name)
        for item in self._synced_items:
            if self._norm(item.get("name", "")) == nn:
                return item
        return None

    def _is_removed(self, name: str) -> bool:
        return self._norm(name) in self._removed_set

    # ─── Sync ──────────────────────────────────────────────────

    def sync_full(self, grocy_client, bap_client, is_initial: bool = False) -> str:
        log = []
        log.append("=== SYNC START ===")

        # ── 1. BAP lesen ─────────────────────────────────────
        bap_active = {}     # nn → {title, list_id, item_id}
        bap_purchased = {}  # nn → {title, list_id, item_id} (letzter)
        bap_purchased_all = {}  # nn → [{title, list_id, item_id}, ...] (alle)
        target_list_id = None

        if bap_client:
            from .config import config
            target_name = config.get("bap_list_name", "Einkaufsliste").lower()
            try:
                for lst in bap_client.get_lists():
                    lid = lst.get("id")
                    lname = lst.get("name", "").lower()
                    if target_name in lname:
                        target_list_id = lid
                    for item in bap_client.get_list_items(lid):
                        if item.get("deleted"):
                            continue
                        title = item.get("title", "")
                        nn = self._norm(title)
                        if not nn:
                            continue
                        entry = {"title": title, "list_id": lid, "item_id": item.get("id")}
                        if item.get("is_purchased"):
                            bap_purchased[nn] = entry
                            bap_purchased_all.setdefault(nn, []).append(entry)
                        else:
                            bap_active[nn] = entry
                log.append(f"BAP: active={list(bap_active.keys())}, purchased={list(bap_purchased.keys())}")
            except Exception as e:
                log.append(f"BAP Fehler: {e}")

        # ── 2. Grocy lesen ────────────────────────────────────
        grocy_active = {}      # nn → {id, amount, product_name} (letzter Eintrag)
        grocy_done = {}        # nn → {id, amount, product_name}
        grocy_dup_ids = {}     # nn → [alle ids] (für Duplikat-Bereinigung)
        if grocy_client:
            try:
                for g in grocy_client.get_shopping_list(include_done=True):
                    pname = g.get("product", {}).get("name", g.get("note", ""))
                    nn = self._norm(pname)
                    if not nn:
                        continue
                    entry = {"id": g.get("id"), "amount": g.get("amount", 1), "product_name": pname}
                    if g.get("done", 0) == 0:
                        grocy_dup_ids.setdefault(nn, []).append(entry)
                        grocy_active[nn] = entry
                    else:
                        grocy_done[nn] = entry
                log.append(f"Grocy: active={list(grocy_active.keys())}, done={list(grocy_done.keys())}")
            except Exception as e:
                log.append(f"Grocy Fehler: {e}")

        # ── 3. Synced-Index aufbauen ──────────────────────────
        synced_by_nn = {}
        for item in self._synced_items:
            nn = self._norm(item.get("name", ""))
            if nn:
                synced_by_nn[nn] = item
        log.append(f"Synced: {list(synced_by_nn.keys())}")

        # ── 4. Neue Artikel aus BAP/Grocy in synced mergen ────
        fresh_items = set()  # In diesem Sync neu hinzugefügte Items

        for nn, entry in bap_active.items():
            if nn not in synced_by_nn:
                item = {"name": entry["title"], "quantity": 1, "category": "",
                       "source": "bap", "added_at": datetime.now().isoformat()}
                self._synced_items.append(item)
                synced_by_nn[nn] = item
                fresh_items.add(nn)
                log.append(f"  Neu in synced (BAP aktiv): {entry['title']}")

        for nn, entry in bap_purchased.items():
            if nn not in synced_by_nn:
                if is_initial and nn not in grocy_active and nn not in grocy_done:
                    item = {"name": entry["title"], "quantity": 1, "category": "",
                           "source": "bap", "added_at": datetime.now().isoformat()}
                    log.append(f"  Neu in synced (BAP purchased → aktiv weil initial): {entry['title']}")
                else:
                    item = {"name": entry["title"], "quantity": 1, "category": "",
                           "source": "bap", "purchased": True,
                           "purchased_at": datetime.now().isoformat()}
                    log.append(f"  Neu in synced (BAP purchased): {entry['title']}")
                self._synced_items.append(item)
                synced_by_nn[nn] = item
                fresh_items.add(nn)

        for nn, entry in grocy_active.items():
            if nn not in synced_by_nn:
                item = {"name": entry["product_name"], "quantity": entry.get("amount", 1), "category": "",
                       "source": "grocy", "added_at": datetime.now().isoformat()}
                self._synced_items.append(item)
                synced_by_nn[nn] = item
                fresh_items.add(nn)
                log.append(f"  Neu in synced (Grocy aktiv): {entry['product_name']}")

        for nn, entry in grocy_done.items():
            if nn not in synced_by_nn:
                item = {"name": entry["product_name"], "quantity": entry.get("amount", 1), "category": "",
                       "source": "grocy", "purchased": True,
                       "purchased_at": datetime.now().isoformat()}
                self._synced_items.append(item)
                synced_by_nn[nn] = item
                fresh_items.add(nn)
                log.append(f"  Neu in synced (Grocy done): {entry['product_name']}")

        # ── 5. Synced-Status aus Quellen aktualisieren ────────
        for nn, item in synced_by_nn.items():
            synced_purchased = item.get("purchased", False)
            name = item["name"]
            qty = item.get("quantity", 1)

            if nn in fresh_items:
                desired_purchased = synced_purchased
                log.append(f"  {name}: frisch hinzugefügt → {'gekauft' if desired_purchased else 'aktiv'}")
            else:
                grocy_purchased = nn in grocy_done
                grocy_active_flag = nn in grocy_active and not grocy_purchased
                grocy_has = grocy_purchased or grocy_active_flag

                bap_purchased_flag = nn in bap_purchased
                bap_active_flag = nn in bap_active and not bap_purchased_flag
                bap_has = bap_purchased_flag or bap_active_flag

                # Wer hat sich seit letztem Sync geändert? (synced = Baseline)
                grocy_says_purchased = grocy_purchased
                grocy_changed = grocy_has and (grocy_says_purchased != synced_purchased)

                bap_says_purchased = bap_purchased_flag
                bap_changed = bap_has and (bap_says_purchased != synced_purchased)

                log.append(f"  QUINT: {name} synced_purch={synced_purchased}, "
                           f"BAP_akt={nn in bap_active}, BAP_purch={nn in bap_purchased}, "
                           f"GR_akt={nn in grocy_active}, GR_done={nn in grocy_done}, "
                           f"GR_changed={grocy_changed}, BAP_changed={bap_changed}")

                # Gewünschten Status ermitteln
                if grocy_changed and bap_changed:
                    desired_purchased = grocy_says_purchased
                    log.append(f"  {name}: Konflikt BAP↔Grocy → Grocy gewinnt ({'gekauft' if desired_purchased else 'aktiv'})")
                elif grocy_changed:
                    desired_purchased = grocy_says_purchased
                    log.append(f"  {name}: Grocy geändert → {'gekauft' if desired_purchased else 'aktiv'}")
                elif bap_changed:
                    desired_purchased = bap_says_purchased
                    log.append(f"  {name}: BAP geändert → {'gekauft' if desired_purchased else 'aktiv'}")
                elif nn in grocy_done:
                    desired_purchased = True
                    log.append(f"  {name}: existiert nur in Grocy done → gekauft")
                elif nn in grocy_active:
                    desired_purchased = False
                    log.append(f"  {name}: existiert nur in Grocy aktiv → aktiv")
                elif nn in bap_purchased:
                    desired_purchased = True
                    log.append(f"  {name}: existiert nur in BAP gekauft → gekauft")
                elif nn in bap_active:
                    desired_purchased = False
                    log.append(f"  {name}: existiert nur in BAP aktiv → aktiv")
                else:
                    desired_purchased = synced_purchased
                    log.append(f"  {name}: nirgends vorhanden, behalte synced ({'gekauft' if desired_purchased else 'aktiv'})")

            if desired_purchased != synced_purchased:
                item["purchased"] = desired_purchased
                item["source"] = "grocy" if grocy_changed else ("bap" if bap_changed else "sync")
                if desired_purchased:
                    item["purchased_at"] = datetime.now().isoformat()
                else:
                    item.pop("purchased_at", None)

            # Quantity aus primärer Quelle übernehmen
            if nn not in fresh_items and nn in grocy_active and not nn in grocy_done:
                item["quantity"] = grocy_active[nn].get("amount", qty)

        # ── 6. Actions bauen ───────────────────────────────────
        actions = {"add_bap": [], "add_grocy": [],
                   "mark_purchased_bap": [], "mark_done_grocy": [],
                   "revert_grocy": [], "del_bap": [], "del_grocy_active": []}

        # 6a: Grocy-Duplikate bereinigen (mehrere aktive Einträge für gleichen Namen)
        for nn, entries in grocy_dup_ids.items():
            if len(entries) > 1:
                for dup in entries[:-1]:
                    actions["del_grocy_active"].append(dup)
                    log.append(f"  → Grocy Duplikat löschen: {dup['product_name']} (id={dup['id']})")

        for nn, item in synced_by_nn.items():
            name = item["name"]
            is_purchased = item.get("purchased", False)
            qty = item.get("quantity", 1)
            log.append(f"  DEBUG {name}: synced_purchased={is_purchased}, "
                       f"bap_akt={nn in bap_active}, bap_purch={nn in bap_purchased}, "
                       f"grocy_akt={nn in grocy_active}, grocy_done={nn in grocy_done}")

            if is_purchased:
                if nn in bap_active:
                    actions["mark_purchased_bap"].append(bap_active[nn])
                if nn in grocy_active:
                    if nn in grocy_done:
                        actions["del_grocy_active"].append(grocy_active[nn])
                        log.append(f"  → Grocy aktiven Eintrag löschen (done existiert): {name}")
                    else:
                        actions["mark_done_grocy"].append(grocy_active[nn])
            else:
                if nn in bap_purchased_all:
                    for e in bap_purchased_all[nn]:
                        actions["del_bap"].append(e)
                    if target_list_id:
                        actions["add_bap"].append({"name": name, "qty": qty, "list_id": target_list_id})
                    log.append(f"  → BAP {len(bap_purchased_all[nn])} purchased löschen + aktiv anlegen: {name}")
                elif nn not in bap_active and target_list_id:
                    actions["add_bap"].append({"name": name, "qty": qty, "list_id": target_list_id})
                    log.append(f"  → BAP +{name}")
                if nn in grocy_done:
                    actions["revert_grocy"].append(grocy_done[nn])
                    log.append(f"  → Grocy done rückgängig: {name}")
                elif nn not in grocy_active and grocy_client:
                    actions["add_grocy"].append({"name": name, "qty": qty})
                    log.append(f"  → Grocy +{name}")

        # ── 7. Actions ausführen (alle API-Calls hier!) ───────
        # 7a: Hinzufügen (bevor gelöscht wird — sicherheitshalber)
        for a in actions["add_bap"]:
            try:
                bap_client.add_item(a["list_id"], a["name"], a["qty"])
                log.append(f"  ✓ BAP +{a['name']}")
            except Exception as e:
                log.append(f"  ✗ BAP +{a['name']}: {e}")
        for a in actions["add_grocy"]:
            try:
                grocy_client.add_to_shopping_list(a["name"], a["qty"])
                log.append(f"  ✓ Grocy +{a['name']}")
            except Exception as e:
                log.append(f"  ✗ Grocy +{a['name']}: {e}")

        # 7b: Purchased/Done markieren
        for a in actions["mark_purchased_bap"]:
            try:
                bap_client.mark_purchased(a["list_id"], a["item_id"])
                log.append(f"  ✓ BAP purch {a['title']}")
            except Exception as e:
                log.append(f"  ✗ BAP purch: {e}")
        for a in actions["mark_done_grocy"]:
            try:
                grocy_client.mark_done(a["id"])
                log.append(f"  ✓ Grocy done {a['product_name']}")
            except Exception as e:
                log.append(f"  ✗ Grocy done: {e}")

        # 7c: Grocy duplicate active löschen (statt done zu markieren)
        for a in actions["del_grocy_active"]:
            try:
                grocy_client.remove_from_shopping_list(a["id"])
                log.append(f"  ✓ Grocy del active {a['product_name']}")
            except Exception as e:
                log.append(f"  ✗ Grocy del active: {e}")

        # 7d: Grocy revert (done→active)
        for a in actions["revert_grocy"]:
            try:
                grocy_client.revert_done(a["id"])
                log.append(f"  ✓ Grocy revert {a['product_name']}")
            except Exception as e:
                log.append(f"  ✗ Grocy revert: {e}")

        # 7d: Alte BAP purchased-Einträge löschen (nachdem active angelegt)
        for a in actions["del_bap"]:
            try:
                bap_client.delete_item(a["list_id"], a["item_id"])
                log.append(f"  ✓ BAP del {a['title']}")
            except Exception as e:
                log.append(f"  ✗ BAP del: {e}")

        # ── 8. Alte purchased-Einträge bereinigen (>24h) ──────
        cutoff = datetime.now() - timedelta(hours=24)
        before = len(self._synced_items)
        cleaned = []
        for item in self._synced_items:
            if item.get("purchased"):
                pa = item.get("purchased_at")
                if pa:
                    try:
                        if datetime.fromisoformat(pa) < cutoff:
                            continue
                    except Exception:
                        pass
                if not item.get("purchased_at"):
                    item["purchased_at"] = datetime.now().isoformat()
            cleaned.append(item)
        self._synced_items = cleaned
        removed_old = before - len(self._synced_items)

        # Removed-Liste aufräumen
        all_active = set()
        for item in self._synced_items:
            if not item.get("purchased"):
                all_active.add(self._norm(item["name"]))
        self._removed = [r for r in self._removed if self._norm(r) not in all_active]
        self._removed_set = {self._norm(r) for r in self._removed}

        self.save()

        active_count = len([i for i in self._synced_items if not i.get("purchased")])
        result = (f"🔄 Sync: {active_count} aktiv, "
                  f"+{len(actions['add_bap'])}→BAP, +{len(actions['add_grocy'])}→Grocy, "
                  f"{len(actions['mark_purchased_bap'])} purch→BAP, "
                  f"{len(actions['mark_done_grocy'])} done→Grocy, "
                  f"{len(actions['revert_grocy'])} revert→Grocy, "
                  f"{len(actions['del_grocy_active'])} del→Grocy, "
                  f"{len(actions['del_bap'])} del→BAP, "
                  f"{removed_old} alte purchased entfernt")
        log.append(result)
        log.append("=== SYNC END ===")
        logger.info("\n".join(log))
        return result

    # ─── CRUD ──────────────────────────────────────────────────

    def add_item(self, name: str, quantity: int = 1, category: str = "", source: str = "manual") -> str:
        if self._is_removed(name):
            nn = self._norm(name)
            self._removed = [r for r in self._removed if self._norm(r) != nn]
            self._removed_set.discard(nn)
        existing = self._find(name)
        if existing:
            existing["quantity"] = existing.get("quantity", 1) + quantity
            self.save()
            return f"✅ '{name}' aktualisiert (jetzt x{existing['quantity']})."
        self._synced_items.append({
            "name": name, "quantity": quantity, "category": category,
            "source": source, "added_at": datetime.now().isoformat(),
        })
        self.save()
        return f"✅ '{name}' hinzugefügt."

    def remove_item(self, name: str, bap_client=None, grocy_client=None) -> str:
        self._removed.append(name)
        self._removed_set.add(self._norm(name))
        before = len(self._synced_items)
        self._synced_items = [i for i in self._synced_items if self._norm(i.get("name", "")) != self._norm(name)]
        removed = before - len(self._synced_items)
        self.save()
        if bap_client and removed:
            try:
                from .config import config
                target_name = config.get("bap_list_name", "Einkaufsliste").lower()
                for lst in bap_client.get_lists():
                    if target_name in lst.get("name", "").lower():
                        for item in bap_client.get_list_items(lst["id"]):
                            if self._norm(item.get("title", "")) == self._norm(name) and not item.get("deleted"):
                                bap_client.delete_item(lst["id"], item["id"])
                                break
                        break
            except Exception:
                pass
        if grocy_client and removed:
            try:
                for g in grocy_client.get_shopping_list():
                    if self._norm(g.get("product", {}).get("name", "")) == self._norm(name):
                        grocy_client.remove_from_shopping_list(g["id"])
                        break
            except Exception:
                pass
        return f"✅ '{name}' entfernt." if removed else f"❌ '{name}' nicht gefunden."

    def mark_purchased(self, name: str, bap_client=None, grocy_client=None) -> str:
        item = self._find(name)
        if not item:
            return f"❌ '{name}' nicht gefunden."
        item["purchased"] = True
        item["purchased_at"] = datetime.now().isoformat()
        self.save()
        if bap_client:
            try:
                from .config import config
                target_name = config.get("bap_list_name", "Einkaufsliste").lower()
                for lst in bap_client.get_lists():
                    if target_name in lst.get("name", "").lower():
                        for bitem in bap_client.get_list_items(lst["id"]):
                            if self._norm(bitem.get("title", "")) == self._norm(name) and not bitem.get("deleted"):
                                bap_client.mark_purchased(lst["id"], bitem["id"])
                                break
                        break
            except Exception:
                pass
        if grocy_client:
            try:
                for gitem in grocy_client.get_shopping_list():
                    if not gitem.get("done") and self._norm(gitem.get("product", {}).get("name", "")) == self._norm(name):
                        grocy_client.mark_done(gitem["id"])
                        break
            except Exception:
                pass
        return f"✅ '{name}' als gekauft markiert."

    def update_quantity(self, name: str, quantity: int) -> str:
        item = self._find(name)
        if item:
            item["quantity"] = quantity
            self.save()
            return f"✅ '{name}' Menge auf x{quantity} aktualisiert."
        return f"❌ '{name}' nicht gefunden."

    def clear_purchased(self) -> str:
        before = len(self._synced_items)
        self._synced_items = [i for i in self._synced_items if not i.get("purchased")]
        removed = before - len(self._synced_items)
        self.save()
        return f"✅ {removed} gekaufte Artikel entfernt."

    def get_merged_text(self) -> str:
        active = [i for i in self._synced_items if not i.get("purchased") and not self._is_removed(i.get("name", ""))]
        if not active:
            return "🛒 Einkaufsliste ist leer."
        lines = [f"🛒 **Einkaufsliste** ({len(active)} Artikel):\n"]
        for item in active:
            qty = f" x{item['quantity']}" if item.get('quantity', 1) > 1 else ""
            lines.append(f"  • {item['name']}{qty}")
        return "\n".join(lines)

    def export_for_buymeapie(self) -> str:
        active = [i for i in self._synced_items if not i.get("purchased") and not self._is_removed(i.get("name", ""))]
        return "\n".join(f"{i['name']}" if i.get('quantity', 1) == 1 else f"{i['name']} x{i['quantity']}" for i in active)

    # ─── API: BAP Sync ─────────────────────────────────────────

    def push_to_buymeapie(self, bap_client) -> str:
        from .config import config
        target_name = config.get("bap_list_name", "Einkaufsliste").lower()
        target_list_id = None
        for lst in bap_client.get_lists():
            if target_name in lst.get("name", "").lower():
                target_list_id = lst.get("id")
                break
        if not target_list_id:
            return "❌ Keine passende BAP-Liste gefunden"
        existing_bap = set()
        for item in bap_client.get_active_items(target_list_id):
            existing_bap.add(self._norm(item.get("title", "")))
        added = 0
        for item in self._synced_items:
            if item.get("purchased") or self._is_removed(item.get("name", "")):
                continue
            if self._norm(item.get("name", "")) in existing_bap:
                continue
            try:
                bap_client.add_item(target_list_id, item["name"], item.get("quantity", 1))
                added += 1
            except Exception:
                continue
        return f"📤 {added} Artikel zu BAP gepusht."

    def pull_purchased_from_bap(self, bap_client, grocy_client=None) -> str:
        from .config import config
        target_name = config.get("bap_list_name", "Einkaufsliste").lower()
        marked = 0
        for lst in bap_client.get_lists():
            if target_name in lst.get("name", "").lower():
                for item in bap_client.get_list_items(lst.get("id")):
                    if not item.get("is_purchased") or item.get("deleted"):
                        continue
                    title = item.get("title", "")
                    existing = self._find(title)
                    if existing and not existing.get("purchased"):
                        existing["purchased"] = True
                        existing["purchased_at"] = datetime.now().isoformat()
                        marked += 1
                    if grocy_client:
                        try:
                            nn = self._norm(title)
                            for g in grocy_client.get_shopping_list():
                                if self._norm(g.get("product", {}).get("name", "")) == nn and not g.get("done"):
                                    grocy_client.mark_done(g["id"])
                                    break
                        except Exception:
                            pass
                break
        self.save()
        return f"📥 {marked} Artikel als gekauft markiert."

    def push_to_grocy(self, grocy_client) -> str:
        added = 0
        for item in self._synced_items:
            if item.get("purchased") or self._is_removed(item.get("name", "")):
                continue
            try:
                result = grocy_client.add_to_shopping_list(item["name"], item.get("quantity", 1))
                if "hinzugefügt" in result:
                    added += 1
            except Exception:
                continue
        return f"📤 {added} Artikel zu Grocy gepusht."


shopping_sync = ShoppingSync()
