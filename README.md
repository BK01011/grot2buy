# Grot2Buy

Bidirectional sync between **Buy Me a Pie**, **Grocy** and a local shopping list.
Grot2Buy merges your shopping list services into one central list and keeps them consistent.

---

## Features

- **Bidirectional Sync** – Grocy ↔ Grot2Buy ↔ Buy Me a Pie
- **Auto-Sync** – Configurable interval (web UI)
- **PWA** – Installable on iOS/Android homescreen (fullscreen mode)
- **Web-UI** – Responsive, mobile-optimized
- **i18n** – German & English, easy to extend
- **Setup Wizard** – Initial setup via browser
- **Docker** – Port 8899, HTTPS included
- **Encrypted** – AES-256 (Fernet) for data at rest

---

## Quick Start

```bash
docker compose up -d
```

Then open in your browser: `https://<server-ip>:8899`

The setup wizard guides you through the configuration.

---

## Requirements

- Linux, macOS or Windows (with Docker Desktop / WSL2)
- Docker + Docker Compose
- 512 MB RAM, 1 GB free disk

---

## Configuration

All settings are managed through the web UI:

| Step | Description |
|------|-------------|
| 1 | Set a login password (first visit `/setup`) |
| 2 | Buy Me a Pie (email + password) |
| 3 | Grocy (server URL + API key) |
| 4 | Sync interval (default 5 minutes) |

---

## PWA — iOS / Android

Once Grot2Buy is running, you can add it to your homescreen like a native app.

### iOS
1. Open Safari → `https://<your-ip>:8899`
2. Tap the **Share button** (center of bottom bar)
3. Scroll down → tap **"Add to Home Screen"**
4. Confirm the name → tap **"Add"**
5. The app icon appears on your homescreen – runs in fullscreen like a native app

### Android
Chrome shows an install banner on first visit (or menu → "Install").

---

## API (Selection)

| Endpoint | Description |
|----------|-------------|
| `GET /api/sync/full` | Trigger full sync |
| `POST /api/items/add` | Add an item |
| `GET /api/synced/items` | Synced list as JSON |
| `GET /health` | Status ping |

Full API documentation: [DOKU.md](DOKU.md)

---

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn
- **Frontend:** Vanilla JS, CSS3 (no framework)
- **Encryption:** Fernet (AES-256-CBC)
- **Auth:** PBKDF2-SHA256 + Bearer Token
- **Container:** Docker + Compose, Health-Check
- **i18n:** JSON-based, extensible

---

## Author

**S.B.** — Concept, development, design

---

## AI Assistance

This tool was created with AI assistance.

### Thanks to

- **[opencode](https://opencode.ai)** – AI-powered development environment
- **Claude** (Anthropic) – Code generation & architecture guidance
- **Grocy** ([grocy.info](https://grocy.info)) – Household ERP system
- **Buy Me a Pie** ([buymeapie.com](https://buymeapie.com)) – The mobile shopping list

---

## License

MIT — see [LICENSE](LICENSE).

Copyright (c) 2026 **S.B.**

---

# Grot2Buy

Bidirektionale Synchronisation zwischen **Buy Me a Pie**, **Grocy** und lokaler Einkaufsliste.
Grot2Buy führt deine Einkaufslisten-Dienste in einer zentralen Liste zusammen und hält sie konsistent.

---

## Features

- **Bidirektionaler Sync** – Grocy ↔ Grot2Buy ↔ Buy Me a Pie
- **Auto-Sync** – Konfigurierbares Intervall (Web-UI)
- **PWA** – Installierbar auf iOS/Android-Homescreen (Vollbildmodus)
- **Web-UI** – Responsiv, mobil-optimiert
- **Mehrsprachig** – Deutsch & Englisch, einfach erweiterbar
- **Setup-Wizard** – Ersteinrichtung via Browser
- **Docker** – Port 8899, HTTPS inklusive
- **Verschlüsselt** – AES-256 (Fernet) für ruhende Daten

---

## Quick Start

```bash
docker compose up -d
```

Danach im Browser öffnen: `https://<server-ip>:8899`

Der Setup-Wizard führt durch die Konfiguration.

---

## Systemvoraussetzungen

- Linux, macOS oder Windows (mit Docker Desktop / WSL2)
- Docker + Docker Compose
- 512 MB RAM, 1 GB freier Plattenplatz

---

## Konfiguration

Alle Einstellungen werden über die Web-UI vorgenommen:

| Schritt | Beschreibung |
|---------|-------------|
| 1 | Login-Passwort vergeben (erster Aufruf `/setup`) |
| 2 | Buy Me a Pie (E-Mail + Passwort) |
| 3 | Grocy (Server-URL + API-Key) |
| 4 | Sync-Intervall (Standard 5 Minuten) |

---

## PWA — iOS / Android installieren

Sobald Grot2Buy läuft, kannst du es wie eine native App auf deinen Homescreen legen.

### iOS
1. Safari öffnen → `https://<deine-ip>:8899`
2. **Teilen-Button** (Mitte der unteren Leiste)
3. **"Zum Home-Bildschirm"** tippen
4. Name bestätigen → **"Hinzufügen"**
5. App-Icon erscheint auf dem Homescreen – wie eine native App

### Android
Chrome zeigt beim ersten Besuch einen Install-Banner an (oder Menü → "Installieren").

---

## API (Auswahl)

| Endpunkt | Beschreibung |
|----------|-------------|
| `GET /api/sync/full` | Vollständigen Sync auslösen |
| `POST /api/items/add` | Artikel hinzufügen |
| `GET /api/synced/items` | Synced-Liste als JSON |
| `GET /health` | Status-Ping |

Vollständige API-Dokumentation: [DOKU.md](DOKU.md)

---

## Technik

- **Backend:** Python 3.12, FastAPI, Uvicorn
- **Frontend:** Vanilla JS, CSS3 (kein Framework)
- **Verschlüsselung:** Fernet (AES-256-CBC)
- **Authentifizierung:** PBKDF2-SHA256 + Bearer Token
- **Container:** Docker + Compose, Health-Check
- **i18n:** JSON-basiert, erweiterbar

---

## Autor

**S.B.** — Konzept, Entwicklung, Design

---

## KI-Erstellung

Dieses Tool wurde mit Unterstützung von KI erstellt.

### Dank an

- **[opencode](https://opencode.ai)** – KI-gestützte Entwicklungsumgebung
- **Claude** (Anthropic) – Code-Generierung und Architekturberatung
- **Grocy** ([grocy.info](https://grocy.info)) – ERP-System für den Haushalt
- **Buy Me a Pie** ([buymeapie.com](https://buymeapie.com)) – Der mobile Einkaufszettel

---

## Lizenz

MIT — siehe [LICENSE](LICENSE).

Copyright (c) 2026 **S.B.**
