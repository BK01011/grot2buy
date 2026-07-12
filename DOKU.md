# Grot2Buy

**EN** — Bidirectional synchronization between Buy Me a Pie, Grocy and local shopping list
**DE** — Bidirektionale Synchronisation zwischen Buy Me a Pie, Grocy und lokaler Liste

Author: **S.B.** | License: MIT
Thanks to: Grocy, Buy Me a Pie

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Initial Setup](#initial-setup)
6. [Configuration](#configuration)
7. [Usage](#usage)
8. [API Reference](#api-reference)
9. [Sync Logic](#sync-logic)
10. [Troubleshooting](#troubleshooting)
11. [File Structure](#file-structure)
12. [Technical Details](#technical-details)

---

## Overview

Grot2Buy is a self-hosted shopping list management application. It synchronizes bidirectionally between three sources:

| Source | Description |
|--------|-------------|
| **Buy Me a Pie (BAP)** | Mobile shopping list app (iOS/Android) |
| **Grocy** | Household ERP system (inventory, shopping lists) |
| **Local List** | Managed directly in the web UI |

### Key Features

- Bidirectional sync (Grocy ↔ BAP ↔ Local)
- Bidirectional sync (Grocy ↔ BAP ↔ Local) mit **Last writer wins**
- Automatic background sync (configurable interval)
- Categorization by EAN prefix
- Quantity management per item
- Encrypted credentials (Fernet/AES)
- Dark mode (auto/system/manual toggle, persisted in localStorage)
- Push notifications on sync errors (desktop via Service Worker)
- Mobile-optimized user interface
- HTTPS with self-signed certificate
- **Batch operations**: Select + buy/delete multiple items
- **Auto-complete**: Suggestions from Grocy products while typing
- **Shareable lists**: Create public read-only share links
- **WebSocket live sync**: Real-time push on sync/CRUD events
- **Background sync**: Silent refresh without blocking UI
- **Offline mode**: Service Worker cache + write queue

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Web-Browser (UI)               │
│         shopping.html + app.js              │
└─────────────────┬───────────────────────────┘
                  │ HTTPS (Port 8899)
┌─────────────────▼───────────────────────────┐
│            FastAPI Server (main.py)          │
│    ┌─────────────────────────────────────┐  │
│    │         ShoppingSync                │  │
│    │   (shopping_sync.py)                │  │
│    │   Source of truth:                  │  │
│    │   synced_list = Central List        │  │
│    └──────┬──────────────┬───────────────┘  │
│           │              │                  │
│    ┌──────▼──────┐ ┌─────▼──────┐          │
│    │ BAP Client  │ │Grocy Client│          │
│    │(buymeapie.py│ │(shopping.py│          │
│    └──────┬──────┘ └─────┬──────┘          │
└───────────┼──────────────┼─────────────────┘
            │              │
    ┌───────▼───┐   ┌──────▼──────┐
    │ Buy Me a  │   │   Grocy     │
    │   Pie API │   │   API       │
    └───────────┘   └─────────────┘
```

### Data Flow

1. **synced_list** is the central data source (JSON file)
2. During sync, all sources are read and merged
3. Missing items are pushed to missing sources
4. Purchased items are marked as "done"

---

## Prerequisites

- Docker and Docker Compose
- Network access to Buy Me a Pie (optional)
- Network access to Grocy (optional)
- Modern web browser (Chrome, Firefox, Safari)

---

## Installation

### 1. Clone repository / prepare files

```bash
# Choose directory (e.g., $HOME, /opt, or any directory):
INSTALL_DIR="$HOME/grot2buy"
mkdir -p "$INSTALL_DIR" && cd "$INSTALL_DIR"

# If Git is available:
git clone <repo-url> .

# Or copy files manually:
# The project structure should look like this:
# grot2buy/
#   ├── main.py
#   ├── Dockerfile
#   ├── docker-compose.yml
#   ├── requirements.txt
#   ├── .dockerignore
#   ├── modules/
#   │   ├── __init__.py
#   │   ├── config.py
#   │   ├── buymeapie.py
#   │   ├── shopping.py
#   │   └── shopping_sync.py
#   ├── templates/
#   │   ├── shopping.html
#   │   ├── setup.html
#   │   └── login.html
#   └── static/
#       ├── app.js
#       ├── style.css
#       └── logo.svg
```

### 2. Build and start Docker image

```bash
cd "$INSTALL_DIR"

# Build image
docker compose build

# Start container
docker compose up -d

# Show logs
docker compose logs -f
```

### 3. Check service status

```bash
# Health check
curl -k https://localhost:8899/health

# Expected response:
# {"status":"ok","service":"grot2buy"}
```

### 4. Enable auto-start on system boot

```bash
# Docker Compose restart: unless-stopped is already configured
# Check:
docker inspect grot2buy | grep RestartPolicy
```

---

## Initial Setup

### Step 1: Open web UI

```
https://<server-ip>:8899
```

> **Note:** The self-signed SSL certificate must be accepted in the browser.

### Step 2: Setup wizard

On first installation, a setup wizard appears:

1. **Buy Me a Pie (optional)**
   - Enter email address
   - Enter password
   - Click "Connect"

2. **Grocy (optional)**
   - Enter server URL (e.g. `http://192.168.178.154:32772`)
   - Enter API key (in Grocy under "Administration → Manage API keys")
   - Click "Connect"

3. **Done!**
   - The UI is ready to use immediately
   - Settings can be changed at any time

### Step 3: Set password (optional)

To set a password:
1. Open settings (gear icon)
2. Enter password
3. Save

---

## Configuration

### Configuration file

**Path:** `data/config.json`

```json
{
  "password": "aabbccdd00112233...$...",
  "bap_user": {"__encrypted__": true, "value": "..."},
  "bap_pass": {"__encrypted__": true, "value": "..."},
  "grocy_url": "http://192.168.178.154:32772",
  "grocy_key": "Ihr-Grocy-API-Key",
  "bap_list_name": "Einkaufsliste",
  "sync_interval": 5,
  "setup_complete": true
}
```

> **Caution:** The password is stored hashed with **PBKDF2-SHA256** (600,000 iterations). An existing plaintext entry is automatically replaced by the hash on first login.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `password` | string (hash) | `""` | Web UI password (PBKDF2-hashed, empty = no login) |
| `bap_user` | encrypted | - | Buy Me a Pie email |
| `bap_pass` | encrypted | - | Buy Me a Pie password |
| `grocy_url` | string | `""` | Grocy server URL |
| `grocy_key` | string | `""` | Grocy API key |
| `bap_list_name` | string | `"Einkaufsliste"` | BAP list name |
| `sync_interval` | int | `5` | Auto-sync interval in minutes (0 = off) |
| `server_port` | int | `8899` | Server port |

### Encryption

- Credentials are encrypted with **Fernet (AES-128-CBC)**
- Key file: `data/secret.key` (created automatically)
- Important: back up the `data/` directory!

### Change sync interval

Via UI:
1. Open settings
2. "Auto-Sync" → Enter interval (minutes)
3. Save

Via API:
```bash
curl -k -X POST https://localhost:8899/api/config/sync-interval \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"interval": 10}'
```

---

## Usage

### Basic functions

| Action | Description |
|--------|-------------|
| **Add item** | `+` button bottom right |
| **Buy item** | Checkmark on the left of the item |
| **Change quantity** | `+`/`-` buttons on the item |
| **Remove item** | `X` button on the right of the item |
| **Sync** | Sync button top right |

### Tabs

| Tab | Description |
|-----|-------------|
| 📋 Synced | Central list (synced_list) |
| 📦 Grocy | Grocy shopping list only (read-only) |
| 📱 [List name] | Buy Me a Pie list |

### Category mapping by EAN prefix

| Prefix | Category |
|--------|----------|
| 400 | Beverages |
| 401 | Dairy |
| 403 | Sweets |
| 500 | Fruits & Vegetables |
| 690 | Asian products |
| 80 | Italy |
| 30 | France |

---

## API Reference

All endpoints require authorization (Cookie or Bearer Token).

### Authentication

```
Cookie: auth_token=<token>
# or
Header: Authorization: Bearer <token>
```

### Lists

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/lists` | All BAP lists |
| GET | `/api/lists/{id}/items` | Items of a BAP list |

### Items

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/items/add` | Add item |
| POST | `/api/items/add-bulk` | Add multiple items |
| POST | `/api/items/{name}/remove` | Remove item |
| POST | `/api/items/{name}/purchased` | Mark as purchased |
| POST | `/api/items/{name}/quantity` | Update quantity |
| POST | `/api/items/clear-purchased` | Clear purchased items |

### Sync

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/sync/full` | Full sync (Grocy including done items) |
| GET | `/api/sync/push` | Push to BAP |
| GET | `/api/sync/pull` | Pull from BAP |
| GET | `/api/sync/grocy` | Show Grocy list (active only) |
| GET | `/api/sync/grocy/push` | Push to Grocy |
| GET | `/api/sync/grocy/pull` | Pull from Grocy (active only) |

### Data

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/synced` | Synced list (text) |
| GET | `/api/synced/items` | Synced list (JSON) |
| POST | `/api/synced/reset` | Reset list |
| GET | `/api/export` | Export for BAP |
| GET | `/api/categories` | Categories |

### Configuration

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/config` | Read configuration |
| POST | `/api/config/bap` | Update BAP data |
| GET | `/api/config/sync-interval` | Read sync interval |
| POST | `/api/config/sync-interval` | Set sync interval |
| GET | `/api/config/export` | Export configuration (without `secret.key`) |
| POST | `/api/config/import` | Import configuration |

### System

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/system/status` | System status |

### Example: Add item

```bash
curl -k -X POST https://localhost:8899/api/items/add \
  -H "Content-Type: application/json" \
  -d '{"name": "Milch", "quantity": 2, "category": "Milchprodukte"}'
```

### Example: Mark item as purchased

```bash
curl -k -X POST https://localhost:8899/api/items/Milch/purchased
```

---

## Sync Logic

### sync_full() — Sync v5.2 (Last writer wins, bidirectional)

```
┌──────────────────────────────────────────────────────────────┐
│  1. Read all sources (BAP active/purchased, Grocy           │
│     active/done)                                            │
│  2. Build synced index (baseline)                           │
│  3. Phase 4: Merge new items from BAP/Grocy → synced       │
│     (track fresh_items)                                     │
│  4. Phase 5: Change detection against baseline:             │
│        → For each known item:                               │
│          - Grocy status ≠ baseline? → Grocy changed         │
│          - BAP status ≠ baseline? → BAP changed             │
│          - Both changed? → Tiebreaker: Grocy wins           │
│          - Neither changed? → Keep status quo               │
│          - Fresh items → Keep source status                 │
│  5. Build actions (revert_grocy, revert_bap, push,          │
│     del_bap_purchased*)                                     │
│  6. Execute actions                                         │
│  7. Stale purchased cleanup (>24h)                          │
└──────────────────────────────────────────────────────────────┘
```

### Clear rules (Last writer wins, v5.2)

1. **Baseline principle**: `synced_items` is the source of truth. Each item has a stored status (`purchased`/`active`). Only the source that has a *different* status than the baseline has won.

2. **Concurrent change** (both ≠ baseline): → Grocy as tiebreaker. BAP change is discarded (Grocy was right).

3. **Fresh items** (new in Phase 4): No change detection. The status of the source that created the item is adopted.

4. **Stale BAP purchased**: All existing purchased IDs of an item are deleted if the target status is "active" (not just the last one).

### Deduplication

Items are identified by **normalized name** (lowercase, strip):

```python
def _norm(self, name: str) -> str:
    return name.lower().strip()
```

### Removed items

- Items are stored in `shopping_sync.json` → `removed` list
- A deleted item will not be re-added
- Removal only via API or reset

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs shopping-list

# Common errors:
# - Port 8899 already in use → Change port in docker-compose.yml
# - SSL certificate missing → will be created automatically
```

### Grocy connection failed

```bash
# Check Grocy status
curl http://<grocy-ip>:<port>/api/objects/products \
  -H "GROCY-API-KEY: <key>"

# Check API key in Grocy:
# Administration → Manage API keys
```

### Buy Me a Pie login failed

```bash
# Check BAP credentials:
# - Email address correct?
# - Password correct?
# - Account locked?
```

### Sync not working

```bash
# Trigger manual sync
curl -k https://localhost:8899/api/sync/full

# Reset list and re-sync
curl -k -X POST https://localhost:8899/api/synced/reset
```

### SSL certificate error in browser

- Accept self-signed certificate
- Or place your own certificate in `certs/`:
  - `certs/server.crt`
  - `certs/server.key`

---

## File Structure

```
assistant/
├── main.py                 # FastAPI server (1280 lines)
├── Dockerfile              # Docker image (37 lines)
├── docker-compose.yml      # Docker Compose (20 lines)
├── requirements.txt        # Python dependencies
├── .dockerignore           # Docker ignore
├── DOKU.md                 # This documentation
├── CHANGELOG.md            # Changelog
├── modules/
│   ├── __init__.py
│   ├── config.py           # Encrypted config (200 lines)
│   ├── i18n.py             # Translation engine (75 lines)
│   ├── buymeapie.py        # BAP API client (210 lines)
│   ├── shopping.py         # Grocy client + ShoppingManager (205 lines)
│   └── shopping_sync.py    # Bidirectional sync + Sync API (755 lines)
├── templates/
│   ├── shopping.html       # Main page (310 lines)
│   ├── setup.html          # Setup wizard
│   └── login.html          # Login page (37 lines)
├── static/
│   ├── sw.js               # Service Worker (with notification support)
│   ├── app.js              # Frontend logic (1150 lines)
│   ├── style.css           # CSS styles (1090 lines)
│   └── logo.svg            # App icon
├── data/                   # Persistent data (Docker volume)
│   ├── config.json         # Configuration
│   └── shopping_sync.json  # Synced list
└── certs/                  # SSL certificates (Docker volume)
    ├── server.crt
    └── server.key
```

---

## Technical Details

### Python dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | ≥0.104.0 | Web framework |
| uvicorn | ≥0.24.0 | ASGI server |
| httpx | ≥0.25.0 | HTTP client |
| cryptography | ≥41.0.0 | Encryption |
| python-multipart | ≥0.0.6 | Form handling |
| Jinja2 | ≥3.1.0 | Template engine |
| requests | ≥2.31.0 | HTTP client (BAP) |

**Note:** Password hashing uses `hashlib.pbkdf2_hmac` (built-in, no extra dependency).

### Docker

- **Base Image:** `python:3.12-slim`
- **Container Name:** `grot2buy`
- **Port:** `8899` (HTTPS)
- **Volumes:** `./data`, `./certs`
- **Healthcheck:** Every 30s
- **Auto-Restart:** `unless-stopped`

### Docker Compose

```yaml
version: '3.8'
services:
  grot2buy:
    build: .
    container_name: grot2buy
    ports:
      - "8899:8899"
    volumes:
      - ./data:/app/data
      - ./certs:/app/certs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "https://localhost:8899/health", "-k"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Security

- Credentials are stored encrypted with **Fernet (AES-128-CBC)**
- Password is hashed with **PBKDF2-SHA256** (600,000 iterations) — no plaintext
- Auth-Token Cookie: `httponly`, `secure`, `samesite=strict`
- HTTPS with self-signed certificate
- **CORS**: `allow_origins=[]` (no external origins allowed)
- `/api/config/export` never exposes the `secret.key`
- **API credentials**: Never logged (redacted from request logs)
- **SSRF protection**: Grocy URL validated against loopback/private/link-local via `ipaddress` + metadata hostname blocklist
- **WebSocket Origin validation**: CSWSH protection via Origin header check
- **Share tokens**: Fernet-encrypted on disk, 30-day expiry, automatic cleanup
- **DOM XSS protection**: Event delegation instead of inline `onclick`, DOM-Parser sanitization for docs
- **Rate limiting**: Login endpoint: 5 attempts/5 minutes per IP (with X-Forwarded-For support), Dict cap 10k entries
- **Input validation**: Item names max 200 chars, quantity 1–999 strict type check, bulk-add max 100 items
- **Reset safety**: Auto-backup before synced-list reset
- **Temp files**: `_atomic_write` creates `.tmp` files with `0o600` permissions

---

---

# Grot2Buy

**Bidirektionale Synchronisation zwischen Buy Me a Pie, Grocy und lokaler Liste**

Autor: **S.B.** | Lizenz: MIT
Dank an: Grocy, Buy Me a Pie

---

## Inhaltsverzeichnis

1. [Überblick](#überblick)
2. [Architektur](#architektur)
3. [Voraussetzungen](#voraussetzungen)
4. [Installation](#installation)
5. [Ersteinrichtung](#ersteinrichtung)
6. [Konfiguration](#konfiguration)
7. [Benutzung](#benutzung)
8. [API-Referenz](#api-referenz)
9. [Synchronisationslogik](#synchronisationslogik)
10. [Fehlerbehebung](#fehlerbehebung)
11. [Dateistruktur](#dateistruktur)

---

## Überblick

Grot2Buy ist eine selbst-gehostete Anwendung zur Verwaltung von Einkaufslisten. Es synchronisiert bidirektional zwischen drei Quellen:

| Quelle | Beschreibung |
|--------|-------------|
| **Buy Me a Pie (BAP)** | Mobile Einkaufslisten-App (iOS/Android) |
| **Grocy** | ERP-System für den Hausbedarf (Bestand, Einkaufslisten) |
| **Lokale Liste** | Direkt in der Web-UI verwaltet |

### Kernfunktionen

- Bidirektionale Synchronisation (Grocy ↔ BAP ↔ Lokal) mit **Wer geändert hat gewinnt**
- Automatische Hintergrund-Synchronisation (konfigurierbares Intervall)
- Kategorisierung nach EAN-Präfix
- Mengenverwaltung pro Artikel
- Verschlüsselte Zugangsdaten (Fernet/AES)
- Dark Mode (Auto/System/Manuell, persistiert in localStorage)
- Push-Benachrichtigungen bei Sync-Fehlern (Desktop via Service Worker)
- Mobile-optimierte Benutzeroberfläche
- HTTPS mit selbst-gezeichnetem Zertifikat
- **Batch-Aktionen**: Auswahl + mehrere Artikel gleichzeitig kaufen/löschen
- **Auto-Vervollständigung**: Vorschläge aus Grocy-Produkten beim Tippen
- **Freigabe-Links**: Öffentliche Read-Only-Freigabelinks erstellen
- **WebSocket Live-Sync**: Echtzeit-Push bei Sync/CRUD-Ereignissen
- **Hintergrund-Sync**: Stille Aktualisierung ohne UI-Blockade
- **Offline-Modus**: Service Worker Cache + Write-Queue

---

## Architektur

```
┌─────────────────────────────────────────────┐
│              Web-Browser (UI)               │
│         shopping.html + app.js              │
└─────────────────┬───────────────────────────┘
                  │ HTTPS (Port 8899)
┌─────────────────▼───────────────────────────┐
│            FastAPI Server (main.py)          │
│    ┌─────────────────────────────────────┐  │
│    │         ShoppingSync                │  │
│    │   (shopping_sync.py)                │  │
│    │   Quelle der Wahrheit:              │  │
│    │   synced_list = Zentral-Liste       │  │
│    └──────┬──────────────┬───────────────┘  │
│           │              │                  │
│    ┌──────▼──────┐ ┌─────▼──────┐          │
│    │ BAP Client  │ │Grocy Client│          │
│    │(buymeapie.py│ │(shopping.py│          │
│    └──────┬──────┘ └─────┬──────┘          │
└───────────┼──────────────┼─────────────────┘
            │              │
    ┌───────▼───┐   ┌──────▼──────┐
    │ Buy Me a  │   │   Grocy     │
    │   Pie API │   │   API       │
    └───────────┘   └─────────────┘
```

### Datenfluss

1. **synced_list** ist die zentrale Datenquelle (JSON-Datei)
2. Bei Synchronisation werden alle Quellen gelesen und merged
3. Fehlende Artikel werden zu fehlenden Quellen gepusht
4. Gekaufte Artikel werden als "done" markiert

---

## Voraussetzungen

- Docker und Docker Compose
- Netzwerkzugang zu Buy Me a Pie (optional)
- Netzwerkzugang zu Grocy (optional)
- moderner Web-Browser (Chrome, Firefox, Safari)

---

## Installation

### 1. Repository klonen / Dateien bereitstellen

```bash
# Verzeichnis wählen (z.B. $HOME, /opt, oder beliebiges Verzeichnis):
INSTALL_DIR="$HOME/grot2buy"
mkdir -p "$INSTALL_DIR" && cd "$INSTALL_DIR"

# Falls Git verfügbar:
git clone <repo-url> .

# Oder Dateien manuell kopieren:
# Die Projektstruktur sollte wie folgt aussehen:
# grot2buy/
#   ├── main.py
#   ├── Dockerfile
#   ├── docker-compose.yml
#   ├── requirements.txt
#   ├── .dockerignore
#   ├── modules/
#   │   ├── __init__.py
#   │   ├── config.py
#   │   ├── buymeapie.py
#   │   ├── shopping.py
#   │   └── shopping_sync.py
#   ├── templates/
#   │   ├── shopping.html
#   │   ├── setup.html
#   │   └── login.html
#   └── static/
#       ├── app.js
#       ├── style.css
#       └── logo.svg
```

### 2. Docker Image bauen und starten

```bash
cd "$INSTALL_DIR"

# Image bauen
docker compose build

# Container starten
docker compose up -d

# Logs anzeigen
docker compose logs -f
```

### 3. Service-Status prüfen

```bash
# Health-Check
curl -k https://localhost:8899/health

# Erwartete Antwort:
# {"status":"ok","service":"grot2buy"}
```

### 4. Auto-Start bei Systemstart aktivieren

```bash
# Docker Compose restart: unless-stopped ist bereits konfiguriert
# Prüfen:
docker inspect grot2buy | grep RestartPolicy
```

---

## Ersteinrichtung

### Schritt 1: Web-UI öffnen

```
https://<server-ip>:8899
```

> **Hinweis:** Das selbst-gezeichnete SSL-Zertifikat muss im Browser akzeptiert werden.

### Schritt 2: Setup-Wizard

Bei der ersten Installation erscheint ein Setup-Wizard:

1. **Buy Me a Pie (optional)**
   - E-Mail-Adresse eingeben
   - Passwort eingeben
   - Auf "Verbinden" klicken

2. **Grocy (optional)**
   - Server-URL eingeben (z.B. `http://192.168.178.154:32772`)
   - API-Key eingeben (in Grocy unter "Administration → Manage API keys")
   - Auf "Verbinden" klicken

3. **Fertig!**
   - Die UI ist sofort einsatzbereit
   - Einstellungen können jederzeit geändert werden

### Schritt 3: Passwort setzen (optional)

Zum Setzen eines Passworts:
1. Einstellungen (Zahnrad) öffnen
2. Passwort eingeben
3. Speichern

---

## Konfiguration

### Konfigurationsdatei

**Pfad:** `data/config.json`

```json
{
  "password": "aabbccdd00112233...$...",
  "bap_user": {"__encrypted__": true, "value": "..."},
  "bap_pass": {"__encrypted__": true, "value": "..."},
  "grocy_url": "http://192.168.178.154:32772",
  "grocy_key": "Ihr-Grocy-API-Key",
  "bap_list_name": "Einkaufsliste",
  "sync_interval": 5,
  "setup_complete": true
}
```

> **Achtung:** Das Passwort wird mit **PBKDF2-SHA256** gehasht gespeichert (600.000 Iterationen). Ein vorhandener Klartext-Eintrag wird beim ersten Login automatisch durch den Hash ersetzt.

### Parameter

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `password` | string (hash) | `""` | Web-UI Passwort (PBKDF2-gehasht, leer = kein Login) |
| `bap_user` | encrypted | - | Buy Me a Pie E-Mail |
| `bap_pass` | encrypted | - | Buy Me a Pie Passwort |
| `grocy_url` | string | `""` | Grocy Server-URL |
| `grocy_key` | string | `""` | Grocy API-Key |
| `bap_list_name` | string | `"Einkaufsliste"` | Name der BAP-Liste |
| `sync_interval` | int | `5` | Auto-Sync Intervall in Minuten (0 = aus) |
| `server_port` | int | `8899` | Server-Port |

### Verschlüsselung

- Zugangsdaten werden mit **Fernet (AES-128-CBC)** verschlüsselt
- Schlüssel: `data/secret.key` (wird automatisch erstellt)
- Wichtig: `data/`-Verzeichnis sichern!

### Sync-Intervall ändern

Über die UI:
1. Einstellungen öffnen
2. "Auto-Sync" → Intervall eingeben (Minuten)
3. Speichern

Über die API:
```bash
curl -k -X POST https://localhost:8899/api/config/sync-interval \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"interval": 10}'
```

---

## Benutzung

### Grundfunktionen

| Aktion | Beschreibung |
|--------|-------------|
| **Artikel hinzufügen** | `+` Button unten rechts |
| **Artikel kaufen** | Häkchen links am Artikel |
| **Menge ändern** | `+`/`-` Buttons am Artikel |
| **Artikel entfernen** | `X` Button rechts am Artikel |
| **Synchronisieren** | Sync-Button oben rechts |

### Tabs

| Tab | Beschreibung |
|-----|-------------|
| 📋 Synchronisiert | Zentrale Liste (synced_list) |
| 📦 Grocy | Nur Grocy-Einkaufsliste (read-only) |
| 📱 [Listenname] | Buy Me a Pie Liste |

### Kategorie-Zuordnung nach EAN-Präfix:

| Präfix | Kategorie |
|--------|-----------|
| 400 | Getränke |
| 401 | Milchprodukte |
| 403 | Süßigkeiten |
| 500 | Obst & Gemüse |
| 690 | Asia-Produkte |
| 80 | Italien |
| 30 | Frankreich |

---

## API-Referenz

Alle Endpunkte erfordern eine Autorisierung (Cookie oder Bearer Token).

### Authentifizierung

```
Cookie: auth_token=<token>
# oder
Header: Authorization: Bearer <token>
```

### Listen

| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| GET | `/api/lists` | Alle BAP-Listen |
| GET | `/api/lists/{id}/items` | Artikel einer BAP-Liste |

### Artikel

| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| POST | `/api/items/add` | Artikel hinzufügen |
| POST | `/api/items/add-bulk` | Mehrere Artikel hinzufügen |
| POST | `/api/items/{name}/remove` | Artikel entfernen |
| POST | `/api/items/{name}/purchased` | Als gekauft markieren |
| POST | `/api/items/{name}/quantity` | Menge aktualisieren |
| POST | `/api/items/clear-purchased` | Erledigte löschen |

### Synchronisation

| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| GET | `/api/sync/full` | Vollständiger Sync (Grocy inkl. done-Items) |
| GET | `/api/sync/push` | Push zu BAP |
| GET | `/api/sync/pull` | Pull aus BAP |
| GET | `/api/sync/grocy` | Grocy-Liste anzeigen (nur aktive) |
| GET | `/api/sync/grocy/push` | Push zu Grocy |
| GET | `/api/sync/grocy/pull` | Pull aus Grocy (nur aktive)

### Daten

| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| GET | `/api/synced` | Synced-Liste (Text) |
| GET | `/api/synced/items` | Synced-Liste (JSON) |
| POST | `/api/synced/reset` | Liste zurücksetzen |
| GET | `/api/export` | Export für BAP |
| GET | `/api/categories` | Kategorien |

### Konfiguration

| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| GET | `/api/config` | Konfiguration lesen |
| POST | `/api/config/bap` | BAP-Daten aktualisieren |
| GET | `/api/config/sync-interval` | Sync-Intervall lesen |
| POST | `/api/config/sync-interval` | Sync-Intervall setzen |
| GET | `/api/config/export` | Konfiguration exportieren (ohne `secret.key`) |
| POST | `/api/config/import` | Konfiguration importieren |

### System

| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| GET | `/health` | Health-Check |
| GET | `/api/system/status` | System-Status |

### Beispiel: Artikel hinzufügen

```bash
curl -k -X POST https://localhost:8899/api/items/add \
  -H "Content-Type: application/json" \
  -d '{"name": "Milch", "quantity": 2, "category": "Milchprodukte"}'
```

### Beispiel: Artikel als gekauft markieren

```bash
curl -k -X POST https://localhost:8899/api/items/Milch/purchased
```

---

## Synchronisationslogik

### sync_full() — Sync v5.2 (Wer geändert hat gewinnt, bidirektional)

```
┌──────────────────────────────────────────────────────────────┐
│  1. Alle Quellen lesen (BAP active/purchased, Grocy         │
│     active/done)                                            │
│  2. Synced-Index aufbauen (Baseline)                        │
│  3. Phase 4: Neue Artikel aus BAP/Grocy → synced mergen    │
│     (fresh_items merken)                                    │
│  4. Phase 5: Änderungsdetektion gegen Baseline:             │
│        → Für jedes bekannte Item:                           │
│          - Grocy-Status ≠ Baseline? → Grocy hat geändert    │
│          - BAP-Status ≠ Baseline? → BAP hat geändert        │
│          - Beide geändert? → Tiebreaker: Grocy gewinnt      │
│          - Keine geändert? → Status quo behalten            │
│          - Frische Items → Quell-Status behalten            │
│  5. Actions bauen (revert_grocy, revert_bap, push,          │
│     del_bap_purchased*)                                     │
│  6. Actions ausführen                                       │
│  7. Stale purchased-Bereinigung (>24h)                      │
└──────────────────────────────────────────────────────────────┘
```

### Klare Regeln (Wer geändert hat gewinnt, v5.2)

1. **Baseline-Prinzip**: `synced_items` ist die Wahrheitsquelle. Jedes Item hat
   einen gespeicherten Status (`purchased`/`active`). Nur die Quelle, die einen
   *anderen* Status als die Baseline hat, hat gewonnen.

2. **Gleichzeitige Änderung** (beide ≠ Baseline): → Grocy als Tiebreaker.
   BAP-Änderung wird verworfen (Grocy hatte Recht).

3. **Frische Items** (neu in Phase 4): Keine Änderungsdetektion. Der Status der
   Quelle, die das Item angelegt hat, wird übernommen.

4. **Stale BAP purchased**: Alle vorhandenen purchased-IDs eines Items werden
   gelöscht wenn der Zielstatus "aktiv" ist (nicht nur der letzte).

### De-Duplizierung

Artikel werden per **normalisiertem Namen** (lowercase, strip) identifiziert:

```python
def _norm(self, name: str) -> str:
    return name.lower().strip()
```

### Gelöschte Artikel

- Artikel werden in `shopping_sync.json` → `removed`-Liste gespeichert
- Ein gelöschter Artikel wird nicht wieder hinzugefügt
- Entfernung nur manuell über API oder Reset

---

## Fehlerbehebung

### Container startet nicht

```bash
# Logs prüfen
docker compose logs shopping-list

# Häufige Fehler:
# - Port 8899 bereits belegt → Port ändern in docker-compose.yml
# - SSL-Zertifikat fehlt → wird automatisch erstellt
```

### Grocy-Verbindung fehlgeschlagen

```bash
# Grocy-Status prüfen
curl http://<grocy-ip>:<port>/api/objects/products \
  -H "GROCY-API-KEY: <key>"

# API-Key prüfen in Grocy:
# Administration → Manage API keys
```

### Buy Me a Pie Login fehlgeschlagen

```bash
# BAP-Zugangsdaten prüfen:
# - E-Mail-Adresse korrekt?
# - Passwort korrekt?
# - Account gesperrt?
```

### Sync funktioniert nicht

```bash
# Manuellen Sync auslösen
curl -k https://localhost:8899/api/sync/full

# Liste zurücksetzen und neu synchronisieren
curl -k -X POST https://localhost:8899/api/synced/reset
```

### SSL-Zertifikat-Fehler im Browser

- Selbst-gezeichnetes Zertifikat akzeptieren
- Oder eigenes Zertifikat in `certs/` ablegen:
  - `certs/server.crt`
  - `certs/server.key`

---

## Dateistruktur

```
assistant/
├── main.py                 # FastAPI Server (1280 Zeilen)
├── Dockerfile              # Docker Image (37 Zeilen)
├── docker-compose.yml      # Docker Compose (20 Zeilen)
├── requirements.txt        # Python-Abhängigkeiten
├── .dockerignore           # Docker-Ignore
├── DOKU.md                 # Diese Dokumentation
├── CHANGELOG.md            # Änderungsprotokoll
├── modules/
│   ├── __init__.py
│   ├── config.py           # Verschlüsselte Konfiguration (200 Zeilen)
│   ├── i18n.py             # Übersetzungs-Modul (75 Zeilen)
│   ├── buymeapie.py        # BAP API Client (210 Zeilen)
│   ├── shopping.py         # Grocy Client + ShoppingManager (205 Zeilen)
│   └── shopping_sync.py    # Bidirektionale Synchronisation + Sync-API (755 Zeilen)
├── templates/
│   ├── shopping.html       # Hauptseite (310 Zeilen)
│   ├── setup.html          # Setup-Wizard
│   └── login.html          # Login-Seite (37 Zeilen)
├── static/
│   ├── sw.js               # Service Worker (mit Benachrichtigungen)
│   ├── app.js              # Frontend-Logik (1150 Zeilen)
│   ├── style.css           # CSS-Styles (1090 Zeilen)
│   └── logo.svg            # App-Icon
├── data/                   # Persistente Daten (Docker Volume)
│   ├── config.json         # Konfiguration
│   └── shopping_sync.json  # Synced-Liste
└── certs/                  # SSL-Zertifikate (Docker Volume)
    ├── server.crt
    └── server.key
```

---

## Technische Details

### Python-Abhängigkeiten

| Paket | Version | Zweck |
|-------|---------|-------|
| fastapi | ≥0.104.0 | Web-Framework |
| uvicorn | ≥0.24.0 | ASGI-Server |
| httpx | ≥0.25.0 | HTTP-Client |
| cryptography | ≥41.0.0 | Verschlüsselung |
| python-multipart | ≥0.0.6 | Formular-Handling |
| Jinja2 | ≥3.1.0 | Template-Engine |
| requests | ≥2.31.0 | HTTP-Client (BAP) |

**Hinweis:** Passwort-Hashing verwendet `hashlib.pbkdf2_hmac` (Built-in, keine extra Dependency).

### Docker

- **Base Image:** `python:3.12-slim`
- **Container-Name:** `grot2buy`
- **Port:** `8899` (HTTPS)
- **Volumes:** `./data`, `./certs`
- **Healthcheck:** Alle 30s
- **Auto-Restart:** `unless-stopped`

### Docker Compose

```yaml
version: '3.8'
services:
  grot2buy:
    build: .
    container_name: grot2buy
    ports:
      - "8899:8899"
    volumes:
      - ./data:/app/data
      - ./certs:/app/certs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "https://localhost:8899/health", "-k"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Sicherheit

- Zugangsdaten werden mit **Fernet (AES-128-CBC)** verschlüsselt gespeichert
- Passwort wird mit **PBKDF2-SHA256** (600.000 Iterationen) gehasht — kein Klartext
- Auth-Token Cookie: `httponly`, `secure`, `samesite=strict`
- HTTPS mit selbst-gezeichnetem Zertifikat
- **CORS**: `allow_origins=[]` (keine externen Origins erlaubt)
- `/api/config/export` gibt **nie** den `secret.key` aus
- **API-Zugangsdaten**: Niemals geloggt (aus Request-Logs entfernt)
- **SSRF-Schutz**: Grocy-URL wird gegen Loopback/Private/Link-Local via `ipaddress` + Metadata-Hostname-Blocklist validiert
- **WebSocket Origin-Validierung**: CSWSH-Schutz via Origin-Header-Prüfung
- **Share-Tokens**: Fernet-verschlüsselt auf Disk, 30-Tage-Expiry, automatische Bereinigung
- **DOM-XSS-Schutz**: Event-Delegation statt inline `onclick`, DOM-Parser-Sanitierung für Docs
- **Rate-Limiting**: Login-Endpunkt: 5 Versuche/5 Minuten pro IP (mit X-Forwarded-For-Unterstützung), Dict-Cap 10k Einträge
- **Eingabevalidierung**: Item-Namen max. 200 Zeichen, Menge 1–999 strikte Typ-Prüfung, Bulk-Add max. 100 Items
- **Reset-Sicherheit**: Auto-Backup vor Sync-Liste-Reset
- **Temp-Dateien**: `_atomic_write` erstellt `.tmp`-Dateien mit `0o600`-Berechtigungen
