# Changelog — Grot2Buy

All changes to Grot2Buy with explanations.

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
