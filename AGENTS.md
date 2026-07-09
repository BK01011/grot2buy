# Grot2Buy v0.12.0

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

Autor: S.B. | Lizenz: MIT | Erstellt mit KI-Unterstützung (opencode, Claude)
