# Grot2Buy

> Bidirektionale Synchronisation zwischen **Buy Me a Pie**, **Grocy** und lokaler Einkaufsliste.

Grot2Buy verbindet deine Einkaufslisten-Dienste zu einer zentralen Liste. Änderungen in
einer Quelle werden automatisch in die anderen propagiert – **wer geändert hat, gewinnt**.

## PWA (iOS / Android)

Grot2Buy ist eine **Progressive Web App** – auf dem Homescreen installierbar,
läuft im Vollbildmodus ohne Browser-Chrome.

### iOS installieren

1. Safari öffnen → `https://<deine-ip>:8899`
2. **Teilen-Button** (Mitte der unteren Leiste)
3. **"Zum Home-Bildschirm"** tippen
4. Name bestätigen → **"Hinzufügen"**
5. App-Icon erscheint auf dem Homescreen – wie eine native App

### Android installieren

Chrome zeigt beim ersten Besuch einen Install-Banner an,
oder via Menü → "Installieren".

---

## Features

- **Bidirektionaler Sync** – Grocy ↔ Grot2Buy ↔ Buy Me a Pie
- **Auto-Sync** – konfigurierbares Intervall (Web-UI)
- **Web-UI** – responsive, mobil-optimiert
- **Mehrsprachig** – Deutsch & Englisch, einfach erweiterbar
- **Setup-Wizard** – Ersteinrichtung via Browser
- **Docker** – Port 8899, HTTPS inklusive
- **Verschlüsselt** – AES-256 (Fernet) für ruhende Daten

## Quick Start

```bash
docker compose up -d
```

Danach im Browser öffnen: `https://<server-ip>:8899`

Der Setup-Wizard führt durch die Konfiguration von Buy Me a Pie und Grocy.

## Systemvoraussetzungen

- Linux, macOS oder Windows (mit Docker Desktop / WSL2)
- Docker + Docker Compose
- 512 MB RAM, 1 GB frei Platte

## Konfiguration

Alle Einstellungen werden über die Web-UI vorgenommen:

| Schritt | Beschreibung |
|---------|-------------|
| 1. Login-Passwort vergeben | Erster Aufruf von `/setup` |
| 2. Buy Me a Pie | E-Mail + Passwort |
| 3. Grocy | Server-URL + API-Key |
| 4. Sync-Intervall | Standard 5 Minuten |

## API (Auswahl)

| Endpunkt | Beschreibung |
|----------|-------------|
| `GET /api/sync/full` | Vollständigen Sync auslösen |
| `POST /api/items/add` | Artikel hinzufügen |
| `GET /api/synced/items` | Synced-Liste als JSON |
| `GET /health` | Status-Ping |

Vollständige API-Dokumentation: [DOKU.md](DOKU.md)

## Technik

- **Backend:** Python 3.12, FastAPI, Uvicorn
- **Frontend:** Vanilla JS, CSS3 (kein Framework)
- **Verschlüsselung:** Fernet (AES-256-CBC)
- **Authentifizierung:** PBKDF2-SHA256 + Bearer-Token
- **Container:** Docker + Compose, Health-Check

## Autor

**S.B.** — Konzept, Entwicklung, Design

## KI-Erstellung

Dieses Tool wurde mit Unterstützung von KI erstellt.

### Dank an

- **[opencode](https://opencode.ai)** – KI-gestützte Entwicklungsumgebung
- **Claude** (Anthropic) – Code-Generierung und Architekturberatung
- Allen beteiligten KI-Systemen, die bei der Umsetzung geholfen haben
- **Grocy** ([grocy.info](https://grocy.info)) – Das ERP-System für den Haushalt
- **Buy Me a Pie** ([buymeapie.com](https://buymeapie.com)) – Der mobile Einkaufszettel

## Lizenz

MIT — siehe [LICENSE](LICENSE).

Copyright (c) 2026 **S.B.** — Bei Verwendung oder Weiterentwicklung wird eine
Namensnennung („S.B.") erbeten.
