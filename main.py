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
import asyncio
from json import JSONDecodeError
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
from datetime import datetime, timezone

VERSION = "0.6.0"

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
from starlette.exceptions import HTTPException as StarletteHTTPException
from modules.config import config
from modules.shopping import shopping_manager
from modules.shopping_sync import shopping_sync
from modules.buymeapie import BuyMeAPieClient
from modules.i18n import t as i18n_t, flattened as i18n_flat, AVAILABLE_LANGUAGES, reload as reload_i18n

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def template_context(request: Request, extra: dict = None) -> dict:
    lang = config.get("lang", "de")
    if lang not in AVAILABLE_LANGUAGES:
        lang = "de"
    ctx = {
        "request": request,
        "t": lambda key, **kw: i18n_t(key, lang, **kw),
        "lang": lang,
        "langs": AVAILABLE_LANGUAGES,
        "t_flat": i18n_flat(lang),
        "version": VERSION,
    }
    if extra:
        ctx.update(extra)
    return ctx

DEFAULT_CATEGORIES = [
    "Obst & Gemüse", "Milchprodukte", "Fleisch & Wurst",
    "Getränke", "Brot & Gebäck", "Vorrat",
    "Tiefkühl", "Süßigkeiten", "Drogerie", "Sonstiges"
]

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


def verify_token(request: Request) -> bool:
    if not config.get_decrypted("password", ""):
        return True
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        if config.validate_token(auth_header[7:]):
            return True
    token = request.cookies.get("auth_token")
    if token and config.validate_token(token):
        return True
    raise HTTPException(status_code=401, detail="Unauthorized")


async def parse_json_body(request: Request) -> dict:
    try:
        return await request.json()
    except JSONDecodeError:
        raise HTTPException(status_code=400, detail="Ungültiges JSON-Format")


def _set_auth_cookie(response, token: str):
    is_https = config.get("server_port", 8899) == 443
    response.set_cookie(
        "auth_token", token,
        httponly=True,
        secure=is_https,
        samesite="lax",
        max_age=86400 * 30
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Grot2Buy startet...")
    bap_user = config.get_decrypted("bap_user", "")
    bap_pass = config.get_decrypted("bap_pass", "")
    if bap_user and bap_pass:
        shopping_manager.configure_buymeapie(bap_user, bap_pass)
        logger.info(f"Buy Me a Pie verbunden als {bap_user}")
    else:
        logger.info("Keine BAP-Zugangsdaten — lokaler Modus")
    grocy_url = config.get_decrypted("grocy_url", "") or config.get("grocy_url", "")
    grocy_key = config.get_decrypted("grocy_key", "") or config.get("grocy_key", "")
    if grocy_url and grocy_key:
        result = shopping_manager.configure_grocy(grocy_url, grocy_key)
        if result:
            logger.info(f"Grocy verbunden: {grocy_url}")
        else:
            logger.warning(f"Grocy Verbindung fehlgeschlagen: {grocy_url}")
    else:
        logger.info("Keine Grocy-Zugangsdaten")
    sync_task = asyncio.create_task(_background_sync())
    yield
    sync_task.cancel()
    if shopping_manager._bap:
        shopping_manager._bap.close()
    if shopping_manager._grocy:
        shopping_manager._grocy.close()
    logger.info("Server beendet.")


async def _background_sync():
    while True:
        try:
            interval = config.get("sync_interval", 5)
            if interval and interval > 0:
                await asyncio.sleep(interval * 60)
                bap_client = shopping_manager._bap
                grocy = shopping_manager._grocy
                if grocy or bap_client:
                    result = await shopping_sync.sync_full(grocy, bap_client)
                    logger.info(f"Auto-Sync: {result}")
            else:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Auto-Sync Fehler: {e}")
            await asyncio.sleep(60)


app = FastAPI(title="Grot2Buy", lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        {"detail": exc.detail},
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    logger.error(f"Unerwarteter Fehler: {exc}")
    return JSONResponse(
        {"detail": "Ein interner Fehler ist aufgetreten."},
        status_code=500,
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# ─── Seiten ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, _: bool = Depends(verify_token)):
    if not config.get("setup_complete", False):
        return RedirectResponse("/setup", status_code=303)
    return templates.TemplateResponse(request, "shopping.html", template_context(request))


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    if config.get("setup_complete", False):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "setup.html", template_context(request))


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if not config.get_decrypted("password", ""):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", template_context(request))


@app.post("/login")
async def login_submit(request: Request, password: str = Form("")):
    stored_pass = config.get_decrypted("password", "")
    if stored_pass and verify_password(password, stored_pass):
        token = secrets.token_urlsafe(32)
        config.set_auth_token(token)
        response = RedirectResponse("/", status_code=303)
        _set_auth_cookie(response, token)
        return response
    return templates.TemplateResponse(request, "login.html", template_context(request, {
        "error": i18n_t("login.error", config.get("lang", "de"))
    }))


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
    lang: str = Form("de"),
):
    config.set("lang", lang if lang in AVAILABLE_LANGUAGES else "de")
    config.set("password", hash_password(password) if password else "")
    config.set_encrypted("bap_user", bap_user)
    config.set_encrypted("bap_pass", bap_pass)
    config.set_encrypted("grocy_url", grocy_url)
    config.set_encrypted("grocy_key", grocy_key)
    config.set("setup_complete", True)

    if bap_user and bap_pass:
        shopping_manager.configure_buymeapie(bap_user, bap_pass)

    if grocy_url and grocy_key:
        shopping_manager.configure_grocy(grocy_url, grocy_key)

    token = secrets.token_urlsafe(32)
    config.set_auth_token(token)
    response = RedirectResponse("/", status_code=303)
    _set_auth_cookie(response, token)
    return response


# ─── API: Listen ────────────────────────────────────────────────

def _ensure_bap_client() -> Optional[BuyMeAPieClient]:
    if shopping_manager._bap:
        return shopping_manager._bap
    bap_user = config.get_decrypted("bap_user", "")
    bap_pass = config.get_decrypted("bap_pass", "")
    if bap_user and bap_pass:
        shopping_manager.configure_buymeapie(bap_user, bap_pass)
        return shopping_manager._bap
    return None


@app.get("/api/lists")
async def api_lists(_: bool = Depends(verify_token)):
    synced_count = 0
    try:
        synced_count = len([i for i in shopping_sync._synced_items if not i.get("purchased")])
    except Exception as e:
        logger.debug(f"synced_count Fehler: {e}")

    grocy_count = 0
    try:
        if shopping_manager._grocy:
            grocy_count = len(shopping_manager._grocy.get_shopping_list())
    except Exception as e:
        logger.debug(f"grocy_count Fehler: {e}")

    try:
        client = _ensure_bap_client()
        if not client:
            return JSONResponse({"lists": [], "synced_count": synced_count, "grocy_count": grocy_count})

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
        return JSONResponse({"lists": result, "synced_count": synced_count, "grocy_count": grocy_count})
    except Exception as e:
        logger.error(f"Listen-Fehler: {e}")
        return JSONResponse({"lists": [], "synced_count": synced_count, "grocy_count": grocy_count, "error": "Fehler beim Laden der Listen"})


@app.get("/api/lists/{list_id}/items")
async def api_list_items(list_id: str, _: bool = Depends(verify_token)):
    try:
        client = _ensure_bap_client()
        if not client:
            return JSONResponse({"items": [], "error": "Keine BAP-Verbindung"})

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
        return JSONResponse({"items": [], "error": "Fehler beim Laden der Artikel"})


# ─── API: Artikel verwalten ────────────────────────────────────

@app.post("/api/items/add")
async def api_add_item(request: Request, _: bool = Depends(verify_token)):
    body = await parse_json_body(request)
    name = body.get("name", "").strip()
    quantity = body.get("quantity", 1)
    category = body.get("category", "")

    if not name:
        return JSONResponse({"error": "Name erforderlich"}, status_code=400)

    result = await shopping_sync.add_item(name, quantity, category)
    logger.info(f"Hinzugefügt: {name} (x{quantity}, {category})")

    return JSONResponse({
        "result": result,
        "name": name,
        "quantity": quantity,
        "category": category,
    })


@app.post("/api/items/add-bulk")
async def api_add_items_bulk(request: Request, _: bool = Depends(verify_token)):
    body = await parse_json_body(request)
    items_text = body.get("items", "")

    added = 0
    skipped = 0

    if isinstance(items_text, str):
        lines = [l.strip() for l in items_text.split("\n") if l.strip()]
    elif isinstance(items_text, list):
        lines = [item.get("name", item) if isinstance(item, dict) else str(item) for item in items_text]
    else:
        return JSONResponse({"error": "Ungültiges Format"}, status_code=400)

    for line in lines:
        name = line
        if isinstance(line, dict):
            name = line.get("name", "")
        if not name:
            skipped += 1
            continue

        qty = 1
        if isinstance(line, dict):
            qty = line.get("quantity", 1)
        result = await shopping_sync.add_item(name, qty, "")
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
    bap_client = shopping_manager._bap
    grocy_client = shopping_manager._grocy if shopping_manager._grocy else None
    result = await shopping_sync.remove_item(item_name, bap_client=bap_client, grocy_client=grocy_client)
    logger.info(f"Entfernt: {item_name}")
    return JSONResponse({"result": result})


@app.post("/api/items/{item_name}/purchased")
async def api_mark_purchased(item_name: str, _: bool = Depends(verify_token)):
    bap_client = shopping_manager._bap
    grocy_client = shopping_manager._grocy if shopping_manager._grocy else None
    logger.info(f"Kauf-Anfrage für '{item_name}'")
    result = await shopping_sync.mark_purchased(item_name, bap_client=bap_client, grocy_client=grocy_client)
    logger.info(f"Erledigt: {item_name} → {result}")
    return JSONResponse({"result": result})


@app.post("/api/items/{item_name}/quantity")
async def api_update_quantity(item_name: str, request: Request, _: bool = Depends(verify_token)):
    body = await parse_json_body(request)
    quantity = body.get("quantity", 1)
    await shopping_sync.update_quantity(item_name, quantity)

    if shopping_manager._grocy:
        try:
            grocy_items = shopping_manager._grocy.get_shopping_list()
            for g in grocy_items:
                gname = g.get("product", {}).get("name", "")
                if gname.lower() == item_name.lower():
                    gid = g.get("id")
                    if gid:
                        shopping_manager._grocy.update_shopping_list_item(int(gid), quantity)
                        logger.info(f"  Grocy aktualisiert: {item_name} x{quantity}")
                        break
        except Exception as e:
            logger.warning(f"Grocy-Update fehlgeschlagen: {e}")

    lang = config.get("lang", "de")
    msg = i18n_t("item.updated", lang, name=item_name, qty=str(quantity))
    logger.info(f"Menge aktualisiert: {item_name} → x{quantity}")
    return JSONResponse({"result": msg})


@app.post("/api/items/clear-purchased")
async def api_clear_purchased(_: bool = Depends(verify_token)):
    result = await shopping_sync.clear_purchased()
    logger.info(f"Gekaufte Artikel bereinigt: {result}")
    return JSONResponse({"result": result})


# ─── API: BAP-Synchronisation ──────────────────────────────────

@app.get("/api/sync/push")
async def api_sync_push(_: bool = Depends(verify_token)):
    try:
        client = shopping_manager._bap
        if not client:
            return JSONResponse({"result": "Keine BAP-Verbindung"})
        result = shopping_sync.push_to_buymeapie(client)
        logger.info(f"BAP-Push: {result}")
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"BAP-Push-Fehler: {e}")
        return JSONResponse({"result": "Fehler beim Push-Sync"})


@app.get("/api/sync/pull")
async def api_sync_pull(_: bool = Depends(verify_token)):
    try:
        client = shopping_manager._bap
        if not client:
            return JSONResponse({"result": "Keine BAP-Verbindung"})
        grocy = shopping_manager._grocy
        result = shopping_sync.pull_purchased_from_bap(client, grocy)
        logger.info(f"BAP-Pull: {result}")
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"BAP-Pull-Fehler: {e}")
        return JSONResponse({"result": "Fehler beim Pull-Sync"})


@app.get("/api/sync/full")
async def api_sync_full(_: bool = Depends(verify_token)):
    try:
        bap_client = shopping_manager._bap
        grocy = shopping_manager._grocy

        if bap_client and grocy:
            result = await shopping_sync.sync_full(grocy, bap_client)
        elif bap_client:
            result = shopping_sync.push_to_buymeapie(bap_client)
        elif grocy:
            result = shopping_sync.get_merged_text()
        else:
            result = "Keine Verbindung konfiguriert"

        logger.info(f"Vollsync: {result}")
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"Vollsync-Fehler: {e}")
        return JSONResponse({"result": "Fehler bei der Synchronisation"})


@app.get("/api/sync/grocy")
async def api_sync_grocy(_: bool = Depends(verify_token)):
    grocy = shopping_manager._grocy
    if not grocy:
        return JSONResponse({"result": "Keine Grocy-Verbindung", "items": []})
    items = grocy.get_shopping_list()
    result = []
    for item in items:
        name = item.get("product", {}).get("name", item.get("note", ""))
        qty = item.get("amount", 1)
        result.append({"id": item.get("id"), "name": name, "quantity": qty})
    return JSONResponse({"items": result, "count": len(result)})


@app.get("/api/sync/grocy/push")
async def api_sync_grocy_push(_: bool = Depends(verify_token)):
    grocy = shopping_manager._grocy
    if not grocy:
        return JSONResponse({"result": "Keine Grocy-Verbindung"})
    try:
        result = shopping_sync.push_to_grocy(grocy)
        logger.info(f"Grocy-Push: {result}")
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"Grocy-Push-Fehler: {e}")
        return JSONResponse({"result": "Fehler beim Grocy-Push"})


@app.get("/api/sync/grocy/pull")
async def api_sync_grocy_pull(_: bool = Depends(verify_token)):
    grocy = shopping_manager._grocy
    if not grocy:
        return JSONResponse({"result": "Keine Grocy-Verbindung"})
    try:
        items = grocy.get_shopping_list()
        added = 0
        for item in items:
            name = item.get("product", {}).get("name", item.get("note", ""))
            qty = item.get("amount", 1)
            if name:
                await shopping_sync.add_item(name, qty, "", source="grocy")
                added += 1
        lang = config.get("lang", "de")
        result = i18n_t("sync.pull_success", lang, n=str(added))
        logger.info(f"Grocy-Pull: {result}")
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"Grocy-Pull-Fehler: {e}")
        return JSONResponse({"result": "Fehler beim Grocy-Pull"})


# ─── API: Daten ────────────────────────────────────────────────

@app.get("/api/synced")
async def api_synced(_: bool = Depends(verify_token)):
    return JSONResponse({"text": shopping_sync.get_merged_text()})


@app.get("/api/synced/items")
async def api_synced_items(_: bool = Depends(verify_token)):
    if not shopping_sync._synced_items and (shopping_manager._bap or shopping_manager._grocy):
        logger.info("Synced-Liste leer → initialer Auto-Sync")
        try:
            await shopping_sync.sync_full(shopping_manager._grocy, shopping_manager._bap, is_initial=True)
        except Exception as e:
            logger.error(f"Initialer Sync fehlgeschlagen: {e}")
    all_items = shopping_sync._synced_items[:]
    active = [i for i in all_items if not i.get("purchased")]
    purchased = [i for i in all_items if i.get("purchased")]
    by_category = {}
    for item in active:
        cat = item.get("category", "") or "Sonstiges"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)
    return JSONResponse({
        "items": active,
        "purchased": purchased,
        "by_category": by_category,
        "count": len(active),
        "total": len(all_items),
    })


@app.post("/api/synced/reset")
async def api_synced_reset(_: bool = Depends(verify_token)):
    shopping_sync._synced_items = []
    shopping_sync._removed = []
    shopping_sync.save()
    result = await shopping_sync.sync_full(shopping_manager._grocy, shopping_manager._bap)
    return JSONResponse({"result": result, "count": len(shopping_sync._synced_items)})


@app.get("/api/export")
async def api_export(_: bool = Depends(verify_token)):
    export = shopping_sync.export_for_buymeapie()
    return JSONResponse({"export": export, "count": len(export.splitlines()) if export else 0})


@app.get("/api/categories")
async def api_categories(_: bool = Depends(verify_token)):
    return JSONResponse({"categories": DEFAULT_CATEGORIES})


# ─── API: Konfiguration ───────────────────────────────────────

@app.get("/api/config")
async def api_config_get(_: bool = Depends(verify_token)):
    return JSONResponse({
        "bap_user": config.get_decrypted("bap_user", ""),
        "bap_list_name": config.get("bap_list_name", "Einkaufsliste"),
        "has_password": bool(config.get_decrypted("password", "")),
        "sync_interval": config.get("sync_interval", 5),
        "lang": config.get("lang", "de"),
    })


@app.post("/api/config/bap")
async def api_config_bap(request: Request, _: bool = Depends(verify_token)):
    body = await parse_json_body(request)
    bap_user = body.get("bap_user", "")
    bap_pass = body.get("bap_pass", "")

    config.set_encrypted("bap_user", bap_user)
    config.set_encrypted("bap_pass", bap_pass)

    if bap_user and bap_pass:
        shopping_manager.configure_buymeapie(bap_user, bap_pass)

    lang = config.get("lang", "de")
    return JSONResponse({"result": i18n_t("config.bap_updated", lang)})


@app.get("/api/config/sync-interval")
async def api_get_sync_interval(_: bool = Depends(verify_token)):
    interval = config.get("sync_interval", 5)
    return JSONResponse({"interval": interval})


@app.post("/api/config/sync-interval")
async def api_set_sync_interval(request: Request, _: bool = Depends(verify_token)):
    body = await parse_json_body(request)
    interval = body.get("interval", 5)
    if not isinstance(interval, (int, float)) or interval < 0:
        return JSONResponse({"error": "Ungültiges Intervall"}, status_code=400)
    config.set("sync_interval", int(interval))
    lang = config.get("lang", "de")
    if interval > 0:
        msg = i18n_t("sync.autosync_enabled", lang, minutes=str(int(interval)))
    else:
        msg = i18n_t("sync.autosync_disabled", lang)
    return JSONResponse({"result": msg, "interval": int(interval)})


@app.get("/api/config/lang")
async def api_get_lang(_: bool = Depends(verify_token)):
    lang = config.get("lang", "de")
    return JSONResponse({"lang": lang, "available": AVAILABLE_LANGUAGES})


@app.post("/api/config/lang")
async def api_set_lang(request: Request, _: bool = Depends(verify_token)):
    body = await parse_json_body(request)
    lang = body.get("lang", "de")
    if lang not in AVAILABLE_LANGUAGES:
        return JSONResponse({"success": False, "error": f"Unsupported language: {lang}"}, status_code=400)
    config.set("lang", lang)
    reload_i18n()
    return JSONResponse({"success": True, "lang": lang})


@app.get("/api/config/export")
async def api_config_export(_: bool = Depends(verify_token)):
    REDACTED = "***"
    safe_config = {}
    redacted_keys = {"auth_token", "grocy_key", "grocy_url", "bap_pass", "password", "ai_api_key", "imap_pass", "smtp_pass", "caldav_pass"}
    for k, v in config._data.items():
        if k in redacted_keys:
            safe_config[k] = REDACTED
        elif isinstance(v, dict) and v.get("__encrypted__"):
            safe_config[k] = REDACTED
        else:
            safe_config[k] = v
    return JSONResponse({
        "config": safe_config,
        "has_secret_key": (Path(__file__).parent.parent / "data" / "secret.key").exists(),
    })


@app.post("/api/config/import")
async def api_config_import(request: Request, _: bool = Depends(verify_token)):
    body = await parse_json_body(request)
    config_data = body.get("config", {})

    if isinstance(config_data, dict):
        blocked_keys = {"secret_key", "auth_token", "auth_token_created_at"}
        for k in blocked_keys:
            config_data.pop(k, None)
        config._data.update(config_data)
        config.save()

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
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ─── API: Downloads ─────────────────────────────────────────────

@app.get("/api/docs/doku")
async def download_doku(_: bool = Depends(verify_token)):
    return FileResponse("DOKU.md", media_type="text/markdown", filename="DOKU.md")


@app.get("/api/docs/changelog")
async def download_changelog(_: bool = Depends(verify_token)):
    return FileResponse("CHANGELOG.md", media_type="text/markdown", filename="CHANGELOG.md")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.server_port)
