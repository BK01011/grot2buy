# Grot2Buy v0.27.0

Bidirektionale Synchronisation zwischen Buy Me a Pie, Grocy und lokaler Einkaufsliste.
Architektur: Zentrale Liste (synced_items) als Wahrheitsquelle, **wer geändert hat gewinnt** (statt "Grocy immer").

## Projektstruktur

- `main.py` - FastAPI Server (30+ API-Endpunkte)
- `modules/` - Kernlogik
  - `config.py` - Konfiguration & Verschlüsselung
  - `shopping.py` - Shopping Manager + GrocyClient
  - `shopping_sync.py` - Sync-Algorithmus v5.2 (Änderungsdetektion, Stale-Cleanup)
  - `buymeapie.py` - BAP API Client
- `templates/` - Jinja2 HTML-Templates
- `static/` - CSS/JS Dateien + Logo
- `data/` - Persistente Daten (encrypted)
- `certs/` - HTTPS Zertifikate

## Wichtige Befehle

```bash
# Server starten
python main.py

# Docker
docker compose up -d

# Logs anzeigen
docker logs -f shopping-list

# Code im Container aktualisieren (ohne Neubau)
docker cp modules/shopping_sync.py shopping-list:/app/modules/shopping_sync.py
docker restart shopping-list
```

## API-Endpunkte

- `GET /api/sync/full` - Vollständiger bidirektionaler Sync
- `POST /api/items/add` - Artikel hinzufügen
- `GET /api/synced/items` - Synced-Liste als JSON
- `GET /health` - Status-Ping

## Frontend — Sync-Status

- **Sync-Pill** im Header: Icon + letzte Sync-Zeit, farbcodiert (grün/gelb/rot)
- **Pull-to-Refresh**: Touch-swipe-down auf Mobilgeräten triggert Sync
- Status persistiert in `localStorage('grot2buy_last_sync')`
- Bei Fehler zeigt die Pill rot, bei Sync-Vorgang gelb mit rotierendem Icon

## Sync v5.2 — Bekannte Probleme

1. **Kein Timestamp-Tracking**: Änderungsdetektion vergleicht nur purchased/nicht-purchased. Gleichzeitige Änderungen in beiden Quellen → Grocy gewinnt (konfigurierbar).
2. **Stale BAP-Einträge**: Alte purchased-Duplikate in BAP (durch frühere Syncs erzeugt) werden jetzt alle gelöscht (`bap_purchased_all`).
3. **Neue Items**: Erstmalig auftauchende Artikel werden nicht gegen die andere Quelle validiert → Quell-Status zählt.

## i18n — Mehrsprachigkeit

Sprache wird in `config["lang"]` gespeichert. Neue Sprache hinzufügen:

1. `i18n/fr.json` erstellen (alle Keys aus de.json übersetzen)
2. `AVAILABLE_LANGUAGES` in `modules/i18n.py` erweitern: `["de", "en", "fr"]`
3. Neustarten

## Aktuelle Version

`0.27.0` — Security Audit Batch 2-5 (25 Findings), Docs, Log-Viewer

`0.6.0` — Sicherheitsaudit (30 Findings in 4 Phasen), 
Docker-Optimierung (367 MB → 203 MB, −45%), 
Regressionstest (16 Endpunkte), Token-Expiry (30 Tage)

`0.7.0` — WebSocket Live-Sync (Push statt Polling),
ConnectionManager, `/ws` Endpunkt, Broadcast bei Sync + CRUD,
Cross-Tab Sync, Auto-Reconnect

`0.8.0` — Grocy-Bestand in UI (api/stock, get_stock(),
Meta-Zeile mit Bestandszahl, i18n)

`0.9.0` — Undo/Trash — gelöschte Items wiederherstellbar,
Papierkorb, Undo-Toast, API-Endpunkte, Sync v2

`0.10.0` — Kategoriesortierung im UI (grouped by category,
alphabetisch sortiert, category-header)

`0.11.0` — Offline-Modus (SW-Cache, Write-Queue, Badge)

`0.12.0` — API-Dokumentation (Swagger/OpenAPI, Tags, Security)

`0.13.0` — Performance + UI: Hintergrund-Sync, Sync-Pill-Umbau, Intervall entfernt

`0.14.0` — Batch-Aktionen, Auto-Vervollständigung, Listen teilen

## Security — Batch 2/5 (v24)
1. 🔴 API credentials nicht mehr im Log (main.py:195-207) → user/pass/url aus Logs entfernt
2. 🔴 CORS Origins → `allow_origins=[]` + `allow_credentials=False` (main.py:318)
3. 🔴 api/synced/reset → Backup vor Reset, Fehlerbehandlung (main.py:897-913)
4. 🔴 Share-Token → 30-Tage-Expiry, automatische Bereinigung (main.py:513-555)
5. 🔴 Max input length → 200 Zeichen für Item-Namen (main.py:596)

## Security — Batch 3/5 (v25)
1. 🔴 Stored DOM XSS — `onclick` durch Event-Delegation ersetzt (app.js:427-431)
2. 🟠 Config-Import — Credential-Keys blockiert (password, bap_user, bap_pass, grocy_url, grocy_key) (main.py:1054)
3. 🟠 Docs innerHTML — sanitize via DOM-Parser, script/style/iframe/on* entfernt (app.js:1110)
4. 🟡 Bulk-Add — auf 100 Items begrenzt (main.py:623)
5. 🟡 Login Rate-Limiter — X-Forwarded-For/X-Real-IP Support, Dict-Cap 10k (main.py:338-348, 352)

## Security — Batch 4/5 (v26)
1. 🔴 Share-Tokens verschlüsselt auf Disk via Fernet (main.py:529-530)
2. 🔴 SSRF via Grocy-URL — URL-Validation mit Blocklist (main.py:391-416)
3. 🟠 Share-Token-Offenlegung — Token aus API-Response/DOM entfernt, Revoke via UID, Event-Delegation (main.py:570-571, app.js:795-801)
4. 🟠 DOM-XSS showTrash — escapeHtml für Fehlermeldung (app.js:982)
5. 🟡 Mengenvalidierung — quantity 1-999, Typ-Prüfung (main.py:599-600, 745)

## Security — Batch 5/5 (v27)
1. 🔴 WebSocket — Origin-Validierung gegen CSWSH (main.py:1139-1144)
2. 🟠 SSRF — Blocklist via ipaddress (loopback/private/link-local) (main.py:389-416)
3. 🟠 `/health` — Version aus ungeschützter Response entfernt (main.py:1121-1123)
4. 🟠 Share-Endpunkt — nur öffentliche Felder (name/quantity/category) (main.py:623-628)
5. 🟡 `_atomic_write` — .tmp-Dateien mit 0o600 (config.py:38-41, shopping_sync.py:21-24)

Autor: S.B. | Lizenz: MIT
