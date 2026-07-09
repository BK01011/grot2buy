# Changelog — Grot2Buy

All changes to Grot2Buy with explanations.

---

## [0.12.0] — 2026-07-09

### 📖 API-Dokumentation (Swagger/OpenAPI)

English summary: FastAPI auto-generates OpenAPI docs at `/api/docs` and `/api/redoc` with Bearer auth.

- `tags_metadata` with 7 endpoint groups (Items, Sync, Trash, Config, System, WebSocket, Docs)
- All endpoints tagged for OpenAPI grouping
- `summary=` description on key API endpoints
- HTTPBearer security scheme with `persistAuthorization`
- Metadata: version, contact, license info
- `docs_url` and `redoc_url` moved to `/api/docs` and `/api/redoc`

**Version**: `0.11.0` → `0.12.0`

---

## [0.11.0] — 2026-07-09

### 📴 Offline-Modus

English summary: offline cache for API reads, write queue replay, offline indicator.

- SW caches `/api/*` GET responses (cache-then-fetch)
- `api()` queues POST/PUT/DELETE when offline, replays on reconnect
- Offline-badge in top bar: 📴 (offline) or ⏳ N (pending queue)
- `showOfflineFallback()` loads cached data from SW when fetch fails offline
- `online`/`offline` event listeners for automatic recovery

**Version**: `0.10.0` → `0.11.0`


## [0.12.0] — 2026-07-09

### 📖 API-Dokumentation (Swagger/OpenAPI)

**Problem**: Es gab keine strukturierte API-Dokumentation. Entwickler mussten den Source-Code lesen.

**Lösung**: FastAPI OpenAPI-Docs mit Tags, Security-Scheme und Metadaten.

**Backend**:
-  mit 7 Gruppen (Items, Sync, Trash, Config, System, WebSocket, Docs)
- Alle Endpoints mit  für OpenAPI-Gruppierung
-  Security Scheme mit 
- Metadaten: Version, Contact, License
-  und  auf  und  gesetzt

**Version**:  → 

---
---

## [0.10.0] — 2026-07-09

### 📂 Kategoriesortierung im UI (grouped by category)

DE version below; English summary: items are now grouped by category headers, sorted alphabetically.

- `renderSyncedItems()` uses `data.by_category` instead of flat list
- Categories sorted alphabetically (A–Z)
- Items within each category sorted alphabetically by name
- Category header shows name + item count
- New CSS: `.category-group`, `.category-header`, `.category-count`

**Cache bust**: `?v=13` → `?v=14`, SW-Cache `grot2buy-v13` → `grot2buy-v14`

**Version**: `0.9.0` → `0.10.0`

---

## [0.9.0] — 2026-07-09

### 🗑️ Undo/Trash — deleted items are recoverable

DE version below; English summary: soft-delete with trash + undo toast.

- Sync data format v2 with `trash` field
- `remove_item` moves to trash instead of hard-delete
- `get_trash()`, `restore_item()`, `empty_trash()` methods
- API endpoints: `GET /api/trash/items`, `POST /api/trash/restore/{name}`, `POST /api/trash/empty`
- `undoToast()` with 5s undo button after delete
- Trash button in header + trash view modal
- Auto-migration from sync v1 → v2

**Version**: `0.8.0` → `0.9.0`

## [0.11.0] — 2026-07-09

### 📴 Offline-Modus

**Problem**: Bei fehlender Internetverbindung zeigte die App nur einen Fehler an. Änderungen gingen verloren.

**Lösung**: Service Worker cacht API-Daten; CRUD-Operationen werden in eine Warteschlange gelegt und bei Wiederherstellung der Verbindung automatisch abgespielt.

**Frontend**:
-  fängt Netzwerkfehler ab → GET schlägt auf Cache zurück, POST/PUT/DELETE werden in  Queue gelegt
- Offline-Badge in der oberen Leiste: 📴 (offline) oder ⏳ N (ausstehende Operationen)
-  lädt gecachte Daten aus dem SW-Cache bei fehlgeschlagenem API-Call
- / Event-Listener → Badge aktualisieren + Queue verarbeiten
-  spielt die Warteschlange nacheinander ab

**Service Worker**:
-  GET-Responses werden jetzt auch gecached (bisher nur CSS/JS/SVG/JSON)

**i18n**: Neue Keys  und  in de.json/en.json

**Version**:  → 

---

---

## [0.8.0] — 2026-07-09

### 📦 Grocy-Bestand in der UI anzeigen

**Neu**: Bei Artikeln aus der Synced-Liste wird der aktuelle Grocy-Lagerbestand angezeigt (falls vorhanden).

**Backend**:
- `GrocyClient.get_stock()` — neue Methode: ruft `GET /api/stock` ab und mapped product_id → Name → Bestand
- `api_synced_items` reichert jedes Item mit `stock`-Feld an (wenn Grocy verbunden)
- Stock wird als float geliefert (Grocy unterstützt Bruchmengen)

**Frontend**:
- `renderItem()` zeigt Bestand in der Meta-Zeile an: "Bestand: 3" (DE) / "Stock: 3" (EN)
- Nur sichtbar wenn Item in Grocy als Produkt existiert und Bestand > 0

**i18n**: Neue Keys `item.stock` in de.json und en.json

**Cache bust**: `?v=12` → `?v=13`, SW-Cache `grot2buy-v12` → `grot2buy-v13`

**Version**: `0.7.0` → `0.8.0`

---

## [0.7.0] — 2026-07-09

### 🔌 WebSocket Live-Sync (Push statt Polling)

**Problem**: UI aktualisierte sich nur nach manuellem Sync oder HTTP-Polling. Mehrere Browser-Tabs waren nicht synchron.

**Lösung**: Echtzeit-Updates via WebSocket an alle verbundenen Clients.

**Backend**:
- `ConnectionManager` — verwaltet alle WebSocket-Verbindungen mit `asyncio.Lock`
- `/ws` WebSocket-Endpunkt — authentifiziert via Cookie (auth_token)
- `broadcast_sync_complete()` — nach jedem Sync: alle Tabs aktualisieren Sync-Pill + Items
- `broadcast_items_updated()` — nach CRUD (add/remove/purchased/quantity/clear)
- WebSocket-Protokoll: `sync_complete`, `items_updated`, `ping`/`pong`
- Background-Sync sendet jetzt `sync_complete` an alle Clients
- Sync- + CRUD-Endpunkte senden Broadcasts

**Frontend**:
- `connectWebSocket()` — verbindet bei `DOMContentLoaded`, Protokoll ws:// oder wss://
- Automatische Reconnect: bis zu 20 Versuche, Backoff 1–10s
- `sync_complete`: aktualisiert Sync-Pill, `localStorage`, Items + Tabs
- `items_updated`: aktualisiert Items + Tabs (Cross-Tab-Sync)
- Fallback: Sync-Button und Timer funktionieren weiterhin via HTTP

**Cache bust**: `?v=11` → `?v=12`, SW-Cache `grot2buy-v11` → `grot2buy-v12`

**Version**: `0.6.0` → `0.7.0`

---

## [0.5.0] — 2026-07-09

### 📱 Sync-Status-Pill + Pull-to-Refresh + Header-Redesign

**New**:
- **Sync-Status-Pill** im Header: Icon + relative Sync-Zeit, farbcodiert (grün/gelb/rot)
- **Pull-to-Refresh**: Touch-swipe-down auf Mobilgeräten triggert Sync
- Status persistiert in `localStorage('grot2buy_last_sync')`
- **Header-Redesign**: Größeres Logo, kleinere Schrift, kompakteres Layout
- Background-Sync + User-initiated Sync getrennt

**Cache bust**: `?v=5` → `?v=8`, SW-Cache `grot2buy-v5` → `grot2buy-v8`

**Version**: `0.4.2` → `0.5.0`

---

## [0.6.0] — 2026-07-09

### 🔒 Security Audit (Phase 1–4) + Docker Optimization

**30 Findings in 4 Phasen — alle behoben.**

**Phase 1 (Critical)**:
- CSRF eliminiert: API nur noch via `Authorization: Bearer`
- `/api/docs/doku` + `/api/docs/changelog` mit `Depends(verify_token)`
- Config-Import blockiert `secret_key` + `auth_token`
- `auth_token`, `grocy_key`, `grocy_url`, `bap_pass` via Fernet verschlüsselt

**Phase 2 (High)**:
- Exception Leaks: generische Fehlermeldungen + `@app.exception_handler` für HTTPException + 500
- Race Conditions: `asyncio.Lock` in `ShoppingSync`; `_sync_running`-Flag
- GrocyClient `close()` + alter Client wird vor `configure_grocy()` geschlossen
- Ephemeral BAP-Clients entfernt: alle nutzen `shopping_manager._bap`
- CORS: `allow_origins` korrigiert
- Atomare Saves (`.tmp` + `os.replace`)

**Phase 3 (Medium)**:
- Fernet-Key `chmod 600`
- `set_encrypted()`/`get_decrypted()` für alle Secrets
- 18 bare `except: pass` durch logging ersetzt
- `/setup` prüft Config-Status
- BAP Password nach `__init__` auf `None` gesetzt
- Token mit 30-Tage-Expiry + `auth_token_created_at`
- Background-Sync + User-Sync parallel via `_sync_running` + Lock
- Dynamische Imports entfernt
- Token-Invalidierung bei Passwort-Änderung

**Phase 4 (Low)**:
- Batch-`save()` in Config
- Auto-Bereinigung purchased-Items nach 24h via `purchased_at`-Timestamp
- UTC-Zeitstempel (`datetime.now(timezone.utc)`)
- Content-Type JSON-Validierung (`JSONDecodeError` abgefangen)
- Config-Export redacted: Secrets → `"***"`
- Sync-Datei hat `"__version__"`-Feld

**Docker Optimization**:
- `gcc` aus apt entfernt (Wheels statt Build) → Image 367 MB → 203 MB (**−45%**)
- `.opencode/` in `.dockerignore` (62 MB node_modules ausgeschlossen)
- Healthcheck: timeout 15s, retries 5
- Build Cache reduziert von 10,5 GB auf 0,4 GB

**Regressionstest (16 Endpunkte)** bestanden, keine Fehler im Log

**Cache bust**: `?v=8` → `?v=11`, SW-Cache `grot2buy-v8` → `grot2buy-v11`

**Version**: `0.5.0` → `0.6.0`

---

## [0.4.2] — 2026-07-08

### 🚀 Initialer Auto-Sync beim Seitenstart

**Bugfix — Einkaufsdaten wurden nicht geladen ohne händischen Sync-Button**

- **Frontend**: `DOMContentLoaded` führt jetzt immer `POST /api/sync/full` aus, bevor `loadItems()` die UI rendert — der Sync-Button ist nur noch für manuelles Re-Sync.
- **Backend**: `api_synced_items` hat `is_initial=True` Flag für den Sync — neu aus BAP auftauchende purchased-Items werden als aktiv (nicht purchased) in die synced-Liste übernommen, damit die Liste beim ersten Start nicht leer bleibt.
- **Backend**: BAP-Client wird in `/api/lists` und `/api/lists/{id}/items` via `shopping_manager._bap` recycelt (kein `create_client()` mehr pro Call).
- **Backend**: Timeout (10s connect, 30s read) für alle BAP-Requests.
- **Frontend**: `watchSyncErrors()` war undefiniert → entfernt.
- **Cache bust**: `?v=4` → `?v=5`, SW-Cache `grot2buy-v3` → `grot2buy-v4`

**Version**: `0.4.1` → `0.4.2`

---

## [0.4.1] — 2026-07-08

## [0.4.0] — 2026-07-08

### 🌗 Dark Mode + Push Notifications + Dead Code Removal

**New**:
- **Dark mode toggle** — Sun/moon icon in header, cycles Auto → Dark → Light; setting in preferences (dropdown Sync/Auto/Dark/Light); persistence via `localStorage` + `prefers-color-scheme` detection
- **Push notifications** — Desktop notifications on sync errors via Service Worker `showNotification()`; permission requested on page load; icon + vibration on notification
- **Dead code removed** (`shopping.py` -297 lines):
  - `ShoppingItem` class — obsolete (replaced by `synced_items` dict)
  - `LocalShoppingList` class — obsolete (replaced by `shopping_sync` JSON)
  - `DATA_DIR` / `SHOPPING_FILE` constants — only used by deleted classes
  - `GrocyClient.get_stock()`, `get_low_stock()`, `to_shopping_text()`, `to_stock_text()` — never called
  - `ShoppingManager.get_items_as_text()`, `get_stock_text()`, `add_item()`, `remove_item()`, `mark_purchased()`, `sync_lists()`, `get_synced_text()`, `export_for_buymeapie()`, `add_to_synced()`, `remove_from_synced()`, `clear_synced()`, `update_quantity()` — duplicates of `shopping_sync` methods, never called
  - `configure_grocy` now uses `get_shopping_list()` instead of removed `get_stock()` for connection test
- `i18n/de.json` + `i18n/en.json` — new keys for dark mode (`header.darkmode`, `settings.appearance_section`, `settings.darkmode_*`) and push notifications (`notify.*`)
- **Cache bust**: `?v=2` → `?v=3` (SW, CSS, manifest, logo)

**Version**: `0.3.1` → `0.4.0`

---

## [0.3.0] — 2026-07-08

### 🌍 Multilingual Support (i18n)

Grot2Buy now speaks German and English — and is ready for additional languages.

**New**:
- `modules/i18n.py` – Translation module with dot-notation, cache, and variable substitution
- `i18n/de.json` – German UI strings (complete)
- `i18n/en.json` – English UI strings (complete)
- Language selection in setup wizard (first step)
- Language selection in settings menu (instant switch with reload)
- `GET/POST /api/config/lang` – API endpoints for language control
- `{{ t("key") }}` – Jinja2 function in all templates
- `__("key")` – JavaScript translation function (embedded from `window._t`)
- Backend API responses translatable (extensible later)

**Adding a new language** (e.g. French):
1. Create `i18n/fr.json` (following `de.json` as a template)
2. Add to `AVAILABLE_LANGUAGES` in `modules/i18n.py`
3. Done – no code structure restart needed

**Version**: `0.2.5` → `0.3.0`

---

## [0.2.5] — 2026-07-08

### PWA (Progressive Web App)

Grot2Buy is now installable as a PWA – add it to the iOS Home Screen,
runs in full-screen mode without browser chrome.

**New**:
- `static/manifest.json` – App name, icons, theme colors
- `static/sw.js` – Service Worker (cache fallback during network outages)
- `apple-touch-icon`, `apple-mobile-web-app-capable` meta tags
- SW registration on all pages

**Version**: `0.2.4` → `0.2.5`

---

## [0.2.4] — 2026-07-08

### UI Cleanup + Publication Preparation

Removed unnecessary UI elements, cleaned up the codebase.
Prepared project for public release:
- README.md, LICENSE (MIT), .gitignore, modules/__init__.py
- Author attribution S.B., AI-creation note, credits

**Version**: `0.2.3` → `0.2.4`

---

## [0.2.3] — 2026-07-08

### Logo Redesign + UI Theme

**Completely new logo**: Slate rounded square with two horizontal sync bars in a
cyan→blue→violet gradient, bold "G2B", three dots representing the three systems (BAP→G2B→Grocy).
No more shopping cart, no golden sync arrow, no blue-violet area.

**UI theme adapted to the logo**:
- `--primary`: cyan `#06b6d4` (buttons, FAB, tabs, spinner)
- `--secondary`: violet `#8b5cf6` (count badge, hover states, accents)
- FAB with gradient (cyan→violet) matching the logo
- Background white (`#ffffff`)
- Cyan focus glow on input fields
- Cache busting (`?v=2`) for logo and CSS

**Version/Chores**:
- Version `0.2.2` → `0.2.3`

---

## [0.2.2] — 2026-07-08

### Bidirectional Algorithm v5.2

**Problem**: Grocy always won ("Grocy always wins"). When BAP marked an item as
purchased but Grocy had an older done entry, the BAP status was discarded.
Concurrent changes in both sources were undefined.

**Solution**: Central `synced_items` as baseline. For each item, compare whether
Grocy or BAP has a *different* status than the baseline → the changed source
determines the new status. On conflict (both changed) → Grocy as tiebreaker.

**Bugfix `revert_grocy`**: Phase 6 never populated `revert_grocy` because the
variable `in_grocy_done` was never set (`nn not in grocy_done` was always True).
→ If desired status was "active" but Grocy had a done entry → no revert →
next sync always reverted back.
Fix: `if nn in grocy_done → actions["revert_grocy"]`.

**Bugfix Fresh Items**: New items (Phase 4) had no sync history in
`synced_items`, so "who changed" failed → stale BAP purchased entries
overwrote the active status.
Fix: `fresh_items` set – Phase 5 skips change detection for fresh items,
keeps the source status.

**Bugfix Stale BAP purchased**: `bap_purchased_all` collects ALL purchased IDs per
normalized name (not just the last one). When switching from purchased→active, all
are deleted, not just the last one (e.g. 4 stale "Hizte" entries).

### Version

- **Version**: `0.2.1` → `0.2.2`
- **Logo**: Modernized with SVG gradient (blue→violet), shopping cart + sync arrow in gold
- **Docs**: `AGENTS.md`, `CHANGELOG.md`, `DOKU.md` updated

---

## [0.2.1] — 2026-07-08

### Bugfix: Grocy Revert + Duplicates

**Problem**: Sync undid Grocy changes (done→active) because Phase 5 checked `grocy_active` before `grocy_done`. When a product exists in Grocy in BOTH lists (active + done), it was mistakenly classified as active and then reset.

**Fix**: Swapped check order in Phase 5 — `grocy_done` now wins before `grocy_active`.

**Problem 2**: When syncing a "purchased" item that exists in Grocy both as active and done, the active entry was marked as done → duplicate done entry.

**Fix**: New action `del_grocy_active`: When an item exists in both Grocy lists, the active entry is deleted instead of being marked as done. No more duplicates.

**Problem 3**: Synced active items that only exist as `done` in Grocy (no active entry) were added as new to Grocy → created a second copy.

**Fix**: `add_grocy` now also checks `grocy_done` — no creation when the item already exists as done.

**Problem 4**: Due to repeated syncs, Grocy had 3x entries for "5 Minuten Terrine Waldpilz" and 2x for "Dienstax" (all `done=0`). The sync only saw the last entry (dict overwrite).

**Fix**: New Phase 2 + 6a: All Grocy IDs are tracked (`grocy_dup_ids`). When multiple active entries exist for the same name, excess ones are deleted via `del_grocy_active`. Only the last one is kept.

### Version

- **Version**: `0.2.0` → `0.2.1`

## [0.2.0] — 2026-07-08

### Sync v5 — Central List, Grocy as Reference

Complete rewrite of the sync algorithm to use a **central list** (synced_items) as the source of truth:

- **No more complex rule priorities**: The synced list is populated from BAP+Grocy and then written 1:1 to both.
- **Grocy wins on conflicts**: When BAP and Grocy disagree (e.g. BAP=purchased, Grocy=active), Grocy wins. This reliably solves the "Dienstax revert problem".
- **New items are automatically adopted**: Items created directly in BAP or Grocy end up in the central list after the next sync.
- **No more inline API calls**: All read/write operations are cleanly separated (Phase 1 read, Phase 4+5 write). This fixes the "appear-and-disappear" problem.

### Bugfixes

- **BAP purchased → active revert fixed**: When Grocy reactivates an item (done→active), the BAP purchased entry is first created as active and then deleted — not the other way around. No more data loss during network errors.
- **Grocy done → purchased reliable**: When Grocy marks an item as done, BAP is reliably marked as purchased.

### Version

- **Version**: `0.1.0` → `0.2.0`

---

## [0.1.0] — 2026-07-08

### Bugfixes

- **Fixed runtime crash**: Added missing sync methods `push_to_buymeapie()`, `pull_purchased_from_bap()`, `push_to_grocy()` in `shopping_sync.py`. The endpoints `/api/sync/push`, `/api/sync/pull` and `/api/sync/grocy/push` now work.
- **Grocy sync fixed (2 bugs)**:
  - `GrocyClient.get_shopping_list()` filtered `done=0` → completed items were never read. Fix: `include_done=True` in `sync_full()`.
  - **Sync rule order corrected**: Rule 1 (purchased) came before Rule 2 (active). If BAP listed an item as purchased, Rule 1 triggered — even if Grocy had reactivated the item. Fix: Swapped rules — "active" wins before "purchased". Additionally, the purchase status in the other source is cleaned up (BAP entry deleted, Grocy-done reverted).
- **Category space fixed**: `" Obst & Gemüse"` → `"Obst & Gemüse"` in `main.py` and `app.js` (bug caused missing icon mappings).
- **changeQuantity() operator precedence fixed**: Fixed incorrect operator precedence in `app.js`.

### Security

- **Password hashing**: Password is now hashed with PBKDF2-SHA256 (600k iterations) instead of storing it in plaintext. Legacy plaintext passwords are automatically detected during login.
- **Secure config export**: `/api/config/export` no longer outputs the `secret.key`. Only `has_secret_key: true/false` and configuration without `auth_token`.
- **Cookie security**: Auth cookie now has `secure=True` and `samesite="strict"`.

### Code Quality

- **Removed**: `except Exception: pass` in sync methods replaced with targeted error handling.
- **Removed**: Inline imports (`from .config import encrypt`) moved from method bodies to module header.

### Version

- **Version**: `0.0.1` → `0.1.0`

---

## [0.0.1] — 2026-07-08

### Initial Release

First version of Grot2Buy with bidirectional synchronization.

### Core Features

- **Bidirectional synchronization** between Buy Me a Pie, Grocy and local list
- **Automatic background synchronization** (configurable interval)
- **Categorization** by EAN prefix
- **Quantity management** per item
- **Encrypted credentials** (Fernet/AES)
- **Mobile-optimized user interface**
- **HTTPS** with self-signed certificate

### Technical

- **FastAPI Server** with 30+ API endpoints
- **Sync Algorithm v4** — Simple decision tree
- **Setup Wizard** for initial installation
- **Docker** with health check and auto-restart

---

## Known Limitations

1. **Grocy inventory not in UI:** Inventory management only via Grocy UI
2. **No multi-user:** Only one BAP account at a time
3. **No WebSocket:** Auto-sync only via interval polling
4. **No undo:** Deleted items cannot be restored

---

## Technical Reference

### Encryption

```python
# Key generation
from cryptography.fernet import Fernet
key = Fernet.generate_key()  # 32 bytes, base64

# Encrypt
token = Fernet(key).encrypt(value.encode()).decode()

# Decrypt
value = Fernet(key).decrypt(token.encode()).decode()
```

### Sync Status Output

```
🔄 Sync: 3 active, +0→BAP, +0→Grocy, 0 purchased→BAP, 0 done→Grocy
```

| Field | Description |
|-------|-------------|
| `active` | Active items in synced_list |
| `→BAP` | New items added to BAP |
| `→Grocy` | New items added to Grocy |
| `purchased→BAP` | Purchases transferred to BAP |
| `done→Grocy` | Purchases marked as done in Grocy |

---

# Changelog — Grot2Buy

Alle Änderungen an Grot2Buy mit Begründungen.

---

## [0.9.0] — 2026-07-09

### 🗑️ Undo/Trash — gelöschte Items wiederherstellbar

**Problem**: Gelöschte Items waren sofort und unwiderruflich weg. Kein Schutz vor Fehlklicks.

**Lösung**: Soft-Delete mit Papierkorb + Undo-Toast.

**Backend**:
- Sync-Datenformat auf v2: neues Feld `trash` in der Sync-Datei
- `remove_item` verschiebt Items in den Papierkorb (statt hartem Löschen)
- `get_trash()` — gibt Papierkorb-Inhalt zurück
- `restore_item(name)` — stellt ein Item wieder her (zurück in `_synced_items`)
- `empty_trash()` — löscht endgültig + clean-up in BAP/Grocy
- Drei neue API-Endpunkte: `GET /api/trash/items`, `POST /api/trash/restore/{name}`, `POST /api/trash/empty`
- Alte Sync-Dateien (v1) werden automatisch migriert

**Frontend**:
- `undoToast()` — Toast mit "Rückgängig"-Button (5s)
- Nach Löschen erscheint "Artikel in den Papierkorb verschoben · Rückgängig"
- Trash-Button in der Header-Leiste öffnet Papierkorb-Ansicht
- Trash-Ansicht: Liste der gelöschten Items mit "Wiederherstellen"-Button
- "Papierkorb leeren" mit Bestätigung → endgültige Löschung
- `toast()` bleibt für normale Benachrichtigungen erhalten

**i18n**: `item.undo`, `item.restored` und gesamter `trash.*` Block in de.json/en.json

**Version**: `0.8.0` → `0.9.0`

---

## [0.10.0] — 2026-07-09

### 📂 Kategoriesortierung im UI

**Problem**: Items wurden flach ohne Gruppierung angezeigt. Kategorien waren nicht sichtbar.

**Lösung**: Grouped View mit Category-Headern, alphabetisch sortiert.

**Frontend**:
- `renderSyncedItems()` nutzt `data.by_category` für kategoriebasierte Darstellung
- Kategorien alphabetisch sortiert (A–Z)
- Items innerhalb jeder Kategorie alphabetisch sortiert
- Category-Header zeigt Name + Anzahl der Items
- Neue CSS-Klassen: `.category-group`, `.category-header`, `.category-count`

**Cache bust**: `?v=13` → `?v=14`, SW-Cache `grot2buy-v13` → `grot2buy-v14`

**Version**: `0.9.0` → `0.10.0`

---

## [0.8.0] — 2026-07-09

### 📦 Grocy-Bestand in der UI anzeigen

**Neu**: Bei Artikeln aus der Synced-Liste wird der aktuelle Grocy-Lagerbestand angezeigt (falls vorhanden).

**Backend**:
- `GrocyClient.get_stock()` — neue Methode: ruft `GET /api/stock` ab und mapped product_id → Name → Bestand
- `api_synced_items` reichert jedes Item mit `stock`-Feld an (wenn Grocy verbunden)

**Frontend**:
- `renderItem()` zeigt Bestand in der Meta-Zeile an: "Bestand: 3" / "Stock: 3"
- Nur sichtbar wenn Item als Produkt in Grocy existiert

**i18n**: Neue Keys `item.stock` in de.json und en.json

**Cache bust**: `?v=12` → `?v=13`, SW-Cache `grot2buy-v12` → `grot2buy-v13`

**Version**: `0.7.0` → `0.8.0`

---

## [0.7.0] — 2026-07-09

### 🔌 WebSocket Live-Sync (Push statt Polling)

**Problem**: UI aktualisierte sich nur nach manuellem Sync oder HTTP-Polling. Mehrere Browser-Tabs waren nicht synchron.

**Lösung**: Echtzeit-Updates via WebSocket an alle verbundenen Clients.

**Backend**:
- `ConnectionManager` — verwaltet alle WebSocket-Verbindungen mit `asyncio.Lock`
- `/ws` WebSocket-Endpunkt — authentifiziert via Cookie (auth_token)
- `broadcast_sync_complete()` — nach jedem Sync: alle Tabs aktualisieren Sync-Pill + Items
- `broadcast_items_updated()` — nach CRUD (add/remove/purchased/quantity/clear)
- WebSocket-Protokoll: `sync_complete`, `items_updated`, `ping`/`pong`
- Background-Sync sendet jetzt `sync_complete` an alle Clients
- Sync- + CRUD-Endpunkte senden Broadcasts

**Frontend**:
- `connectWebSocket()` — verbindet bei `DOMContentLoaded`, Protokoll ws:// oder wss://
- Automatische Reconnect: bis zu 20 Versuche, Backoff 1–10s
- `sync_complete`: aktualisiert Sync-Pill, `localStorage`, Items + Tabs
- `items_updated`: aktualisiert Items + Tabs (Cross-Tab-Sync)
- Fallback: Sync-Button und Timer funktionieren weiterhin via HTTP

**Cache bust**: `?v=11` → `?v=12`, SW-Cache `grot2buy-v11` → `grot2buy-v12`

**Version**: `0.6.0` → `0.7.0`

---

## [0.5.0] — 2026-07-09

### 📱 Sync-Status-Pill + Pull-to-Refresh + Header-Redesign

**Neu**:
- **Sync-Status-Pill** im Header: Icon + relative Sync-Zeit, farbcodiert (grün/gelb/rot)
- **Pull-to-Refresh**: Touch-swipe-down auf Mobilgeräten triggert Sync
- Status persistiert in `localStorage('grot2buy_last_sync')`
- **Header-Redesign**: Größeres Logo, kleinere Schrift, kompakteres Layout
- Background-Sync + User-initiated Sync getrennt

**Cache bust**: `?v=5` → `?v=8`, SW-Cache `grot2buy-v5` → `grot2buy-v8`

**Version**: `0.4.2` → `0.5.0`

---

## [0.6.0] — 2026-07-09

### 🔒 Security Audit (Phase 1–4) + Docker-Optimierung

**30 Findings in 4 Phasen — alle behoben.**

**Phase 1 (Critical)**:
- CSRF eliminiert: API nur noch via `Authorization: Bearer`
- `/api/docs/doku` + `/api/docs/changelog` mit `Depends(verify_token)`
- Config-Import blockiert `secret_key` + `auth_token`
- `auth_token`, `grocy_key`, `grocy_url`, `bap_pass` via Fernet verschlüsselt

**Phase 2 (High)**:
- Exception Leaks: generische Fehlermeldungen + `@app.exception_handler` für HTTPException + 500
- Race Conditions: `asyncio.Lock` in `ShoppingSync`; `_sync_running`-Flag
- GrocyClient `close()` + alter Client wird vor `configure_grocy()` geschlossen
- Ephemere BAP-Clients entfernt: alle nutzen `shopping_manager._bap`
- CORS: `allow_origins` korrigiert
- Atomare Saves (`.tmp` + `os.replace`)

**Phase 3 (Medium)**:
- Fernet-Key `chmod 600`
- `set_encrypted()`/`get_decrypted()` für alle Secrets
- 18 bare `except: pass` durch logging ersetzt
- `/setup` prüft Config-Status
- BAP-Passwort nach `__init__` auf `None` gesetzt
- Token mit 30-Tage-Expiry + `auth_token_created_at`
- Background-Sync + User-Sync parallel via `_sync_running` + Lock
- Dynamische Imports entfernt
- Token-Invalidierung bei Passwort-Änderung

**Phase 4 (Low)**:
- Batch-`save()` in Config
- Auto-Bereinigung purchased-Items nach 24h via `purchased_at`-Timestamp
- UTC-Zeitstempel (`datetime.now(timezone.utc)`)
- Content-Type JSON-Validierung (`JSONDecodeError` abgefangen)
- Config-Export redacted: Secrets → `"***"`
- Sync-Datei hat `"__version__"`-Feld

**Docker-Optimierung**:
- `gcc` aus apt entfernt (Wheels statt Build) → Image 367 MB → 203 MB (**−45%**)
- `.opencode/` in `.dockerignore` (62 MB node_modules ausgeschlossen)
- Healthcheck: timeout 15s, retries 5
- Build Cache reduziert von 10,5 GB auf 0,4 GB

**Regressionstest (16 Endpunkte)** bestanden, keine Fehler im Log

**Cache bust**: `?v=8` → `?v=11`, SW-Cache `grot2buy-v8` → `grot2buy-v11`

**Version**: `0.5.0` → `0.6.0`

---

## [0.4.0] — 2026-07-08

### 🌗 Dark Mode + Push-Benachrichtigungen + Toter Code entfernt

**Neu**:
- **Dark Mode Umschalter** — Sonne/Mond-Icon im Header, Zyklus Auto→Dunkel→Hell; Einstellung in den Preferences (Dropdown Auto/Dunkel/Hell); Speicherung via `localStorage` + `prefers-color-scheme`-Erkennung
- **Push-Benachrichtigungen** — Desktop-Benachrichtigungen bei Sync-Fehlern via Service Worker `showNotification()`; Berechtigungsabfrage beim Seitenladen; Icon + Vibration
- **Toter Code entfernt** (`shopping.py` -297 Zeilen):
  - `ShoppingItem`-Klasse — obsolet (ersetzt durch `synced_items`-Dict)
  - `LocalShoppingList`-Klasse — obsolet (ersetzt durch `shopping_sync`-JSON)
  - `DATA_DIR`/`SHOPPING_FILE`-Konstanten — nur von entfernten Klassen genutzt
  - `GrocyClient.get_stock()`, `get_low_stock()`, `to_shopping_text()`, `to_stock_text()` — nie aufgerufen
  - `ShoppingManager.get_items_as_text()`, `get_stock_text()`, `add_item()`, `remove_item()`, `mark_purchased()`, `sync_lists()`, `get_synced_text()`, `export_for_buymeapie()`, `add_to_synced()`, `remove_from_synced()`, `clear_synced()`, `update_quantity()` — Duplikate von `shopping_sync`-Methoden, nie aufgerufen
  - `configure_grocy` nutzt jetzt `get_shopping_list()` statt des entfernten `get_stock()` für Verbindungstest
- `i18n/de.json` + `i18n/en.json` — neue Keys für Dark Mode (`header.darkmode`, `settings.appearance_section`, `settings.darkmode_*`) und Push-Benachrichtigungen (`notify.*`)
- **Cache-Bust**: `?v=2` → `?v=3` (SW, CSS, Manifest, Logo)

**Version**: `0.3.1` → `0.4.0`

---

## [0.3.0] — 2026-07-08

### 🌍 Mehrsprachigkeit (i18n)

Grot2Buy spricht jetzt Deutsch und Englisch – und ist bereit für weitere Sprachen.

**Neu**:
- `modules/i18n.py` – Übersetzungs-Modul mit Punkt-Notation, Cache und Variablen-Substitution
- `i18n/de.json` – Deutsche UI-Strings (vollständig)
- `i18n/en.json` – Englische UI-Strings (vollständig)
- Sprachauswahl im Setup-Wizard (erster Schritt)
- Sprachauswahl im Einstellungs-Menü (sofortiger Wechsel mit Neuladen)
- `GET/POST /api/config/lang` – API-Endpunkte für Sprachsteuerung
- `{{ t("key") }}` – Jinja2-Funktion in allen Templates
- `__("key")` – JavaScript-Übersetzungsfunktion (eingebettet aus `window._t`)
- Backend-API-Responses übersetzbar (später erweiterbar)

**Neue Sprache hinzufügen** (z.B. Französisch):
1. `i18n/fr.json` erstellen (nach de.json-Vorbild)
2. `AVAILABLE_LANGUAGES` in `modules/i18n.py` ergänzen
3. Fertig – kein Neustart der Code-Struktur nötig

**Version**: `0.2.5` → `0.3.0`

---

## [0.2.5] — 2026-07-08

### PWA (Progressive Web App)

Grot2Buy ist jetzt als PWA installierbar – auf iOS zum HomeScreen hinzufügbar,
läuft im Vollbildmodus ohne Browser-Chrome.

**Neu**:
- `static/manifest.json` – App-Name, Icons, Theme-Farben
- `static/sw.js` – Service Worker (Cache-Fallback bei Netzwerkausfällen)
- `apple-touch-icon`, `apple-mobile-web-app-capable` Meta-Tags
- SW-Registration auf allen Seiten

**Version**: `0.2.4` → `0.2.5`

---

## [0.2.4] — 2026-07-08

### UI aufgeräumt + Publikationsvorbereitung

Nicht benötigte UI-Elemente entfernt, Codebasis bereinigt.
Projekt für öffentliche Veröffentlichung vorbereitet:
- README.md, LICENSE (MIT), .gitignore, modules/__init__.py
- Autorenangabe S.B., KI-Erstellungs-Hinweis, Credits

**Version**: `0.2.3` → `0.2.4`

---

## [0.2.3] — 2026-07-08

### Logo-Redesign + UI-Theme

**Komplett neues Logo**: Slate-Rounded-Square, zwei horizontale Sync-Balken im
cyan→blue→violet Verlauf, fettes "G2B", drei Punkte für die drei Systeme (BAP→G2B→Grocy).
Kein Shopping-Cart mehr, kein goldener Sync-Pfeil, keine blau-violette Fläche.

**UI-Theme an Logo angepasst**:
- `--primary`: cyan `#06b6d4` (Button, FAB, Tabs, Spinner)
- `--secondary`: violet `#8b5cf6` (Count-Badge, Hover-States, Akzente)
- FAB mit Gradient (cyan→violet) passend zum Logo
- Hintergrund weiß (`#ffffff`)
- Cyaner Focus-Glow bei Eingabefeldern
- Cache-Busting (`?v=2`) für Logo und CSS

**Version/Chores**:
- Version `0.2.2` → `0.2.3`

---

## [0.2.2] — 2026-07-08

### Bidirektionaler Algorithmus v5.2

**Problem**: Grocy hat immer gewonnen ("Grocy always wins"). Wenn BAP einen Eintrag als
gekauft markiert hat, Grocy aber einen älteren done-Eintrag hatte, wurde der BAP-Status
verworfen. Gleichzeitige Änderungen in beiden Quellen waren nicht definiert.

**Lösung**: Zentrales `synced_items` als Baseline. Für jedes Item wird verglichen ob
Grocy oder BAP einen *anderen* Status als die Baseline hat → die geänderte Quelle
bestimmt den neuen Status. Bei Konflikt (beide geändert) → Grocy als Tiebreaker.

**Bugfix `revert_grocy`**: Phase 6 hat `revert_grocy` nie befüllt, weil die Variable
`in_grocy_done` nicht gesetzt wurde (`nn not in grocy_done` war immer True).
→ Wenn gewünschter Status "aktiv" war, Grocy aber einen done-Eintrag hatte → kein
Revert → nächster Sync revertierte immer zurück.
Fix: `if nn in grocy_done → actions["revert_grocy"]`.

**Bugfix Frische Items**: Neue Items (Phase 4) hatten keine Sync-Vergangenheit in
`synced_items`, daher schlug "wer hat geändert" fehl → veraltete BAP purchased-Einträge
überschrieben den aktiven Status.
Fix: `fresh_items`-Set – Phase 5 überspringt Änderungsdetektion für frische Items,
behält den Quell-Status.

**Bugfix Stale BAP purchased**: `bap_purchased_all` sammelt ALLE purchased-IDs pro
normalisiertem Namen (nicht nur letzte). Beim Wechsel von purchased→aktiv werden alle
gelöscht, nicht nur der letzte (z.B. 4 stale "Hizte"-Einträge).

### Version

- **Version**: `0.2.1` → `0.2.2`
- **Logo**: Modernisiert mit SVG-Gradient (blau→violett), Einkaufswagen + Sync-Pfeil in Gold
- **Doku**: `AGENTS.md`, `CHANGELOG.md`, `DOKU.md` aktualisiert

---

## [0.2.1] — 2026-07-08

### Bugfix: Grocy-Revert + Duplikate

**Problem**: Sync hat Grocy-Änderungen (done→active) rückgängig gemacht, weil Phase 5 `grocy_active` vor `grocy_done` prüfte. Wenn ein Produkt in Grocy in BEIDEN Listen existiert (aktiv + erledigt), wurde es irrtümlich als aktiv eingestuft und dann zurückgesetzt.

**Fix**: Prüf-Reihenfolge in Phase 5 vertauscht — `grocy_done` gewinnt jetzt vor `grocy_active`.

**Problem 2**: Beim Sync eines "purchased"-Artikels, der in Grocy sowohl als aktiv als auch erledigt existiert, wurde der aktive Eintrag als done markiert → doppelter done-Eintrag.

**Fix**: Neue Aktion `del_grocy_active`: Wenn ein Artikel in beiden Grocy-Listen existiert, wird der aktive Eintrag gelöscht statt als done markiert. Keine Duplikate mehr.

**Problem 3**: Synced-aktive Artikel, die in Grocy nur als `done` existieren (kein aktiver Eintrag), wurden als neu zu Grocy hinzugefügt → erzeugte ein zweites Exemplar.

**Fix**: `add_grocy` prüft jetzt auch `grocy_done` — kein Anlegen wenn der Artikel bereits als erledigt existiert.

**Problem 4**: Grocy hatte durch wiederholte Syncs 3-fache Einträge für "5 Minuten Terrine Waldpilz" und 2-fache für "Dienstax" (alle `done=0`). Der Sync sah nur den letzten Eintrag (Dict-Overwrite).

**Fix**: Neue Phase 2 + 6a: Alle Grocy-IDs werden getrackt (`grocy_dup_ids`). Bei mehreren aktiven Einträgen für denselben Namen werden die überzähligen via `del_grocy_active` gelöscht. Nur der letzte bleibt erhalten.

### Version

- **Version**: `0.2.0` → `0.2.1`

## [0.2.0] — 2026-07-08

### Sync v5 — Zentrale Liste, Grocy als Maßstab

Komplette Neuentwicklung des Sync-Algorithmus auf eine **zentrale Liste** (synced_items) als Wahrheitsquelle:

- **Keine komplexen Regel-Prioritäten mehr**: Die Synced-Liste wird aus BAP+Grocy befüllt und dann 1:1 in beide geschrieben.
- **Grocy gewinnt bei Konflikten**: Wenn BAP und Grocy unterschiedliche Meinungen haben (z.B. BAP=purchased, Grocy=active), gewinnt Grocy. Das löst das "Dienstax-Revert-Problem" zuverlässig.
- **Neue Artikel werden automatisch übernommen**: Artikel, die direkt in BAP oder Grocy angelegt wurden, landen nach dem nächsten Sync in der Zentralliste.
- **Keine inline-API-Calls mehr**: Alle Lese-/Schreiboperationen laufen sauber getrennt (Phase 1 lesen, Phase 4+5 schreiben). Das behebt das "auftauchen-und-verschwinden"-Problem.

### Bugfixes

- **BAP purchased → active Revert gefixt**: Wenn Grocy einen Artikel reaktiviert (done→active), wird der BAP-purchased-Eintrag zuerst als active neu angelegt und dann gelöscht — nicht umgekehrt. Kein Datenverlust mehr bei Netzwerkfehlern.
- **Grocy done → purchased zuverlässig**: Wenn Grocy einen Artikel als done markiert, wird BAP zuverlässig als purchased markiert.

### Version

- **Version**: `0.1.0` → `0.2.0`

---

## [0.1.0] — 2026-07-08

### Bugfixes

- **Runtime-Crash behoben**: Fehlende Sync-Methoden `push_to_buymeapie()`, `pull_purchased_from_bap()`, `push_to_grocy()` in `shopping_sync.py` ergänzt. Die Endpunkte `/api/sync/push`, `/api/sync/pull` und `/api/sync/grocy/push` funktionieren jetzt.
- **Grocy-Sync gefixt (2 Bugs)**:
  - `GrocyClient.get_shopping_list()` filterte `done=0` → erledigte Artikel wurden nie gelesen. Fix: `include_done=True` in `sync_full()`.
  - **Sync-Regel-Reihenfolge korrigiert**: Regel 1 (purchased) stand vor Regel 2 (active). Wenn BAP einen Artikel als gekauft führte, schlug Regel 1 zu — selbst wenn Grocy den Artikel wieder aktiviert hatte. Fix: Regeln getauscht — "aktiv" gewinnt vor "gekauft". Zusätzlich wird der Kaufstatus in der anderen Quelle bereinigt (BAP-Eintrag gelöscht, Grocy-done rückgängig).
- **Kategorie-Leerzeichen gefixt**: `" Obst & Gemüse"` → `"Obst & Gemüse"` in `main.py` und `app.js` (bug führte zu fehlenden Icon-Zuordnungen).
- **changeQuantity()-Operator-Bug gefixt**: Falsche Operator-Precedenz in `app.js` korrigiert.

### Sicherheit

- **Passwort-Hashing**: Passwort wird jetzt mit PBKDF2-SHA256 (600k Iterationen) gehasht statt im Klartext gespeichert. Legacy-Klartext-Passwörter werden beim Login automatisch erkannt.
- **Config-Export gesichert**: `/api/config/export` gibt **nicht mehr** den `secret.key` aus. Nur noch `has_secret_key: true/false` und Konfiguration ohne `auth_token`.
- **Cookie-Security**: Auth-Cookie hat jetzt `secure=True` und `samesite="strict"`.

### Code-Qualität

- **Entfernt**: `except Exception: pass` in Sync-Methoden durch gezielte Fehlerbehandlung ersetzt.
- **Entfernt**: Inline-Imports (`from .config import encrypt`) aus Methodenkörpern an Modulkopf verschoben.

### Version

- **Version**: `0.0.1` → `0.1.0`

---

## [0.0.1] — 2026-07-08

### Initial Release

Erste Version von Grot2Buy mit bidirektionaler Synchronisation.

### Kernfunktionen

- **Bidirektionale Synchronisation** zwischen Buy Me a Pie, Grocy und lokaler Liste
- **Automatische Hintergrund-Synchronisation** (konfigurierbares Intervall)
- **Kategorisierung** nach EAN-Präfix
- **Mengenverwaltung** pro Artikel
- **Verschlüsselte Zugangsdaten** (Fernet/AES)
- **Mobile-optimierte Benutzeroberfläche**
- **HTTPS** mit selbst-gezeichnetem Zertifikat

### Technik

- **FastAPI Server** mit 30+ API-Endpunkten
- **Sync-Algorithmus v4** — Einfacher Entscheidungsbaum
- **Setup-Wizard** für Neuinstallation
- **Docker** mit Health-Check und Auto-Restart

---

## Bekannte Einschränkungen

1. **Grocy-Bestand nicht in UI:** Bestandsverwaltung nur via Grocy-UI
2. **Kein Multi-User:** Nur ein BAP-Account gleichzeitig
3. **Kein WebSocket:** Auto-Sync nur via Intervall-Polling
4. **Kein Undo:** Gelöschte Artikel können nicht wiederhergestellt werden

---

## Technische Referenz

### Verschlüsselung

```python
# Schlüsselgenerierung
from cryptography.fernet import Fernet
key = Fernet.generate_key()  # 32 bytes, base64

# Verschlüsseln
token = Fernet(key).encrypt(value.encode()).decode()

# Entschlüsseln
value = Fernet(key).decrypt(token.encode()).decode()
```

### Synchronisations-Statusausgabe

```
🔄 Sync: 3 aktiv, +0→BAP, +0→Grocy, 0 purchased→BAP, 0 done→Grocy
```

| Feld | Beschreibung |
|------|-------------|
| `aktiv` | Aktive Artikel in synced_list |
| `→BAP` | Neue Artikel zu BAP hinzugefügt |
| `→Grocy` | Neue Artikel zu Grocy hinzugefügt |
| `purchased→BAP` | Käufe an BAP übertragen |
| `done→Grocy` | Käufe in Grocy als done markiert |
