# Grot2Buy

**DE** — Bidirektionale Synchronisation zwischen **Buy Me a Pie**, **Grocy** und lokaler Einkaufsliste.
Grot2Buy führt deine Einkaufslisten-Dienste in einer zentralen Liste zusammen und hält sie konsistent.

**EN** — Bidirectional sync between **Buy Me a Pie**, **Grocy** and a local shopping list.
Grot2Buy merges your shopping list services into one central list and keeps them consistent.

---

## Features

- **Bidirektionaler Sync** – Grocy ↔ Grot2Buy ↔ Buy Me a Pie
- **Bidirectional Sync** – Grocy ↔ Grot2Buy ↔ Buy Me a Pie
- **Auto-Sync** – Konfigurierbares Intervall (Web-UI) | Configurable interval (web UI)
- **PWA** – Installierbar auf iOS/Android-Homescreen (Vollbildmodus)
- **Web-UI** – Responsiv, mobil-optimiert | Responsive, mobile-optimized
- **Mehrsprachig** – Deutsch & Englisch, einfach erweiterbar | German & English, easy to extend
- **Setup-Wizard** – Ersteinrichtung via Browser | Initial setup via browser
- **Docker** – Port 8899, HTTPS inklusive | HTTPS included
- **Verschlüsselt** – AES-256 (Fernet) für ruhende Daten | AES-256 for data at rest

---

## PWA — iOS / Android installieren

**DE**
1. Safari öffnen → `https://<deine-ip>:8899`
2. **Teilen-Button** (Mitte der unteren Leiste)
3. **"Zum Home-Bildschirm"** tippen
4. Name bestätigen → **"Hinzufügen"**
5. App-Icon erscheint auf dem Homescreen – wie eine native App

**EN**
1. Open Safari → `https://<your-ip>:8899`
2. Tap the **Share button** (center of bottom bar)
3. Scroll down → tap **"Add to Home Screen"**
4. Confirm the name → tap **"Add"**
5. The app icon appears on your homescreen – runs in fullscreen like a native app

### Android

Chrome zeigt beim ersten Besuch einen Install-Banner an (oder Menü → "Installieren").
Chrome shows an install banner on first visit (or menu → "Install").

---

## Quick Start

```bash
docker compose up -d
```

**DE** — Danach im Browser öffnen: `https://<server-ip>:8899`
**EN** — Then open in your browser: `https://<server-ip>:8899`

Der Setup-Wizard führt durch die Konfiguration.
The setup wizard guides you through the configuration.

---

## Systemvoraussetzungen / Requirements

- Linux, macOS oder Windows (with Docker Desktop / WSL2)
- Docker + Docker Compose
- 512 MB RAM, 1 GB free disk

---

## Konfiguration / Configuration

Alle Einstellungen werden über die Web-UI vorgenommen.
All settings are managed through the web UI:

| Step | DE | EN |
|------|----|----|
| 1 | Login-Passwort vergeben (erster Aufruf `/setup`) | Set a login password (first visit `/setup`) |
| 2 | Buy Me a Pie (E-Mail + Passwort) | Buy Me a Pie (email + password) |
| 3 | Grocy (Server-URL + API-Key) | Grocy (server URL + API key) |
| 4 | Sync-Intervall (Standard 5 Minuten) | Sync interval (default 5 minutes) |

---

## API (Auswahl / Selection)

| Endpoint | Description |
|----------|-------------|
| `GET /api/sync/full` | Trigger full sync |
| `POST /api/items/add` | Add an item |
| `GET /api/synced/items` | Synced list as JSON |
| `GET /health` | Status ping |

Vollständige API-Dokumentation: [DOKU.md](DOKU.md)
Full API documentation: [DOKU.md](DOKU.md)

---

## Technik / Tech Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn
- **Frontend:** Vanilla JS, CSS3 (no framework)
- **Verschlüsselung / Encryption:** Fernet (AES-256-CBC)
- **Authentifizierung / Auth:** PBKDF2-SHA256 + Bearer Token
- **Container:** Docker + Compose, Health-Check
- **i18n:** JSON-basiert, erweiterbar | JSON-based, extensible

---

## Autor / Author

**S.B.** — Konzept, Entwicklung, Design | Concept, development, design

---

## KI-Erstellung / AI Assistance

Dieses Tool wurde mit Unterstützung von KI erstellt.
This tool was created with AI assistance.

### Dank an / Thanks to

- **[opencode](https://opencode.ai)** – KI-gestützte Entwicklungsumgebung | AI-powered development environment
- **Claude** (Anthropic) – Code-Generierung und Architekturberatung | Code generation & architecture guidance
- **Grocy** ([grocy.info](https://grocy.info)) – ERP-System für den Haushalt | Household ERP system
- **Buy Me a Pie** ([buymeapie.com](https://buymeapie.com)) – Der mobile Einkaufszettel | The mobile shopping list

---

## Lizenz / License

MIT — siehe [LICENSE](LICENSE) | see [LICENSE](LICENSE).

Copyright (c) 2026 **S.B.**
