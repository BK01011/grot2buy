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
