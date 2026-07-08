# Grot2Buy v0.2.4

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

## Sync v5.2 — Bekannte Probleme

1. **Kein Timestamp-Tracking**: Änderungsdetektion vergleicht nur purchased/nicht-purchased. Gleichzeitige Änderungen in beiden Quellen → Grocy gewinnt (konfigurierbar).
2. **Stale BAP-Einträge**: Alte purchased-Duplikate in BAP (durch frühere Syncs erzeugt) werden jetzt alle gelöscht (`bap_purchased_all`).
3. **Neue Items**: Erstmalig auftauchende Artikel werden nicht gegen die andere Quelle validiert → Quell-Status zählt.

## Aktuelle Version

`0.2.4` — UI aufgeräumt, Publikationsvorbereitung

Autor: S.B. | Lizenz: MIT | Erstellt mit KI-Unterstützung (opencode, Claude)
