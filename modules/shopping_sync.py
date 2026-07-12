"""Shopping Sync v5.2 — Zentrale Liste als Quelle der Wahrheit."""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from .config import config, encrypt, decrypt

logger = logging.getLogger("shopping")
DATA_DIR = Path(__file__).parent.parent / "data"
SYNC_FILE = DATA_DIR / "shopping_sync.json"
SYNC_VERSION = 1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _atomic_write(path: Path, content: str):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.chmod(str(tmp), 0o600)
    tmp.replace(path)


SYNC_DATA_VERSION = 2


class ShoppingSync:
    def __init__(self):
        self._synced_items: list[dict] = []
        self._removed: list[str] = []
        self._removed_set: set[str] = set()
        self._trash: list[dict] = []
        self._lock = asyncio.Lock()
        self._sync_running = False
        self._linked_bap = None
        self._linked_grocy = None
        self.load()

    def load(self):
        if SYNC_FILE.exists():
            try:
                raw = SYNC_FILE.read_text()
                if raw.startswith("gAAAAA"):
                    raw = decrypt(raw)
                data = json.loads(raw)
                if isinstance(data, list):
                    self._synced_items = data
                    self._removed = []
                    self._trash = []
                elif isinstance(data, dict):
                    self._synced_items = data.get("items", [])
                    self._removed = data.get("removed", [])
                    self._trash = data.get("trash", [])
                    ver = data.get("__version__", 0)
                    if ver < 2:
                        self._trash = []
                else:
                    self._synced_items = []
                    self._removed = []
                    self._trash = []
                self._removed_set = {self._norm(r) for r in self._removed}
            except Exception as e:
                logger.error(f"Sync-Datei korrupt, starte neu: {e}")
                self._synced_items = []
                self._removed = []
                self._removed_set = set()
                self._trash = []

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            self._removed_set = {self._norm(r) for r in self._removed}
            payload = {
                "__version__": SYNC_DATA_VERSION,
                "items": self._synced_items,
                "removed": self._removed,
                "trash": self._trash,
            }
            content = encrypt(json.dumps(payload, ensure_ascii=False))
            _atomic_write(SYNC_FILE, content)
        except Exception as e:
            logger.error(f"Sync-Datei schreiben fehlgeschlagen: {e}")

    def backup(self) -> str:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = DATA_DIR / f"shopping_sync_backup_{ts}.json"
        if SYNC_FILE.exists():
            import shutil
            shutil.copy2(SYNC_FILE, backup_path)
            logger.info(f"Backup erstellt: {backup_path}")
        return str(backup_path)

    def _norm(self, name: str) -> str:
        return name.lower().strip()

    def _find(self, name: str) -> Optional[dict]:
        nn = self._norm(name)
        for item in self._synced_items:
            if self._norm(item.get("name", "")) == nn:
                return item
        return None

    def _find_active(self, name: str) -> Optional[dict]:
        nn = self._norm(name)
        for item in self._synced_items:
            if not item.get("purchased") and self._norm(item.get("name", "")) == nn:
                return item
        return None

    def _is_removed(self, name: str) -> bool:
        return self._norm(name) in self._removed_set

    async def acquire_lock(self):
        await self._lock.acquire()
        self._sync_running = True

    def release_lock(self):
        self._sync_running = False
        self._lock.release()

    def link_clients(self, bap=None, grocy=None):
        self._linked_bap = bap
        self._linked_grocy = grocy

    # ─── Sync ──────────────────────────────────────────────────

    async def sync_full(self, grocy_client, bap_client, is_initial: bool = False) -> str:
        async with self._lock:
            self._sync_running = True
            try:
                return self._sync_full_inner(grocy_client, bap_client, is_initial)
            finally:
                self._sync_running = False

    def _sync_full_inner(self, grocy_client, bap_client, is_initial: bool = False) -> str:
        log = []
        log.append("=== SYNC START ===")

        # ── 1. BAP lesen ─────────────────────────────────────
        bap_active = {}
        bap_purchased = {}
        bap_purchased_all = {}
        target_list_id = None

        if bap_client:
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
                        bap_amount = item.get("amount", "")
                        qty = 1
                        if bap_amount:
                            try:
                                qty = int(''.join(c for c in bap_amount if c.isdigit()))
                            except ValueError:
                                qty = 1
                        entry = {"title": title, "list_id": lid, "item_id": item.get("id"), "quantity": max(1, qty)}
                        if item.get("is_purchased"):
                            bap_purchased[nn] = entry
                            bap_purchased_all.setdefault(nn, []).append(entry)
                        else:
                            bap_active[nn] = entry
                log.append(f"BAP: active={list(bap_active.keys())}, purchased={list(bap_purchased.keys())}")
            except Exception as e:
                log.append(f"BAP Fehler: {e}")

        # ── 2. Grocy lesen ────────────────────────────────────
        grocy_active = {}
        grocy_done = {}
        grocy_dup_ids = {}
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
        fresh_items = set()
        now_ts = _utcnow().isoformat()

        for nn, entry in bap_active.items():
            if nn not in synced_by_nn:
                item = {"name": entry["title"], "quantity": entry.get("quantity", 1), "category": "",
                       "source": "bap", "added_at": now_ts}
                self._synced_items.append(item)
                synced_by_nn[nn] = item
                fresh_items.add(nn)
                log.append(f"  Neu in synced (BAP aktiv): {entry['title']}")

        for nn, entry in bap_purchased.items():
            if nn not in synced_by_nn:
                if is_initial and nn not in grocy_active and nn not in grocy_done:
                    item = {"name": entry["title"], "quantity": entry.get("quantity", 1), "category": "",
                           "source": "bap", "added_at": now_ts}
                    log.append(f"  Neu in synced (BAP purchased → aktiv weil initial): {entry['title']}")
                else:
                    item = {"name": entry["title"], "quantity": entry.get("quantity", 1), "category": "",
                           "source": "bap", "purchased": True, "purchased_at": now_ts}
                    log.append(f"  Neu in synced (BAP purchased): {entry['title']}")
                self._synced_items.append(item)
                synced_by_nn[nn] = item
                fresh_items.add(nn)

        for nn, entry in grocy_active.items():
            if nn not in synced_by_nn:
                item = {"name": entry["product_name"], "quantity": entry.get("amount", 1), "category": "",
                       "source": "grocy", "added_at": now_ts}
                self._synced_items.append(item)
                synced_by_nn[nn] = item
                fresh_items.add(nn)
                log.append(f"  Neu in synced (Grocy aktiv): {entry['product_name']}")

        for nn, entry in grocy_done.items():
            if nn not in synced_by_nn:
                item = {"name": entry["product_name"], "quantity": entry.get("amount", 1), "category": "",
                       "source": "grocy", "purchased": True, "purchased_at": now_ts}
                self._synced_items.append(item)
                synced_by_nn[nn] = item
                fresh_items.add(nn)
                log.append(f"  Neu in synced (Grocy done): {entry['product_name']}")

        # ── 5. Synced-Status aus Quellen aktualisieren ────────
        now = _utcnow()
        for nn, item in synced_by_nn.items():
            synced_purchased = item.get("purchased", False)
            name = item["name"]
            qty = item.get("quantity", 1)
            added_at = item.get("added_at")
            recently_manual = (
                item.get("source") == "manual"
                and added_at
                and (now - datetime.fromisoformat(added_at)).total_seconds() < 3600
            )

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

                grocy_says_purchased = grocy_purchased
                grocy_changed = grocy_has and (grocy_says_purchased != synced_purchased)

                bap_says_purchased = bap_purchased_flag
                bap_changed = bap_has and (bap_says_purchased != synced_purchased)

                log.append(f"  QUINT: {name} synced_purch={synced_purchased}, "
                           f"BAP_akt={nn in bap_active}, BAP_purch={nn in bap_purchased}, "
                           f"GR_akt={nn in grocy_active}, GR_done={nn in grocy_done}, "
                           f"GR_changed={grocy_changed}, BAP_changed={bap_changed}")

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
                if recently_manual and desired_purchased:
                    log.append(f"  {name}: kürzlich manuell hinzugefügt → aktiv behalten (nicht kaufen)")
                else:
                    item["purchased"] = desired_purchased
                    item["source"] = "grocy" if nn in grocy_done else ("bap" if nn in bap_purchased else "sync")
                    if desired_purchased:
                        item["purchased_at"] = now_ts
                    else:
                        item.pop("purchased_at", None)

            if nn not in fresh_items and nn in grocy_active and not nn in grocy_done:
                item["quantity"] = grocy_active[nn].get("amount", qty)

        # ── 6. Purchased-Cleanup: älter als 30 Tage (oder ohne Datum) entfernen ──
        cutoff = now - timedelta(days=30)
        before = len(self._synced_items)
        self._synced_items = [
            i for i in self._synced_items
            if not i.get("purchased")
            or (i.get("purchased_at") and datetime.fromisoformat(i["purchased_at"]) > cutoff)
        ]
        removed_count = before - len(self._synced_items)
        if removed_count:
            log.append(f"  🧹 {removed_count} alte gekaufte Einträge entfernt")

        # ── 7. Actions bauen ───────────────────────────────────
        actions = {"add_bap": [], "add_grocy": [],
                   "mark_purchased_bap": [], "mark_done_grocy": [],
                   "revert_grocy": [], "del_bap": [], "del_grocy_active": []}

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

        # ── 7. Actions ausführen ───────────────────────────────
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

        for a in actions["del_grocy_active"]:
            try:
                grocy_client.remove_from_shopping_list(a["id"])
                log.append(f"  ✓ Grocy del active {a['product_name']}")
            except Exception as e:
                log.append(f"  ✗ Grocy del active: {e}")

        for a in actions["revert_grocy"]:
            try:
                grocy_client.revert_done(a["id"])
                log.append(f"  ✓ Grocy revert {a['product_name']}")
            except Exception as e:
                log.append(f"  ✗ Grocy revert: {e}")

        for a in actions["del_bap"]:
            try:
                bap_client.delete_item(a["list_id"], a["item_id"])
                log.append(f"  ✓ BAP del {a['title']}")
            except Exception as e:
                log.append(f"  ✗ BAP del: {e}")

        # ── 8. Alte purchased-Einträge bereinigen (>24h) ──────
        cutoff = _utcnow() - timedelta(hours=24)
        before = len(self._synced_items)
        cleaned = []
        for item in self._synced_items:
            if item.get("purchased"):
                pa = item.get("purchased_at")
                if pa:
                    try:
                        if datetime.fromisoformat(pa) < cutoff:
                            continue
                    except Exception as e:
                        logger.debug(f"purchased_at parse: {e}")
                if not item.get("purchased_at"):
                    item["purchased_at"] = _utcnow().isoformat()
            cleaned.append(item)
        self._synced_items = cleaned
        removed_old = before - len(self._synced_items)

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

    async def add_item(self, name: str, quantity: int = 1, category: str = "", source: str = "manual") -> str:
        async with self._lock:
            if self._is_removed(name):
                nn = self._norm(name)
                self._removed = [r for r in self._removed if self._norm(r) != nn]
                self._removed_set.discard(nn)
            existing = self._find_active(name)
            if existing:
                existing["quantity"] = existing.get("quantity", 1) + quantity
                self.save()
                return f"✅ '{name}' aktualisiert (jetzt x{existing['quantity']})."
            self._synced_items.append({
                "name": name, "quantity": quantity, "category": category,
                "source": source, "added_at": _utcnow().isoformat(),
            })
            self.save()
        return f"✅ '{name}' hinzugefügt."

    def propagate_add(self, name: str, quantity: int = 1):
        bap_client = getattr(self, '_linked_bap', None)
        grocy_client = getattr(self, '_linked_grocy', None)
        if bap_client:
            try:
                target_name = config.get("bap_list_name", "Einkaufsliste").lower()
                for lst in bap_client.get_lists():
                    if target_name in lst.get("name", "").lower():
                        bap_client.add_item(lst["id"], name, quantity)
                        break
            except Exception as e:
                logger.debug(f"BAP propagate_add: {e}")
        if grocy_client:
            try:
                grocy_client.add_to_shopping_list(name, quantity)
            except Exception as e:
                logger.debug(f"Grocy propagate_add: {e}")

    async def remove_item(self, name: str) -> str:
        async with self._lock:
            self._removed.append(name)
            self._removed_set.add(self._norm(name))
            item = None
            for i in self._synced_items:
                if self._norm(i.get("name", "")) == self._norm(name):
                    item = i
                    break
            if not item:
                return f"❌ '{name}' nicht gefunden."
            self._synced_items = [i for i in self._synced_items if self._norm(i.get("name", "")) != self._norm(name)]
            trash_item = {
                "name": item.get("name", name),
                "quantity": item.get("quantity", 1),
                "category": item.get("category", ""),
                "trashed_at": _utcnow().isoformat(),
            }
            self._trash.append(trash_item)
            self.save()
        return f"✅ '{name}' in den Papierkorb verschoben."

    def propagate_remove(self, name: str):
        bap_client = getattr(self, '_linked_bap', None)
        grocy_client = getattr(self, '_linked_grocy', None)
        if bap_client:
            try:
                target_name = config.get("bap_list_name", "Einkaufsliste").lower()
                for lst in bap_client.get_lists():
                    if target_name in lst.get("name", "").lower():
                        for bitem in bap_client.get_list_items(lst["id"]):
                            if self._norm(bitem.get("title", "")) == self._norm(name) and not bitem.get("deleted"):
                                bap_client.delete_item(lst["id"], bitem["id"])
                                break
                        break
            except Exception as e:
                logger.debug(f"BAP propagate_remove: {e}")
        if grocy_client:
            try:
                for gitem in grocy_client.get_shopping_list():
                    if self._norm(gitem.get("product", {}).get("name", "")) == self._norm(name):
                        grocy_client.remove_from_shopping_list(gitem["id"])
                        break
            except Exception as e:
                logger.debug(f"Grocy propagate_remove: {e}")

    def get_trash(self) -> list[dict]:
        return list(self._trash)

    async def restore_item(self, name: str) -> str:
        async with self._lock:
            for i, t in enumerate(self._trash):
                if self._norm(t.get("name", "")) == self._norm(name):
                    item = self._trash.pop(i)
                    item.pop("trashed_at", None)
                    self._synced_items.append(item)
                    self._removed = [r for r in self._removed if self._norm(r) != self._norm(name)]
                    self._removed_set = {self._norm(r) for r in self._removed}
                    self.save()
                    return f"✅ '{name}' wiederhergestellt."
            return f"❌ '{name}' nicht im Papierkorb gefunden."

    async def empty_trash(self, bap_client=None, grocy_client=None) -> str:
        async with self._lock:
            count = len(self._trash)
            names = [t.get("name", "") for t in self._trash]
            self._trash = []
            self.save()
        # BAP/Grocy cleanup (outside lock, may be slow)
        if bap_client:
            target_name = config.get("bap_list_name", "Einkaufsliste").lower()
            try:
                for lst in bap_client.get_lists():
                    if target_name in lst.get("name", "").lower():
                        for bitem in bap_client.get_list_items(lst["id"]):
                            if any(self._norm(n) == self._norm(bitem.get("title", "")) for n in names) and not bitem.get("deleted"):
                                bap_client.delete_item(lst["id"], bitem["id"])
                        break
            except Exception as e:
                logger.debug(f"BAP trash cleanup: {e}")
        if grocy_client:
            try:
                for g in grocy_client.get_shopping_list():
                    if any(self._norm(n) == self._norm(g.get("product", {}).get("name", "")) for n in names):
                        grocy_client.remove_from_shopping_list(g["id"])
            except Exception as e:
                logger.debug(f"Grocy trash cleanup: {e}")
        return f"✅ {count} Artikel endgültig gelöscht."

    async def mark_purchased(self, name: str) -> str:
        async with self._lock:
            item = self._find(name)
            if not item:
                return f"❌ '{name}' nicht gefunden."
            item["purchased"] = True
            item["purchased_at"] = _utcnow().isoformat()
            self.save()
        return f"✅ '{name}' als gekauft markiert."

    def propagate_mark_purchased(self, name: str):
        bap_client = getattr(self, '_linked_bap', None)
        grocy_client = getattr(self, '_linked_grocy', None)
        if bap_client:
            try:
                target_name = config.get("bap_list_name", "Einkaufsliste").lower()
                for lst in bap_client.get_lists():
                    if target_name in lst.get("name", "").lower():
                        for bitem in bap_client.get_list_items(lst["id"]):
                            if self._norm(bitem.get("title", "")) == self._norm(name) and not bitem.get("deleted"):
                                bap_client.mark_purchased(lst["id"], bitem["id"])
                                break
                        break
            except Exception as e:
                logger.debug(f"BAP propagate_mark_purchased: {e}")
        if grocy_client:
            try:
                for gitem in grocy_client.get_shopping_list():
                    if not gitem.get("done") and self._norm(gitem.get("product", {}).get("name", "")) == self._norm(name):
                        grocy_client.mark_done(gitem["id"])
                        break
            except Exception as e:
                logger.debug(f"Grocy propagate_mark_purchased: {e}")

    async def update_quantity(self, name: str, quantity: int) -> str:
        async with self._lock:
            item = self._find(name)
            if item:
                item["quantity"] = quantity
                self.save()
                return f"✅ '{name}' Menge auf x{quantity} aktualisiert."
            return f"❌ '{name}' nicht gefunden."

    async def clear_purchased(self) -> str:
        async with self._lock:
            before = len(self._synced_items)
            self._synced_items = [i for i in self._synced_items if not i.get("purchased")]
            removed = before - len(self._synced_items)
            self.save()
            return f"✅ {removed} gekaufte Artikel entfernt."

    async def batch_mark_purchased(self, names: list) -> str:
        marked = 0
        for name in names:
            r = await self.mark_purchased(name)
            if "✅" in r:
                marked += 1
        return f"✅ {marked}/{len(names)} Artikel als gekauft markiert."

    async def batch_remove(self, names: list) -> str:
        removed = 0
        for name in names:
            r = await self.remove_item(name)
            if "✅" in r:
                removed += 1
        return f"✅ {removed}/{len(names)} Artikel in den Papierkorb verschoben."

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
            except Exception as e:
                logger.debug(f"BAP push item: {e}")
                continue
        return f"📤 {added} Artikel zu BAP gepusht."

    def pull_purchased_from_bap(self, bap_client, grocy_client=None) -> str:
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
                        existing["purchased_at"] = _utcnow().isoformat()
                        marked += 1
                    if grocy_client:
                        try:
                            nn = self._norm(title)
                            for g in grocy_client.get_shopping_list():
                                if self._norm(g.get("product", {}).get("name", "")) == nn and not g.get("done"):
                                    grocy_client.mark_done(g["id"])
                                    break
                        except Exception as e:
                            logger.debug(f"Grocy pull purchased: {e}")
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
            except Exception as e:
                logger.debug(f"Grocy push item: {e}")
                continue
        return f"📤 {added} Artikel zu Grocy gepusht."


shopping_sync = ShoppingSync()
