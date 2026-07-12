"""Grot2Buy — Bidirektionale Einkaufslisten-Synchronisation.

Buy Me a Pie ↔ Grocy ↔ Lokale Liste.
Autor: S.B. — Lizenz: MIT
"""
import json
import re
import secrets
import hashlib
import logging
import asyncio
import time
from json import JSONDecodeError
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import uuid

from fastapi import WebSocket, WebSocketDisconnect

VERSION = "1.0.0"

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "data" / "app.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("shopping")
_file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
_file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S'))
logger.addHandler(_file_handler)

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from modules.config import config, encrypt, decrypt
from modules.shopping import shopping_manager
from modules.shopping_sync import shopping_sync
from modules.buymeapie import BuyMeAPieClient
from modules.i18n import t as i18n_t, flattened as i18n_flat, AVAILABLE_LANGUAGES, reload as reload_i18n

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
    """Passwort mit PBKDF2-HMAC-SHA256 und zufälligem Salt hashen (600k Iterationen)."""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"{salt}${h.hex()}"

def verify_password(password: str, stored: str) -> bool:
    """Passwort gegen einen PBKDF2-Hash prüfen (auch rückwärtskompatibel zu Klartext)."""
    if '$' not in stored:
        return secrets.compare_digest(password, stored)
    salt, h = stored.split('$', 1)
    return secrets.compare_digest(
        hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex(),
        h
    )


def verify_token(request: Request) -> bool:
    """Authentifizierungs-Token prüfen (Bearer-Header oder Cookie). Gibt 401 bei ungültigem Token."""
    if not config.is_setup_complete:
        return True
    if not config.get("password", ""):
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
    """JSON-Body sicher parsen, mit 400-Fehler bei ungültigem Format."""
    try:
        return await request.json()
    except JSONDecodeError:
        raise HTTPException(status_code=400, detail="Ungültiges JSON-Format")


def _set_auth_cookie(response, token: str, secure: bool = False):
    """Auth-Token als HTTP-Only-Cookie setzen (30 Tage gültig)."""
    response.set_cookie(
        "auth_token", token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=86400 * 30
    )


# ─── WebSocket Connection Manager ──────────────────────────────

class ConnectionManager:
    """Verwaltet aktive WebSocket-Verbindungen für Live-Updates an alle Clients."""
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Neuen WebSocket-Client anmelden und Verbindung akzeptieren."""
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        """WebSocket-Client entfernen, wenn er die Verbindung trennt."""
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Nachricht an alle verbundenen Clients senden. Tote Verbindungen werden aufgeräumt."""
        dead = []
        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.remove(ws)


ws_manager = ConnectionManager()


async def broadcast_sync_complete(result: str):
    """Sync-Ergebnis per WebSocket an alle verbundenen Clients senden."""
    await ws_manager.broadcast({
        "type": "sync_complete",
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def broadcast_items_updated():
    """Signal „Einkaufsliste geändert" an alle WebSocket-Clients senden."""
    await ws_manager.broadcast({"type": "items_updated"})


async def _propagate_add(name: str, quantity: int = 1):
    """Neuen Artikel asynchron an Buy Me a Pie/Grocy weitergeben (Fehler-tolerant)."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, shopping_sync.propagate_add, name, quantity)
    except Exception as e:
        logger.warning(f"Background propagate_add fehlgeschlagen: {e}")


async def _propagate_remove(name: str):
    """Löschen eines Artikels asynchron an die externen Dienste weitergeben."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, shopping_sync.propagate_remove, name)
    except Exception as e:
        logger.warning(f"Background propagate_remove fehlgeschlagen: {e}")


async def _propagate_mark_purchased(name: str):
    """Kauf-Status eines Artikels asynchron an BAP/Grocy weitergeben."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, shopping_sync.propagate_mark_purchased, name)
    except Exception as e:
        logger.warning(f"Background propagate_mark_purchased fehlgeschlagen: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start- und Shutdown-Logik: Verbindungen aufbauen, Hintergrund-Sync starten/stoppen."""
    logger.info("Grot2Buy startet...")
    # Buy Me a Pie-Zugangsdaten entschlüsseln und Client initialisieren
    bap_user = config.get_decrypted("bap_user", "")
    bap_pass = config.get_decrypted("bap_pass", "")
    if bap_user and bap_pass:
        shopping_manager.configure_buymeapie(bap_user, bap_pass)
        logger.info("Buy Me a Pie verbunden")
    else:
        logger.info("Keine BAP-Zugangsdaten — lokaler Modus")
    # Grocy-URL und API-Key aus der Konfiguration laden
    grocy_url = config.get_decrypted("grocy_url", "") or config.get("grocy_url", "")
    grocy_key = config.get_decrypted("grocy_key", "") or config.get("grocy_key", "")
    if grocy_url and grocy_key:
        result = shopping_manager.configure_grocy(grocy_url, grocy_key)
        if result:
            logger.info("Grocy verbunden")
        else:
            logger.warning("Grocy Verbindung fehlgeschlagen")
    else:
        logger.info("Keine Grocy-Zugangsdaten")
    # Sync-Engine mit beiden Clients verknüpfen
    shopping_sync.link_clients(bap=shopping_manager._bap, grocy=shopping_manager._grocy)
    # Hintergrund-Auto-Sync als asynchrone Task starten
    sync_task = asyncio.create_task(_background_sync())
    yield
    sync_task.cancel()
    if shopping_manager._bap:
        shopping_manager._bap.close()
    if shopping_manager._grocy:
        shopping_manager._grocy.close()
    logger.info("Server beendet.")


async def _background_sync():
    """Auto-Sync-Schleife im konfigurierten Intervall. Läuft bis zum Server-Shutdown."""
    while True:
        try:
            interval = config.get("sync_interval", 5)
            if interval and interval > 0:
                await asyncio.sleep(interval * 60)
                bap_client = shopping_manager._bap
                grocy = shopping_manager._grocy
                # Nur synchronisieren, wenn mindestens ein Client verbunden ist
                if grocy or bap_client:
                    result = await shopping_sync.sync_full(grocy, bap_client)
                    logger.info(f"Auto-Sync: {result}")
                    await broadcast_sync_complete(result)
            else:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Auto-Sync Fehler: {e}")
            await asyncio.sleep(60)


tags_metadata = [
    {"name": "Items", "description": "CRUD für Einkaufslisten-Artikel"},
    {"name": "Sync", "description": "Synchronisation mit Grocy und Buy Me a Pie"},
    {"name": "Trash", "description": "Papierkorb (gelöschte Items wiederherstellen)"},
    {"name": "Config", "description": "App-Konfiguration verwalten"},
    {"name": "System", "description": "System-Status und Health-Check"},
    {"name": "WebSocket", "description": "Live-Updates via WebSocket"},
    {"name": "Docs", "description": "Dokumentation und Changelog"},
]

app = FastAPI(
    title="Grot2Buy",
    description="Bidirektionale Synchronisation zwischen Buy Me a Pie, Grocy und lokaler Einkaufsliste.\n\n"
                "Authentifizierung via Bearer Token (`Authorization: Bearer <token>`).\n"
                "WebSocket unter `/ws` für Live-Updates.",
    version=VERSION,
    lifespan=lifespan,
    openapi_tags=tags_metadata,
    contact={"name": "S.B.", "url": "https://github.com/BK01011/grot2buy"},
    license_info={"name": "MIT", "url": "https://github.com/BK01011/grot2buy/blob/main/LICENSE"},
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    swagger_ui_parameters={"persistAuthorization": True},
)

security_scheme = HTTPBearer(auto_error=False)


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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware für sicherheitsrelevante HTTP-Header (CSP, HSTS, XSS-Schutz, Cache)."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self' ws:; img-src 'self' data:; font-src 'self'"
        # API-Antworten nicht cachen (keine veralteten Daten ausliefern)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(SecurityHeadersMiddleware)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statische Dateien (CSS, JS, Bilder) bereitstellen
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# ─── Seiten ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, _: bool = Depends(verify_token)):
    """Hauptseite der Einkaufsliste (leitet zum Setup weiter, falls nicht konfiguriert)."""
    if not config.get("setup_complete", False):
        return RedirectResponse("/setup", status_code=303)
    return templates.TemplateResponse(request, "shopping.html", template_context(request))


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Erstkonfigurations-Seite anzeigen (nur vor dem ersten Setup erreichbar)."""
    if config.get("setup_complete", False):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "setup.html", template_context(request))


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login-Seite anzeigen (nur wenn Setup abgeschlossen und Passwort gesetzt)."""
    if not config.is_setup_complete:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", template_context(request))


_login_attempts: dict[str, list[float]] = {}

def _client_ip(request: Request) -> str:
    """Echte Client-IP ermitteln, auch hinter Reverse-Proxys (X-Forwarded-For, X-Real-IP)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP", "")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"

def _check_rate_limit(ip: str, max_attempts: int = 5, window: int = 300) -> bool:
    """Login-Rate-Limiter: max. max_attempts Fehlversuche innerhalb von window Sekunden pro IP."""
    now = time.time()
    # Dict vor Überlauf schützen (max. 10.000 Einträge)
    if len(_login_attempts) > 10000:
        _login_attempts.clear()
    attempts = _login_attempts.get(ip, [])
    # Abgelaufene Einträge entfernen
    attempts = [t for t in attempts if now - t < window]
    _login_attempts[ip] = attempts
    if len(attempts) >= max_attempts:
        return False
    attempts.append(now)
    return True

@app.post("/login")
async def login_submit(request: Request, password: str = Form("")):
    """Login-Formular verarbeiten: Passwort prüfen, Token ausstellen, Rate-Limiting."""
    client_ip = _client_ip(request)
    if not _check_rate_limit(client_ip):
        import asyncio
        await asyncio.sleep(2)
        return templates.TemplateResponse(request, "login.html", template_context(request, {
            "error": "Zu viele Fehlversuche. Bitte warte 5 Minuten."
        }))
    stored_pass = config.get("password", "")
    if stored_pass and verify_password(password, stored_pass):
        token = secrets.token_urlsafe(32)
        config.set_auth_token(token)
        response = RedirectResponse("/", status_code=303)
        _set_auth_cookie(response, token, secure=request.url.scheme == "https")
        return response
    return templates.TemplateResponse(request, "login.html", template_context(request, {
        "error": i18n_t("login.error", config.get("lang", "de"))
    }))


@app.get("/logout")
async def logout():
    """Ausloggen: Auth-Cookie löschen und zur Login-Seite weiterleiten."""
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("auth_token")
    return response


BLOCKED_HOSTS = {"metadata.google.internal", "metadata.lxd"}

def _validate_url(url: str) -> bool:
    """SSRF-Prüfung: Erlaubt nur öffentliche HTTP(S)-URLs, blockt Loopback/Private/Metadaten-Hosts."""
    from urllib.parse import urlparse
    import ipaddress
    try:
        parsed = urlparse(url)
        # Nur HTTP/HTTPS erlauben
        if parsed.scheme not in {"http", "https"}:
            return False
        host = parsed.hostname
        if not host:
            return False
        # Bekannte Cloud-Metadaten-Endpoints blocken
        if host in BLOCKED_HOSTS:
            return False
        try:
            addr = ipaddress.ip_address(host)
            # Loopback (127.0.0.1), private IPs (10.x, 192.168.x) und Link-Local blocken
            if addr.is_loopback or addr.is_private or addr.is_link_local:
                return False
        except ValueError:
            pass  # Hostname (keine IP), kommt durch
        return True
    except Exception:
        return False


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
    """Erstkonfiguration: Passwort, BAP-/Grocy-Zugangsdaten und Sprache speichern."""
    if config.get("setup_complete", False):
        return RedirectResponse("/", status_code=303)
    if grocy_url and not _validate_url(grocy_url):
        return templates.TemplateResponse(request, "setup.html", template_context(request, {
            "error": "Ungültige Grocy-URL."
        }))
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

    shopping_sync.link_clients(shopping_manager._bap, shopping_manager._grocy)

    token = secrets.token_urlsafe(32)
    config.set_auth_token(token)
    response = RedirectResponse("/", status_code=303)
    _set_auth_cookie(response, token, secure=request.url.scheme == "https")
    return response


# ─── API: Listen ────────────────────────────────────────────────

def _ensure_bap_client() -> Optional[BuyMeAPieClient]:
    """BAP-Client zurückgeben oder neu initialisieren, falls noch nicht verbunden."""
    if shopping_manager._bap:
        return shopping_manager._bap
    bap_user = config.get_decrypted("bap_user", "")
    bap_pass = config.get_decrypted("bap_pass", "")
    if bap_user and bap_pass:
        shopping_manager.configure_buymeapie(bap_user, bap_pass)
        shopping_sync.link_clients(shopping_manager._bap, shopping_manager._grocy)
        return shopping_manager._bap
    return None


@app.get("/api/lists", tags=["Items"])
async def api_lists(_: bool = Depends(verify_token)):
    """Alle BAP-Einkaufslisten mit Artikelanzahl und Sync-Statistiken abrufen."""
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


@app.get("/api/lists/{list_id}/items", tags=["Items"])
async def api_list_items(list_id: str, _: bool = Depends(verify_token)):
    """Alle aktiven Artikel einer bestimmten BAP-Liste abrufen."""
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


# ─── Share-Tokens ──────────────────────────────────────────────

SHARE_TOKENS_FILE = BASE_DIR / "data" / "share_tokens.json"


def _load_share_tokens() -> dict:
    """Freigabe-Tokens aus der verschlüsselten JSON-Datei laden, abgelaufene entfernen."""
    try:
        raw = SHARE_TOKENS_FILE.read_text()
    except FileNotFoundError:
        return {}
    try:
        if raw.startswith("gAAAAA"):
            raw = decrypt(raw)
        tokens = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return {}
    now = datetime.now(timezone.utc)
    changed = False
    for k, v in list(tokens.items()):
        if "uid" not in v:
            v["uid"] = secrets.token_urlsafe(8)
            changed = True
        expires = v.get("expires_at")
        if expires and datetime.fromisoformat(expires) < now:
            del tokens[k]
            changed = True
    if changed:
        _save_share_tokens(tokens)
    return tokens


def _save_share_tokens(tokens: dict):
    """Freigabe-Tokens verschlüsselt auf Disk persistieren."""
    SHARE_TOKENS_FILE.write_text(encrypt(json.dumps(tokens, indent=2)))


def _create_share_token(name: str = "") -> dict:
    """Neuen Freigabe-Token mit 30 Tagen Gültigkeit erstellen."""
    tokens = _load_share_tokens()
    token = secrets.token_urlsafe(32)
    uid = secrets.token_urlsafe(8)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=30)
    tokens[token] = {
        "uid": uid,
        "name": name or f"Freigabe #{len(tokens) + 1}",
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "active": True,
    }
    _save_share_tokens(tokens)
    return {"token": token, "uid": uid, **tokens[token]}


@app.post("/api/share/create", tags=["Share"])
async def api_share_create(request: Request, _: bool = Depends(verify_token)):
    """Neuen Freigabe-Link erstellen (30 Tage gültig) und die URL zurückgeben."""
    body = await parse_json_body(request)
    name = body.get("name", "")
    result = _create_share_token(name)
    link = f"{request.base_url}api/share/{result['token']}/items"
    result["link"] = link
    return JSONResponse(result)


@app.post("/api/share/revoke", tags=["Share"])
async def api_share_revoke(request: Request, _: bool = Depends(verify_token)):
    """Freigabe-Token per UID deaktivieren (widerrufen)."""
    body = await parse_json_body(request)
    uid = body.get("uid", "")
    if not uid:
        return JSONResponse({"error": "uid erforderlich"}, status_code=400)
    tokens = _load_share_tokens()
    for k, v in list(tokens.items()):
        if v.get("uid") == uid:
            tokens[k]["active"] = False
            _save_share_tokens(tokens)
            return JSONResponse({"result": "Token deaktiviert."})
    return JSONResponse({"result": "Token nicht gefunden."}, status_code=404)


@app.get("/api/share/tokens", tags=["Share"])
async def api_share_tokens(_: bool = Depends(verify_token)):
    """Alle aktiven Freigabe-Tokens auflisten (ohne die Tokens selbst)."""
    tokens = _load_share_tokens()
    result = [{"uid": v.get("uid", ""), "name": v.get("name", ""),
               "created_at": v.get("created_at", ""), "active": v.get("active", True)}
              for k, v in tokens.items()]
    return JSONResponse({"tokens": result})


@app.get("/api/share/{token}/items", tags=["Share"])
async def api_share_items(token: str):
    """Öffentlicher Endpunkt: Aktive Einkaufslisten-Items über einen Freigabe-Link abrufen (kein Auth nötig)."""
    tokens = _load_share_tokens()
    td = tokens.get(token)
    if not td or not td.get("active"):
        return JSONResponse({"error": "Ungültiger oder deaktivierter Freigabe-Link."}, status_code=404)
    expires = td.get("expires_at")
    if expires and datetime.fromisoformat(expires) < datetime.now(timezone.utc):
        td["active"] = False
        _save_share_tokens(tokens)
        return JSONResponse({"error": "Freigabe-Link ist abgelaufen."}, status_code=410)
    items = [
        {"name": i.get("name", ""), "quantity": i.get("quantity", 1), "category": i.get("category", "")}
        for i in shopping_sync._synced_items if not i.get("purchased")
    ]
    return JSONResponse({
        "items": items,
        "count": len(items),
        "shared_by": "Grot2Buy",
    })


# ─── API: Artikel verwalten ────────────────────────────────────

@app.post("/api/items/add", tags=["Items"])
async def api_add_item(request: Request, _: bool = Depends(verify_token)):
    """Neuen Artikel zur Einkaufsliste hinzufügen. Validiert Name (max. 200) und Menge (1-999)."""
    body = await parse_json_body(request)
    name = body.get("name", "").strip()
    quantity = body.get("quantity", 1)
    category = body.get("category", "")

    if not name:
        return JSONResponse({"error": "Name erforderlich"}, status_code=400)
    if len(name) > 200:
        return JSONResponse({"error": "Name zu lang (max. 200 Zeichen)"}, status_code=400)
    if not isinstance(quantity, int) or quantity < 1 or quantity > 999:
        return JSONResponse({"error": "Ungültige Menge (1-999)"}, status_code=400)

    result = await shopping_sync.add_item(name, quantity, category)
    logger.info(f"Hinzugefügt: {name} (x{quantity}, {category})")
    asyncio.create_task(_propagate_add(name, quantity))
    await broadcast_items_updated()

    return JSONResponse({
        "result": result,
        "name": name,
        "quantity": quantity,
        "category": category,
    })


@app.post("/api/items/add-bulk", tags=["Items"])
async def api_add_items_bulk(request: Request, _: bool = Depends(verify_token)):
    """Mehrere Artikel auf einmal hinzufügen (max. 100). Akzeptiert JSON-Array oder Zeilenumbrüche."""
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

    if len(lines) > 100:
        return JSONResponse({"error": "Maximal 100 Artikel auf einmal erlaubt"}, status_code=400)

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
            asyncio.create_task(_propagate_add(name, qty))
        else:
            skipped += 1

    await broadcast_items_updated()
    return JSONResponse({
        "added": added,
        "skipped": skipped,
        "total": len(lines),
    })


@app.post("/api/items/{item_name}/remove", tags=["Items"])
async def api_remove_item(item_name: str, _: bool = Depends(verify_token)):
    """Einzelnen Artikel aus der Liste entfernen (in den Papierkorb verschieben)."""
    result = await shopping_sync.remove_item(item_name)
    logger.info(f"Entfernt: {item_name}")
    asyncio.create_task(_propagate_remove(item_name))
    await broadcast_items_updated()
    return JSONResponse({"result": result})


@app.get("/api/trash/items", tags=["Trash"])
async def api_trash_items(_: bool = Depends(verify_token)):
    """Papierkorb-Inhalte abrufen (gelöschte, noch nicht endgültig entfernte Artikel)."""
    items = shopping_sync.get_trash()
    return JSONResponse({"items": items, "count": len(items)})


@app.post("/api/trash/restore/{item_name}", tags=["Trash"])
async def api_trash_restore(item_name: str, _: bool = Depends(verify_token)):
    """Gelöschten Artikel aus dem Papierkorb zurück in die Liste holen."""
    result = await shopping_sync.restore_item(item_name)
    logger.info(f"Wiederhergestellt: {item_name}")
    await broadcast_items_updated()
    return JSONResponse({"result": result})


@app.post("/api/trash/empty", tags=["Trash"])
async def api_trash_empty(_: bool = Depends(verify_token)):
    """Papierkorb endgültig leeren (nicht wiederherstellbar)."""
    bap_client = shopping_manager._bap
    grocy_client = shopping_manager._grocy if shopping_manager._grocy else None
    result = await shopping_sync.empty_trash(bap_client=bap_client, grocy_client=grocy_client)
    logger.info(f"Papierkorb geleert: {result}")
    await broadcast_items_updated()
    return JSONResponse({"result": result})


@app.post("/api/items/{item_name}/purchased", tags=["Items"])
async def api_mark_purchased(item_name: str, _: bool = Depends(verify_token)):
    """Artikel als gekauft markieren (entfernt ihn aus der aktiven Liste)."""
    logger.info(f"Kauf-Anfrage für '{item_name}'")
    result = await shopping_sync.mark_purchased(item_name)
    logger.info(f"Erledigt: {item_name} → {result}")
    asyncio.create_task(_propagate_mark_purchased(item_name))
    await broadcast_items_updated()
    return JSONResponse({"result": result})


@app.post("/api/items/{item_name}/quantity", tags=["Items"])
async def api_update_quantity(item_name: str, request: Request, _: bool = Depends(verify_token)):
    """Menge eines Artikels ändern (1-999) und Grocy-Listen-Eintrag synchron halten."""
    body = await parse_json_body(request)
    quantity = body.get("quantity", 1)
    if not isinstance(quantity, int) or quantity < 1 or quantity > 999:
        return JSONResponse({"error": "Ungültige Menge (1-999)"}, status_code=400)
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
    await broadcast_items_updated()
    return JSONResponse({"result": msg})


@app.post("/api/items/clear-purchased", tags=["Items"])
async def api_clear_purchased(_: bool = Depends(verify_token)):
    """Alle als gekauft markierten Artikel auf einmal aus der Liste entfernen."""
    result = await shopping_sync.clear_purchased()
    logger.info(f"Gekaufte Artikel bereinigt: {result}")
    await broadcast_items_updated()
    return JSONResponse({"result": result})


@app.post("/api/items/batch-purchased", tags=["Items"])
async def api_batch_purchased(request: Request, _: bool = Depends(verify_token)):
    """Mehrere Artikel gleichzeitig als gekauft markieren (Batch-Operation)."""
    body = await parse_json_body(request)
    names = body.get("names", [])
    if not names:
        return JSONResponse({"result": "Keine Artikel ausgewählt."})
    result = await shopping_sync.batch_mark_purchased(names)
    logger.info(f"Batch gekauft ({len(names)}): {result}")
    for n in names:
        asyncio.create_task(_propagate_mark_purchased(n))
    await broadcast_items_updated()
    return JSONResponse({"result": result})


@app.post("/api/items/batch-remove", tags=["Items"])
async def api_batch_remove(request: Request, _: bool = Depends(verify_token)):
    """Mehrere Artikel gleichzeitig aus der Liste entfernen (Batch-Operation)."""
    body = await parse_json_body(request)
    names = body.get("names", [])
    if not names:
        return JSONResponse({"result": "Keine Artikel ausgewählt."})
    result = await shopping_sync.batch_remove(names)
    logger.info(f"Batch entfernt ({len(names)}): {result}")
    for n in names:
        asyncio.create_task(_propagate_remove(n))
    await broadcast_items_updated()
    return JSONResponse({"result": result})


# ─── API: BAP-Synchronisation ──────────────────────────────────

@app.get("/api/sync/push", tags=["Sync"])
async def api_sync_push(_: bool = Depends(verify_token)):
    """Lokale Liste an Buy Me a Pie pushen (Einweg-Sync: lokal → BAP)."""
    try:
        client = shopping_manager._bap
        if not client:
            return JSONResponse({"result": "Keine BAP-Verbindung"})
        result = shopping_sync.push_to_buymeapie(client)
        logger.info(f"BAP-Push: {result}")
        await broadcast_items_updated()
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"BAP-Push-Fehler: {e}")
        return JSONResponse({"result": "Fehler beim Push-Sync"})


@app.get("/api/sync/pull", tags=["Sync"])
async def api_sync_pull(_: bool = Depends(verify_token)):
    """Gekaufte Artikel von Buy Me a Pie abrufen (Einweg-Sync: BAP → lokal)."""
    try:
        client = shopping_manager._bap
        if not client:
            return JSONResponse({"result": "Keine BAP-Verbindung"})
        grocy = shopping_manager._grocy
        result = shopping_sync.pull_purchased_from_bap(client, grocy)
        logger.info(f"BAP-Pull: {result}")
        await broadcast_items_updated()
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"BAP-Pull-Fehler: {e}")
        return JSONResponse({"result": "Fehler beim Pull-Sync"})


@app.get("/api/sync/full", tags=["Sync"])
async def api_sync_full(_: bool = Depends(verify_token)):
    """Vollständiger bidirektionaler Sync zwischen BAP, Grocy und lokaler Liste."""
    try:
        bap_client = shopping_manager._bap
        grocy = shopping_manager._grocy

        # Bidirektionaler Sync wenn beide Quellen verfügbar, sonst Einweg
        if bap_client and grocy:
            result = await shopping_sync.sync_full(grocy, bap_client)
        elif bap_client:
            result = shopping_sync.push_to_buymeapie(bap_client)
        elif grocy:
            result = shopping_sync.get_merged_text()
        else:
            result = "Keine Verbindung konfiguriert"

        logger.info(f"Vollsync: {result}")
        await broadcast_sync_complete(result)
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"Vollsync-Fehler: {e}")
        return JSONResponse({"result": "Fehler bei der Synchronisation"})


@app.get("/api/sync/grocy", tags=["Sync"])
async def api_sync_grocy(_: bool = Depends(verify_token)):
    """Rohdaten der Grocy-Einkaufsliste abrufen (Name, Menge, ID)."""
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


@app.get("/api/sync/grocy/push", tags=["Sync"])
async def api_sync_grocy_push(_: bool = Depends(verify_token)):
    """Lokale Einkaufsliste nach Grocy übertragen (lokal → Grocy)."""
    grocy = shopping_manager._grocy
    if not grocy:
        return JSONResponse({"result": "Keine Grocy-Verbindung"})
    try:
        result = shopping_sync.push_to_grocy(grocy)
        logger.info(f"Grocy-Push: {result}")
        await broadcast_items_updated()
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"Grocy-Push-Fehler: {e}")
        return JSONResponse({"result": "Fehler beim Grocy-Push"})


@app.get("/api/sync/grocy/pull", tags=["Sync"])
async def api_sync_grocy_pull(_: bool = Depends(verify_token)):
    """Grocy-Artikel in die lokale Liste importieren (Grocy → lokal)."""
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
        await broadcast_items_updated()
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"Grocy-Pull-Fehler: {e}")
        return JSONResponse({"result": "Fehler beim Grocy-Pull"})


# ─── API: Daten ────────────────────────────────────────────────

@app.get("/api/synced", tags=["Sync"])
async def api_synced(_: bool = Depends(verify_token)):
    """Zusammengeführte Text-Ansicht der gesamten Sync-Liste abrufen."""
    return JSONResponse({"text": shopping_sync.get_merged_text()})


@app.get("/api/synced/items", tags=["Sync"])
async def api_synced_items(_: bool = Depends(verify_token)):
    """Synced-Items mit Kategoriesortierung und optionalem Grocy-Bestand abrufen."""
    # Initialen Sync anstoßen, falls die Liste noch leer ist
    if not shopping_sync._synced_items and (shopping_manager._bap or shopping_manager._grocy):
        logger.info("Synced-Liste leer → initialer Auto-Sync")
        try:
            await shopping_sync.sync_full(shopping_manager._grocy, shopping_manager._bap, is_initial=True)
        except Exception as e:
            logger.error(f"Initialer Sync fehlgeschlagen: {e}")
    all_items = shopping_sync._synced_items[:]
    # Aktive und gekaufte Items trennen
    active = [i for i in all_items if not i.get("purchased")]
    purchased = [i for i in all_items if i.get("purchased")]

    # Grocy-Bestand je Produkt abrufen
    stock_map = {}
    if shopping_manager._grocy:
        try:
            stock_map = shopping_manager._grocy.get_stock()
        except Exception as e:
            logger.debug(f"Stock-Fehler: {e}")

    # Bestandsinformation an die aktiven Items anhängen
    for item in active:
        nn = shopping_sync._norm(item.get("name", ""))
        if nn in stock_map:
            item["stock"] = stock_map[nn]

    # Items nach Kategorie gruppieren
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


@app.post("/api/synced/reset", tags=["Sync"])
async def api_synced_reset(_: bool = Depends(verify_token)):
    """Komplette Sync-Liste zurücksetzen: Backup anlegen, leeren, neu synchronisieren."""
    backup_path = shopping_sync.backup()
    shopping_sync._synced_items = []
    shopping_sync._removed = []
    shopping_sync._trash = []
    shopping_sync.save()
    try:
        result = await shopping_sync.sync_full(shopping_manager._grocy, shopping_manager._bap)
        await broadcast_items_updated()
        return JSONResponse({"result": result, "count": len(shopping_sync._synced_items)})
    except Exception as e:
        logger.error(f"Sync nach Reset fehlgeschlagen: {e}")
        return JSONResponse({"error": f"Sync fehlgeschlagen, Backup unter {backup_path}", "backup": backup_path}, status_code=500)


@app.get("/api/export")
async def api_export(_: bool = Depends(verify_token)):
    """Synced-Liste als BAP-kompatibles Format exportieren."""
    export = shopping_sync.export_for_buymeapie()
    return JSONResponse({"export": export, "count": len(export.splitlines()) if export else 0})


@app.get("/api/suggestions")
async def api_suggestions(q: str = "", _: bool = Depends(verify_token)):
    """Auto-Vervollständigungsvorschläge aus bestehenden Items + Grocy-Produkten (max. 15)."""
    suggestions = set()
    ql = q.lower().strip()
    # Vorschläge aus der aktuellen Sync-Liste (ungekaufte Items)
    for item in shopping_sync._synced_items:
        if not item.get("purchased") and (not ql or ql in item.get("name", "").lower()):
            suggestions.add(item["name"])
    # Zusätzliche Vorschläge aus den Grocy-Produktnamen
    if shopping_manager._grocy:
        try:
            products = shopping_manager._grocy._get("objects/products")
            if isinstance(products, list):
                for p in products:
                    name = p.get("name", "")
                    if name and (not ql or ql in name.lower()):
                        suggestions.add(name)
        except Exception:
            pass
    sorted_suggestions = sorted(suggestions, key=lambda s: (0 if s.lower().startswith(ql) else 1, s.lower()))
    return JSONResponse({"suggestions": sorted_suggestions[:15]})


@app.get("/api/categories")
async def api_categories(_: bool = Depends(verify_token)):
    """Vordefinierte Kategorien für die Einkaufsliste abrufen."""
    return JSONResponse({"categories": DEFAULT_CATEGORIES})


# ─── API: Konfiguration ───────────────────────────────────────

@app.get("/api/config", tags=["Config"])
async def api_config_get(_: bool = Depends(verify_token)):
    """Aktuelle Konfigurationseinstellungen abrufen (unsensible Werte)."""
    return JSONResponse({
        "bap_user": config.get_decrypted("bap_user", ""),
        "bap_list_name": config.get("bap_list_name", "Einkaufsliste"),
        "has_password": bool(config.get_decrypted("password", "")),
        "sync_interval": config.get("sync_interval", 5),
        "lang": config.get("lang", "de"),
    })


@app.post("/api/config/bap", tags=["Config"])
async def api_config_bap(request: Request, _: bool = Depends(verify_token)):
    """Buy Me a Pie-Zugangsdaten aktualisieren und Client neu verbinden."""
    body = await parse_json_body(request)
    bap_user = body.get("bap_user", "")
    bap_pass = body.get("bap_pass", "")

    config.set_encrypted("bap_user", bap_user)
    config.set_encrypted("bap_pass", bap_pass)

    if bap_user and bap_pass:
        shopping_manager.configure_buymeapie(bap_user, bap_pass)
    shopping_sync.link_clients(shopping_manager._bap, shopping_manager._grocy)

    lang = config.get("lang", "de")
    return JSONResponse({"result": i18n_t("config.bap_updated", lang)})


@app.get("/api/config/sync-interval", tags=["Config"])
async def api_get_sync_interval(_: bool = Depends(verify_token)):
    """Aktuelles Auto-Sync-Intervall in Minuten abrufen."""
    interval = config.get("sync_interval", 5)
    return JSONResponse({"interval": interval})


@app.post("/api/config/sync-interval", tags=["Config"])
async def api_set_sync_interval(request: Request, _: bool = Depends(verify_token)):
    """Auto-Sync-Intervall setzen (in Minuten, 0 deaktiviert Auto-Sync)."""
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


@app.get("/api/config/lang", tags=["Config"])
async def api_get_lang(_: bool = Depends(verify_token)):
    """Aktuelle Sprache und verfügbare Sprachen abrufen."""
    lang = config.get("lang", "de")
    return JSONResponse({"lang": lang, "available": AVAILABLE_LANGUAGES})


@app.post("/api/config/lang", tags=["Config"])
async def api_set_lang(request: Request, _: bool = Depends(verify_token)):
    """Sprache der Benutzeroberfläche ändern und i18n neu laden."""
    body = await parse_json_body(request)
    lang = body.get("lang", "de")
    if lang not in AVAILABLE_LANGUAGES:
        return JSONResponse({"success": False, "error": f"Unsupported language: {lang}"}, status_code=400)
    config.set("lang", lang)
    reload_i18n()
    return JSONResponse({"success": True, "lang": lang})


@app.get("/api/config/export", tags=["Config"])
async def api_config_export(_: bool = Depends(verify_token)):
    """Konfiguration exportieren (sensible Felder werden mit *** unkenntlich gemacht)."""
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


@app.post("/api/config/import", tags=["Config"])
async def api_config_import(request: Request, _: bool = Depends(verify_token)):
    """Konfiguration importieren (Credentials werden blockiert — können nicht überschrieben werden)."""
    body = await parse_json_body(request)
    config_data = body.get("config", {})

    if isinstance(config_data, dict):
        # Sicherheitskritische Keys dürfen nicht überschrieben werden
        blocked_keys = {"secret_key", "auth_token", "auth_token_created_at",
                        "password", "bap_user", "bap_pass", "grocy_url", "grocy_key"}
        for k in blocked_keys:
            config_data.pop(k, None)
        config._data.update(config_data)
        config.save()

    return JSONResponse({"result": "Konfiguration importiert."})


# ─── API: System ───────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    """Einfacher Health-Check-Ping (ohne Auth, für Monitoring-Tools)."""
    return {"status": "ok", "service": "grot2buy"}


@app.get("/api/system/status", tags=["System"])
async def api_system_status(_: bool = Depends(verify_token)):
    """Server-Status mit Version, Backend-Typ und Zeitstempel abrufen."""
    return JSONResponse({
        "status": "running",
        "version": VERSION,
        "backend": shopping_manager.backend,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ─── WebSocket ─────────────────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket-Endpunkt für Live-Updates. Clients erhalten Sync-Benachrichtigungen und können Sync anstoßen."""
    # Origin-Validierung gegen CSWSH (Cross-Site WebSocket Hijacking)
    origin = websocket.headers.get("origin", "")
    if origin:
        from urllib.parse import urlparse
        try:
            import ipaddress
            o = urlparse(origin)
            host = o.hostname or ""
            if host.startswith("["):
                host = host.strip("[]")
            allowed = {"localhost", "127.0.0.1", "::1", "shopping-list"}
            if host not in allowed:
                try:
                    addr = ipaddress.ip_address(host)
                    if not addr.is_private:
                        await websocket.close(code=1008)
                        return
                except ValueError:
                    await websocket.close(code=1008)
                    return
        except Exception:
            await websocket.close(code=1008)
            return
    # Authentifizierung via Cookie-Token, falls ein Passwort gesetzt ist
    has_password = bool(config.get_decrypted("password", ""))
    if has_password:
        token = websocket.cookies.get("auth_token", "")
        if not token or not config.validate_token(token):
            await websocket.close(code=1008)
            return
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg.get("type") == "sync_request":
                try:
                    result = await shopping_sync.sync_full(
                        shopping_manager._grocy, shopping_manager._bap
                    )
                    logger.info(f"WS-Sync: {result}")
                    await broadcast_sync_complete(result)
                except Exception as e:
                    logger.error(f"WS-Sync-Fehler: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WS-Fehler: {e}")
        await ws_manager.disconnect(websocket)


# ─── API: Downloads ─────────────────────────────────────────────

def _md_to_html(md: str) -> str:
    """Minimaler Markdown→HTML Renderer (Server-seitig)."""
    lines = md.split('\n')
    html = []
    in_code = False
    code_buf = []
    in_list = False

    def flush():
        """Offene List-Tags schließen."""
        nonlocal in_list
        if in_list:
            html.append('</ul>\n')
            in_list = False

    def esc(s):
        """HTML-Sonderzeichen escapen (XSS-Schutz)."""
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def inline(s):
        """Inline-Markdown-Elemente (fett, code) in HTML umwandeln."""
        s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'`(.+?)`', r'<code>\1</code>', s)
        return s

    for line in lines:
        # Code-Block umschalten (```)
        if line.startswith('```'):
            if in_code:
                # Code-Block schließen
                html.append('<pre><code>' + esc('\n'.join(code_buf)) + '</code></pre>\n')
                code_buf = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue

        # Überschriften
        if line.startswith('### '):
            flush(); html.append('<h3>' + inline(esc(line[4:])) + '</h3>\n')
        elif line.startswith('## '):
            flush(); html.append('<h2>' + inline(esc(line[3:])) + '</h2>\n')
        elif line.startswith('# '):
            flush(); html.append('<h1>' + inline(esc(line[2:])) + '</h1>\n')
        # Ungeordnete Listen
        elif line.startswith('- ') or line.startswith('* '):
            if not in_list:
                html.append('<ul>\n'); in_list = True
            html.append('<li>' + inline(esc(line[2:])) + '</li>\n')
        # Nummerierte Listen
        elif re.match(r'^\d+\.\s', line):
            if not in_list:
                html.append('<ol>\n'); in_list = 'ol'
            html.append('<li>' + inline(esc(re.sub(r'^\d+\.\s', '', line))) + '</li>\n')
        # Leerzeilen trennen Absätze
        elif line.strip() == '':
            flush()
        # Horizontale Trennlinie
        elif line.startswith('---'):
            flush(); html.append('<hr>\n')
        # Normale Absätze
        else:
            flush(); html.append('<p>' + inline(esc(line)) + '</p>\n')

    # Übrig gebliebene Code/List-Blöcke schließen
    if in_code:
        html.append('<pre><code>' + esc('\n'.join(code_buf)) + '</code></pre>\n')
    if in_list:
        html.append('</ul>\n')
    return ''.join(html)


@app.get("/api/docs/doku", tags=["Docs"])
async def get_doku(_: bool = Depends(verify_token)):
    """DOKU.md als HTML ausliefern (Server-seitig gerendert)."""
    try:
        with open("DOKU.md", "r", encoding="utf-8") as f:
            content = f.read()
        return {"title": "Dokumentation", "html": _md_to_html(content)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/docs/changelog", tags=["Docs"])
async def get_changelog(_: bool = Depends(verify_token)):
    """CHANGELOG.md als HTML ausliefern (Server-seitig gerendert)."""
    try:
        with open("CHANGELOG.md", "r", encoding="utf-8") as f:
            content = f.read()
        return {"title": "Changelog", "html": _md_to_html(content)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


def _read_last_n_lines(filepath: str, n: int = 200) -> str:
    """Liest die letzten n Zeilen einer Datei, sicher und speichereffizient."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            from collections import deque
            lines = deque(f, maxlen=n)
        return "".join(lines)
    except Exception:
        return ""


# Zu filternde Patterns (Credentials, Tokens)
_LOG_SANITIZE_PATTERNS = [
    (re.compile(r'(?i)(password|passwd|pwd|api_key|apikey|token|secret|auth)\s*[:=]\s*\S+'), r'\1=***'),
    (re.compile(r'(?i)(bap_pass|bap_user|grocy_key|grocy_url)\s*[:=]\s*\S+'), r'\1=***'),
    (re.compile(r'Authorization:\s*\S+'), 'Authorization: ***'),
    (re.compile(r'Bearer\s+\S+'), 'Bearer ***'),
]


@app.get("/api/logs", tags=["Docs"])
async def get_logs(lines: int = 200, _: bool = Depends(verify_token)):
    """Gibt die letzten N Zeilen des Logs zurück (gesäubert — Credentials/Tokens werden entfernt)."""
    max_lines = min(max(lines, 10), 500)
    raw = _read_last_n_lines(str(LOG_FILE), max_lines)
    sanitized = raw
    # Alle bekannten Credential-Muster aus den Logs entfernen
    for pattern, replacement in _LOG_SANITIZE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return {"logs": sanitized, "lines": max_lines}


if __name__ == "__main__":
    import uvicorn
    cert_dir = Path(__file__).parent / "certs"
    ssl_keyfile = str(cert_dir / "server.key") if (cert_dir / "server.key").exists() else None
    ssl_certfile = str(cert_dir / "server.crt") if (cert_dir / "server.crt").exists() else None
    uvicorn.run(app, host="0.0.0.0", port=config.server_port,
                ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile)
