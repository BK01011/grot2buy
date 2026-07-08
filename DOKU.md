# Grot2Buy

**Bidirektionale Synchronisation zwischen Buy Me a Pie, Grocy und lokaler Liste**

Autor: **S.B.** | Lizenz: MIT | Erstellt mit KI-Unterstützung
Dank an: Grocy, Buy Me a Pie, opencode, Claude

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

- Bidirektionale Synchronisation (Grocy ↔ BAP ↔ Lokal)
- Automatische Hintergrund-Synchronisation (konfigurierbares Intervall)
- Kategorisierung nach EAN-Präfix
- Mengenverwaltung pro Artikel
- Verschlüsselte Zugangsdaten (Fernet/AES)
- Mobile-optimierte Benutzeroberfläche
- HTTPS mit selbst-gezeichnetem Zertifikat

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
# {"status":"ok","service":"grot2buy","version":"0.3.0"}
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
├── main.py                 # FastAPI Server (700+ Zeilen)
├── Dockerfile              # Docker Image (37 Zeilen)
├── docker-compose.yml      # Docker Compose (20 Zeilen)
├── requirements.txt        # Python-Abhängigkeiten
├── .dockerignore           # Docker-Ignore
├── DOKU.md                 # Diese Dokumentation
├── CHANGELOG.md            # Änderungsprotokoll
├── modules/
│   ├── __init__.py
│   ├── config.py           # Verschlüsselte Konfiguration (158 Zeilen)
│   ├── buymeapie.py        # BAP API Client (178 Zeilen)
│   ├── shopping.py         # Grocy Client + ShoppingManager (437 Zeilen)
│   └── shopping_sync.py    # Bidirektionale Synchronisation + Sync-API (550+ Zeilen)
├── templates/
│   ├── shopping.html       # Hauptseite (177 Zeilen)
│   └── login.html          # Login-Seite (32 Zeilen)
├── static/
│   ├── app.js              # Frontend-Logik (469 Zeilen)
│   └── style.css           # CSS-Styles (636 Zeilen)
├── data/                   # Persistente Daten (Docker Volume)
│   ├── config.json         # Konfiguration
│   ├── shopping_sync.json  # Synced-Liste
│   ├── shopping.json       # Lokale Einkaufsliste
│   └── secret.key          # Verschlüsselungsschlüssel
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
- CORS erlaubt alle Origins (für lokale Nutzung)
- `/api/config/export` gibt **nie** den `secret.key` aus
