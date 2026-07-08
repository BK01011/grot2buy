"""Grot2Buy — Bidirektionale Einkaufslisten-Synchronisation.

Buy Me a Pie ↔ Grocy ↔ Lokale Liste.
Autor: S.B.
Lizenz: MIT
Erstellt mit KI-Unterstützung (opencode, Claude).
"""
import json
import secrets
import hashlib
import logging
import re
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime

VERSION = "0.2.4"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("shopping")

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
import httpx

from modules.config import config, DATA_DIR, encrypt
from modules.shopping import shopping_manager
from modules.shopping_sync import shopping_sync
from modules.buymeapie import create_client

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Barcode-Kategorie-Zuordnung (EAN-Präfixe)
BARCODE_CATEGORIES = {
    "400": "Getränke", "401": "Milchprodukte", "403": "Süßigkeiten",
    "500": "Obst & Gemüse", "690": "Asia-Produkte", "80": "Italien",
    "30": "Frankreich", "00": "USA", "84": "Spanien",
}

DEFAULT_CATEGORIES = [
    "Obst & Gemüse", "Milchprodukte", "Fleisch & Wurst",
    "Getränke", "Brot & Gebäck", "Vorrat",
    "Tiefkühl", "Süßigkeiten", "Drogerie", "Sonstiges"
]


def categorize_barcode(barcode: str) -> str:
    """Ordnet einen Barcode einer Kategorie zu."""
    if not barcode or not barcode.isdigit():
        return "Sonstiges"
    prefix = barcode[:3]
    return BARCODE_CATEGORIES.get(prefix, "Sonstiges")


def parse_barcode_input(text: str) -> tuple[str, str]:
    """Parst Eingabe mit optionalem Barcode: 'Artikelname [1234567890123]' oder '1234567890123'."""
    match = re.search(r'\[(\d{8,14})\]', text)
    if match:
        name = text[:match.start()].strip()
        return name, match.group(1)
    if text.strip().isdigit() and 8 <= len(text.strip()) <= 14:
        return "", text.strip()
    return text.strip(), ""


# Passwort-Hashing (PBKDF2-SHA256)
PBKDF2_ITERATIONS = 600_000

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"{salt}${h.hex()}"

def verify_password(password: str, stored: str) -> bool:
    if '$' not in stored:
        return secrets.compare_digest(password, stored)
    salt, h = stored.split('$', 1)
    return secrets.compare_digest(
        hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex(),
        h
    )

# Token-Verifikation
def verify_token(request: Request) -> bool:
    # Kein Passwort gesetzt → Zugang erlauben
    if not config.get_decrypted("password", ""):
        return True
    token = request.cookies.get("auth_token")
    if token and config.validate_token(token):
        return True
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return config.validate_token(auth_header[7:])
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🛒 Grot2Buy startet...")
    # BAP-Verbindung herstellen
    bap_user = config.get_decrypted("bap_user", "")
    bap_pass = config.get_decrypted("bap_pass", "")
    if bap_user and bap_pass:
        shopping_manager.configure_buymeapie(bap_user, bap_pass)
        logger.info(f"✅ Buy Me a Pie verbunden als {bap_user}")
    else:
        logger.info("⚠️ Keine BAP-Zugangsdaten — lokaler Modus")
    # Grocy-Verbindung herstellen
    grocy_url = config.get_decrypted("grocy_url", "") or config.get("grocy_url", "")
    grocy_key = config.get_decrypted("grocy_key", "") or config.get("grocy_key", "")
    if grocy_url and grocy_key:
        result = shopping_manager.configure_grocy(grocy_url, grocy_key)
        if result:
            logger.info(f"✅ Grocy verbunden: {grocy_url}")
        else:
            logger.warning(f"❌ Grocy Verbindung fehlgeschlagen: {grocy_url}")
    else:
        logger.info("⚠️ Keine Grocy-Zugangsdaten")
    # Hintergrund-Sync starten
    sync_task = asyncio.create_task(_background_sync())
    yield
    sync_task.cancel()
    logger.info("👋 Server beendet.")


async def _background_sync():
    """Hintergrund-Sync-Task — läuft im konfigurierten Intervall."""
    while True:
        try:
            interval = config.get("sync_interval", 5)
            if interval and interval > 0:
                await asyncio.sleep(interval * 60)
                bap_user = config.get_decrypted("bap_user", "")
                bap_pass = config.get_decrypted("bap_pass", "")
                bap_client = create_client(bap_user, bap_pass) if bap_user and bap_pass else None
                grocy = shopping_manager._grocy
                if grocy or bap_client:
                    result = shopping_sync.sync_full(grocy, bap_client)
                    logger.info(f"🔄 Auto-Sync: {result}")
            else:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Auto-Sync Fehler: {e}")
            await asyncio.sleep(60)


app = FastAPI(title="Grot2Buy", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# ─── Seiten ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, _: bool = Depends(verify_token)):
    # Bei Neuinstallation Setup-Seite anzeigen
    if not config.get("setup_complete", False):
        return RedirectResponse("/setup", status_code=303)
    return templates.TemplateResponse(request, "shopping.html")


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    # Bei abgeschlossenem Setup zur Hauptseite weiterleiten
    if config.get("setup_complete", False):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "setup.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Kein Passwort gesetzt → direkt weiterleiten
    if not config.get_decrypted("password", ""):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html")


@app.post("/login")
async def login_submit(request: Request, password: str = Form("")):
    stored_pass = config.get_decrypted("password", "")
    if stored_pass and verify_password(password, stored_pass):
        token = secrets.token_urlsafe(32)
        config.set_auth_token(token)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie("auth_token", token, httponly=True, secure=True, samesite="strict", max_age=86400 * 30)
        return response
    return templates.TemplateResponse(request, "login.html", {
        "error": "Falsches Passwort"
    })


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("auth_token")
    return response


# ─── Setup ─────────────────────────────────────────────────────

@app.post("/setup")
async def setup(
    request: Request,
    password: str = Form(""),
    bap_user: str = Form(""),
    bap_pass: str = Form(""),
    grocy_url: str = Form(""),
    grocy_key: str = Form(""),
):
    config.set("password", hash_password(password) if password else "")
    config.set_encrypted("bap_user", bap_user)
    config.set_encrypted("bap_pass", bap_pass)
    config.set("grocy_url", grocy_url)
    config.set("grocy_key", grocy_key)
    config.set("setup_complete", True)

    if bap_user and bap_pass:
        shopping_manager.configure_buymeapie(bap_user, bap_pass)
    
    if grocy_url and grocy_key:
        shopping_manager.configure_grocy(grocy_url, grocy_key)

    token = secrets.token_urlsafe(32)
    config.set_auth_token(token)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("auth_token", token, httponly=True, secure=True, samesite="strict", max_age=86400 * 30)
    return response


# ─── API: Listen ────────────────────────────────────────────────

@app.get("/api/lists")
async def api_lists(_: bool = Depends(verify_token)):
    """Zeigt alle BAP-Listen."""
    try:
        bap_user = config.get_decrypted("bap_user", "")
        bap_pass = config.get_decrypted("bap_pass", "")
        if not bap_user or not bap_pass:
            return JSONResponse({"lists": [], "error": "Keine BAP-Zugangsdaten"})

        client = create_client(bap_user, bap_pass)
        if not client:
            return JSONResponse({"lists": [], "error": "BAP-Verbindung fehlgeschlagen"})

        lists = client.get_lists()
        result = []
        for lst in lists:
            items = client.get_active_items(lst.get("id"))
            result.append({
                "id": lst.get("id"),
                "name": lst.get("name"),
                "count": len(items),
                "purchased_count": lst.get("items_purchased", 0),
            })
        return JSONResponse({"lists": result})
    except Exception as e:
        logger.error(f"Listen-Fehler: {e}")
        return JSONResponse({"lists": [], "error": str(e)})


@app.get("/api/lists/{list_id}/items")
async def api_list_items(list_id: str, _: bool = Depends(verify_token)):
    """Zeigt Artikel einer bestimmten BAP-Liste."""
    try:
        bap_user = config.get_decrypted("bap_user", "")
        bap_pass = config.get_decrypted("bap_pass", "")
        if not bap_user or not bap_pass:
            return JSONResponse({"items": [], "error": "Keine BAP-Zugangsdaten"})

        client = create_client(bap_user, bap_pass)
        if not client:
            return JSONResponse({"items": [], "error": "BAP-Verbindung fehlgeschlagen"})

        items = client.get_active_items(list_id)
        result = []
        for item in items:
            qty_str = item.get("amount", "")
            qty = 1
            if qty_str and "x" in qty_str.lower():
                try:
                    qty = int(qty_str.lower().replace("x", "").strip())
                except ValueError:
                    qty = 1

            result.append({
                "id": item.get("id"),
                "title": item.get("title", ""),
                "quantity": qty,
                "amount": qty_str,
                "is_purchased": item.get("is_purchased", False),
            })
        return JSONResponse({"items": result, "list_id": list_id})
    except Exception as e:
        logger.error(f"Artikel-Fehler: {e}")
        return JSONResponse({"items": [], "error": str(e)})


# ─── API: Artikel verwalten ────────────────────────────────────

@app.post("/api/items/add")
async def api_add_item(request: Request, _: bool = Depends(verify_token)):
    """Fügt einen Artikel hinzu — mit optionalem Barcode."""
    body = await request.json()
    name = body.get("name", "").strip()
    quantity = body.get("quantity", 1)
    category = body.get("category", "")
    list_id = body.get("list_id")
    barcode = body.get("barcode", "")

    # Barcode-Eingabe parsen
    if not name and barcode:
        parsed_name, parsed_barcode = parse_barcode_input(barcode)
        if parsed_barcode:
            barcode = parsed_barcode
        name = parsed_name

    if not name:
        return JSONResponse({"error": "Name erforderlich"}, status_code=400)

    # Barcode-Kategorie zuordnen
    if barcode and not category:
        category = categorize_barcode(barcode)

    # Zur synchronisierten Liste hinzufügen
    result = shopping_sync.add_item(name, quantity, category)
    logger.info(f"➕ Hinzugefügt: {name} (x{quantity}, {category}, Barcode: {barcode or 'keiner'})")

    return JSONResponse({
        "result": result,
        "name": name,
        "quantity": quantity,
        "category": category,
        "barcode": barcode,
    })


@app.post("/api/items/add-bulk")
async def api_add_items_bulk(request: Request, _: bool = Depends(verify_token)):
    """Fügt mehrere Artikel hinzu (CSV-Format oder JSON-Array)."""
    body = await request.json()
    items_text = body.get("items", "")
    list_id = body.get("list_id")

    added = 0
    skipped = 0
    errors = []

    if isinstance(items_text, str):
        lines = [l.strip() for l in items_text.split("\n") if l.strip()]
    elif isinstance(items_text, list):
        lines = [item.get("name", item) if isinstance(item, dict) else str(item) for item in items_text]
    else:
        return JSONResponse({"error": "Ungültiges Format"}, status_code=400)

    for line in lines:
        name, barcode = parse_barcode_input(line)
        if not name and barcode:
            name = f"Artikel {barcode[-4:]}"
        if not name:
            skipped += 1
            continue

        category = categorize_barcode(barcode) if barcode else ""
        result = shopping_sync.add_item(name, 1, category)
        if "hinzugefügt" in result or "aktualisiert" in result:
            added += 1
        else:
            skipped += 1

    return JSONResponse({
        "added": added,
        "skipped": skipped,
        "total": len(lines),
    })


@app.post("/api/items/{item_name}/remove")
async def api_remove_item(item_name: str, _: bool = Depends(verify_token)):
    """Entfernt einen Artikel — auch aus BAP und Grocy."""
    bap_user = config.get_decrypted("bap_user", "")
    bap_pass = config.get_decrypted("bap_pass", "")
    bap_client = create_client(bap_user, bap_pass) if bap_user and bap_pass else None
    grocy_client = shopping_manager._grocy if shopping_manager._grocy else None
    result = shopping_sync.remove_item(item_name, bap_client=bap_client, grocy_client=grocy_client)
    logger.info(f"🗑️ Entfernt: {item_name}")
    return JSONResponse({"result": result})


@app.post("/api/items/{item_name}/purchased")
async def api_mark_purchased(item_name: str, _: bool = Depends(verify_token)):
    """Markiert einen Artikel als gekauft — auch in BAP und Grocy."""
    bap_user = config.get_decrypted("bap_user", "")
    bap_pass = config.get_decrypted("bap_pass", "")
    bap_client = create_client(bap_user, bap_pass) if bap_user and bap_pass else None
    grocy_url = config.get_decrypted("grocy_url", "") or config.get("grocy_url", "")
    grocy_key = config.get_decrypted("grocy_key", "") or config.get("grocy_key", "")
    grocy_client = shopping_manager._grocy if shopping_manager._grocy else None
    if not grocy_client and grocy_url and grocy_key:
        from modules.shopping import GrocyClient
        grocy_client = GrocyClient(grocy_url, grocy_key)
    logger.info(f"🛒 Kauf-Anfrage für '{item_name}' — BAP Client: {bap_client is not None}, Grocy Client: {grocy_client is not None}")
    result = shopping_sync.mark_purchased(item_name, bap_client=bap_client, grocy_client=grocy_client)
    logger.info(f"✅ Erledigt: {item_name} → {result}")
    return JSONResponse({"result": result})


@app.post("/api/items/{item_name}/quantity")
async def api_update_quantity(item_name: str, request: Request, _: bool = Depends(verify_token)):
    """Aktualisiert die Menge eines Artikels."""
    body = await request.json()
    quantity = body.get("quantity", 1)
    shopping_sync.update_quantity(item_name, quantity)
    logger.info(f"🔄 Menge aktualisiert: {item_name} → x{quantity}")
    return JSONResponse({"result": f"Menge für '{item_name}' auf x{quantity} aktualisiert."})


@app.post("/api/items/clear-purchased")
async def api_clear_purchased(_: bool = Depends(verify_token)):
    """Entfernt alle gekauften Artikel."""
    shopping_sync.clear_purchased()
    logger.info("🧹 Kaufte Artikel bereinigt")
    return JSONResponse({"result": "Alle gekauften Artikel entfernt."})


# ─── API: BAP-Synchronisation ──────────────────────────────────

@app.get("/api/sync/push")
async def api_sync_push(_: bool = Depends(verify_token)):
    """Pushed synced items zu BAP."""
    try:
        bap_user = config.get_decrypted("bap_user", "")
        bap_pass = config.get_decrypted("bap_pass", "")
        if not bap_user or not bap_pass:
            return JSONResponse({"result": "Keine BAP-Zugangsdaten"})

        client = create_client(bap_user, bap_pass)
        if not client:
            return JSONResponse({"result": "BAP-Verbindung fehlgeschlagen"})

        result = shopping_sync.push_to_buymeapie(client)
        logger.info(f"📤 BAP-Push: {result}")
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"BAP-Push-Fehler: {e}")
        return JSONResponse({"result": f"Fehler: {e}"})


@app.get("/api/sync/pull")
async def api_sync_pull(_: bool = Depends(verify_token)):
    """Holt gekaufte Artikel aus BAP und markiert sie in Grocy als erledigt."""
    try:
        bap_user = config.get_decrypted("bap_user", "")
        bap_pass = config.get_decrypted("bap_pass", "")
        if not bap_user or not bap_pass:
            return JSONResponse({"result": "Keine BAP-Zugangsdaten"})

        client = create_client(bap_user, bap_pass)
        if not client:
            return JSONResponse({"result": "BAP-Verbindung fehlgeschlagen"})

        grocy = shopping_manager._grocy
        result = shopping_sync.pull_purchased_from_bap(client, grocy)
        logger.info(f"📥 BAP-Pull: {result}")
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"BAP-Pull-Fehler: {e}")
        return JSONResponse({"result": f"Fehler: {e}"})


@app.get("/api/sync/full")
async def api_sync_full(_: bool = Depends(verify_token)):
    """Vollständige bidirektionale Synchronisation Grocy ↔ BAP ↔ Lokal."""
    try:
        bap_user = config.get_decrypted("bap_user", "")
        bap_pass = config.get_decrypted("bap_pass", "")
        client = None
        if bap_user and bap_pass:
            client = create_client(bap_user, bap_pass)

        grocy = shopping_manager._grocy

        if grocy and client:
            result = shopping_sync.sync_full(grocy, client)
        elif client:
            result = shopping_sync.push_to_buymeapie(client)
        elif grocy:
            result = shopping_sync.get_merged_text()
        else:
            result = "⚠️ Keine Verbindung konfiguriert"

        logger.info(f"🔄 Vollsync: {result}")
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"Vollsync-Fehler: {e}")
        return JSONResponse({"result": f"Fehler: {e}"})


@app.get("/api/sync/grocy")
async def api_sync_grocy(_: bool = Depends(verify_token)):
    """Zeigt Grocy-Einkaufsliste."""
    grocy = shopping_manager._grocy
    if not grocy:
        return JSONResponse({"result": "⚠️ Keine Grocy-Verbindung", "items": []})
    items = grocy.get_shopping_list()
    result = []
    for item in items:
        name = item.get("product", {}).get("name", item.get("note", ""))
        qty = item.get("amount", 1)
        result.append({"id": item.get("id"), "name": name, "quantity": qty})
    return JSONResponse({"items": result, "count": len(result)})


@app.get("/api/sync/grocy/push")
async def api_sync_grocy_push(_: bool = Depends(verify_token)):
    """Pushed lokale/gedeckte Artikel zu Grocy."""
    grocy = shopping_manager._grocy
    if not grocy:
        return JSONResponse({"result": "⚠️ Keine Grocy-Verbindung"})
    try:
        result = shopping_sync.push_to_grocy(grocy)
        logger.info(f"📤 Grocy-Push: {result}")
        return JSONResponse({"result": result})
    except Exception as e:
        return JSONResponse({"result": f"Fehler: {e}"})


@app.get("/api/sync/grocy/pull")
async def api_sync_grocy_pull(_: bool = Depends(verify_token)):
    """Holt Artikel aus Grocy in die synced-Liste."""
    grocy = shopping_manager._grocy
    if not grocy:
        return JSONResponse({"result": "⚠️ Keine Grocy-Verbindung"})
    try:
        items = grocy.get_shopping_list()
        added = 0
        for item in items:
            name = item.get("product", {}).get("name", item.get("note", ""))
            qty = item.get("amount", 1)
            if name:
                shopping_sync.add_item(name, qty, "", source="grocy")
                added += 1
        result = f"✅ {added} Artikel aus Grocy geholt."
        logger.info(f"📥 Grocy-Pull: {result}")
        return JSONResponse({"result": result})
    except Exception as e:
        return JSONResponse({"result": f"Fehler: {e}"})


# ─── API: Daten ────────────────────────────────────────────────

@app.get("/api/synced")
async def api_synced(_: bool = Depends(verify_token)):
    """Zeigt die synchronisierte Liste."""
    return JSONResponse({"text": shopping_sync.get_merged_text()})


@app.get("/api/synced/items")
async def api_synced_items(_: bool = Depends(verify_token)):
    """Gibt die synchronisierte Liste als JSON-Array zurück."""
    active = [i for i in shopping_sync._synced_items if not i.get("purchased")]
    by_category = {}
    for item in active:
        cat = item.get("category", "") or "Sonstiges"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)
    return JSONResponse({"items": active, "by_category": by_category, "count": len(active)})


@app.post("/api/synced/reset")
async def api_synced_reset(_: bool = Depends(verify_token)):
    """Setzt die synced_liste zurück und synchronisiert neu."""
    shopping_sync._synced_items = []
    shopping_sync._removed = []
    shopping_sync.save()
    result = shopping_sync.sync_full(shopping_manager._grocy, shopping_manager._bap)
    return JSONResponse({"result": result, "count": len(shopping_sync._synced_items)})


@app.get("/api/export")
async def api_export(_: bool = Depends(verify_token)):
    """Exportiert die Liste für Buy Me a Pie."""
    export = shopping_sync.export_for_buymeapie()
    return JSONResponse({"export": export, "count": len(export.splitlines()) if export else 0})


@app.get("/api/categories")
async def api_categories(_: bool = Depends(verify_token)):
    """Gibt die verfügbaren Kategorien zurück."""
    return JSONResponse({"categories": DEFAULT_CATEGORIES})


# ─── API: Konfiguration ───────────────────────────────────────

@app.get("/api/config")
async def api_config_get(_: bool = Depends(verify_token)):
    """Gibt die aktuelle Konfiguration zurück."""
    return JSONResponse({
        "bap_user": config.get_decrypted("bap_user", ""),
        "bap_list_name": config.get("bap_list_name", "Einkaufsliste"),
        "has_password": bool(config.get_decrypted("password", "")),
        "sync_interval": config.get("sync_interval", 5),
    })


@app.post("/api/config/bap")
async def api_config_bap(request: Request, _: bool = Depends(verify_token)):
    """Aktualisiert die BAP-Zugangsdaten."""
    body = await request.json()
    bap_user = body.get("bap_user", "")
    bap_pass = body.get("bap_pass", "")

    config.set_encrypted("bap_user", bap_user)
    config.set_encrypted("bap_pass", bap_pass)

    if bap_user and bap_pass:
        shopping_manager.configure_buymeapie(bap_user, bap_pass)

    return JSONResponse({"result": "BAP-Zugangsdaten aktualisiert."})


@app.get("/api/config/sync-interval")
async def api_get_sync_interval(_: bool = Depends(verify_token)):
    """Gibt das aktuelle Sync-Intervall zurück."""
    interval = config.get("sync_interval", 5)
    return JSONResponse({"interval": interval})


@app.post("/api/config/sync-interval")
async def api_set_sync_interval(request: Request, _: bool = Depends(verify_token)):
    """Setzt das Sync-Intervall in Minuten (0 = deaktiviert)."""
    body = await request.json()
    interval = body.get("interval", 5)
    if not isinstance(interval, (int, float)) or interval < 0:
        return JSONResponse({"error": "Ungültiges Intervall"}, status_code=400)
    config.set("sync_interval", int(interval))
    status = f"alle {interval} Minuten" if interval > 0 else "deaktiviert"
    return JSONResponse({"result": f"Auto-Sync: {status}", "interval": int(interval)})


@app.get("/api/config/export")
async def api_config_export(_: bool = Depends(verify_token)):
    """Exportiert die Konfiguration (sicher, ohne secret.key)."""
    safe_config = {k: v for k, v in config._data.items() if k not in ("auth_token",)}
    return JSONResponse({
        "config": safe_config,
        "has_secret_key": (DATA_DIR / "secret.key").exists(),
    })


@app.post("/api/config/import")
async def api_config_import(request: Request, _: bool = Depends(verify_token)):
    """Importiert eine Konfiguration."""
    body = await request.json()
    config_data = body.get("config", {})
    secret_key = body.get("secret_key", "")

    if config_data:
        config._data.update(config_data)
        config.save()

    if secret_key:
        (DATA_DIR / "secret.key").write_text(secret_key)

    return JSONResponse({"result": "Konfiguration importiert."})


# ─── API: System ───────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "grot2buy", "version": VERSION}


@app.get("/api/system/status")
async def api_system_status(_: bool = Depends(verify_token)):
    return JSONResponse({
        "status": "running",
        "version": VERSION,
        "backend": shopping_manager.backend,
        "timestamp": datetime.now().isoformat(),
    })


# ─── API: Downloads ─────────────────────────────────────────────

@app.get("/api/docs/doku")
async def download_doku():
    return FileResponse("DOKU.md", media_type="text/markdown", filename="DOKU.md")


@app.get("/api/docs/changelog")
async def download_changelog():
    return FileResponse("CHANGELOG.md", media_type="text/markdown", filename="CHANGELOG.md")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.server_port)
