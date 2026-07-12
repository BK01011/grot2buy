"""Verschlüsselte Konfigurations- und Zugangsdaten-Verwaltung."""
import json
import secrets
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Optional

logger = logging.getLogger("shopping")

DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"
KEY_FILE = DATA_DIR / "secret.key"


def _load_or_create_key() -> bytes:
    """Lädt den vorhandenen Fernet-Verschlüsselungsschlüssel oder erstellt einen neuen.

    Der Schlüssel wird in data/secret.key abgelegt und auf 0o600 gesetzt,
    sodass nur der Eigentümer lesen kann.
    """
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    os.chmod(str(KEY_FILE), 0o600)  # nur Besitzer darf lesen
    return key


_fernet = Fernet(_load_or_create_key())


def encrypt(value: str) -> str:
    """Verschlüsselt einen Klartext-String mit dem Fernet-Schlüssel."""
    return _fernet.encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    """Entschlüsselt einen Fernet-Token zurück in den Klartext."""
    return _fernet.decrypt(token.encode()).decode()


def _atomic_write(path: Path, content: str):
    """Schreibt eine Datei atomar via .tmp-Datei, um Datenverlust zu vermeiden.

    Schreibt zuerst in eine temporäre Datei, setzt Berechtigungen auf 0o600
    und ersetzt dann das Ziel – so bleibt bei Abstürzen die alte Datei erhalten.
    """
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.chmod(str(tmp), 0o600)  # nur Besitzer darf lesen
    tmp.replace(path)


class Config:
    """Zentrale Konfigurationsverwaltung mit Verschlüsselung sensibler Daten.

    Speichert alle Einstellungen in einer JSON-Datei (data/config.json).
    Sensible Felder (API-Keys, Passwörter) werden mit Fernet verschlüsselt
    und als {"__encrypted__": True, "value": "..."} abgelegt.
    """

    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        """Lädt die Konfiguration aus der JSON-Datei."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Config-Datei korrupt: {e}")
                self._data = {}
        # Migration: fehlenden timestamp für auth_token nachtragen
        if self.auth_token and not self._data.get("auth_token_created_at"):
            self._data["auth_token_created_at"] = datetime.now(timezone.utc).isoformat()
            self.save()

    def save(self):
        """Schreibt die Konfiguration atomar auf die Festplatte."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _atomic_write(CONFIG_FILE, json.dumps(self._data, indent=2, ensure_ascii=False))

    def get(self, key: str, default=None):
        """Gibt einen Konfigurationswert zurück."""
        return self._data.get(key, default)

    def set(self, key: str, value):
        """Setzt einen Konfigurationswert und speichert sofort."""
        self._data[key] = value
        self.save()

    def set_encrypted(self, key: str, value: str):
        """Verschlüsselt einen Wert und speichert ihn in der Konfiguration."""
        self._data[key] = {"__encrypted__": True, "value": encrypt(value)}
        self.save()

    def get_decrypted(self, key: str, default=None) -> Optional[str]:
        """Liest einen verschlüsselten Wert aus der Konfiguration und entschlüsselt ihn."""
        val = self._data.get(key)
        if val is None:
            return default
        if isinstance(val, dict) and val.get("__encrypted__"):
            return decrypt(val["value"])
        return str(val)

    @property
    def is_setup_complete(self) -> bool:
        return self._data.get("setup_complete", False)

    @property
    def ai_provider(self) -> str:
        return self._data.get("ai_provider", "gemini")

    @property
    def ai_api_key(self) -> str:
        return self.get_decrypted("ai_api_key", "")

    @property
    def ai_model(self) -> str:
        return self._data.get("ai_model", "gemini-2.0-flash")

    @property
    def imap_host(self) -> str:
        return self._data.get("imap_host", "")

    @property
    def imap_port(self) -> int:
        return int(self._data.get("imap_port", 993))

    @property
    def imap_user(self) -> str:
        return self._data.get("imap_user", "")

    @property
    def imap_pass(self) -> str:
        return self.get_decrypted("imap_pass", "")

    @property
    def imap_folder(self) -> str:
        return self._data.get("imap_folder", "INBOX")

    @property
    def smtp_host(self) -> str:
        return self._data.get("smtp_host", "")

    @property
    def smtp_port(self) -> int:
        return int(self._data.get("smtp_port", 587))

    @property
    def smtp_user(self) -> str:
        return self._data.get("smtp_user", "")

    @property
    def smtp_pass(self) -> str:
        return self.get_decrypted("smtp_pass", "")

    @property
    def caldav_url(self) -> str:
        return self._data.get("caldav_url", "")

    @property
    def caldav_user(self) -> str:
        return self._data.get("caldav_user", "")

    @property
    def caldav_pass(self) -> str:
        return self.get_decrypted("caldav_pass", "")

    @property
    def server_host(self) -> str:
        return self._data.get("server_host", "0.0.0.0")

    @property
    def server_port(self) -> int:
        return int(self._data.get("server_port", 8899))

    @property
    def person_name(self) -> str:
        return self._data.get("person_name", "")

    @property
    def auth_token(self) -> str:
        val = self._data.get("auth_token")
        if isinstance(val, dict) and val.get("__encrypted__"):
            return decrypt(val["value"])
        return str(val) if val else ""

    TOKEN_MAX_AGE_DAYS = 30

    def set_auth_token(self, token: str):
        """Setzt einen neuen Authentifizierungs-Token (verschlüsselt) mit Zeitstempel."""
        self._data["auth_token"] = {"__encrypted__": True, "value": encrypt(token)}
        self._data["auth_token_created_at"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def validate_token(self, token: str) -> bool:
        """Prüft einen Token gegen den gespeicherten (konstante Zeit, Altersprüfung)."""
        stored = self.auth_token
        if not stored:
            return False
        created_at = self._data.get("auth_token_created_at")
        if not created_at:
            return False
        try:
            created = datetime.fromisoformat(created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            # Token älter als TOKEN_MAX_AGE_DAYS → ungültig
            if (datetime.now(timezone.utc) - created).days >= self.TOKEN_MAX_AGE_DAYS:
                return False
        except Exception:
            return False
        return secrets.compare_digest(token, stored)

    def reset_auth_tokens(self):
        """Entfernt alle Auth-Tokens und zwingt Benutzer zum erneuten Einloggen."""
        self._data.pop("auth_token", None)
        self._data.pop("auth_token_created_at", None)
        self.save()


config = Config()
