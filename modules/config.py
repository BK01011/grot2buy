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
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    os.chmod(str(KEY_FILE), 0o600)
    return key


_fernet = Fernet(_load_or_create_key())


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()


def _atomic_write(path: Path, content: str):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.chmod(str(tmp), 0o600)
    tmp.replace(path)


class Config:
    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Config-Datei korrupt: {e}")
                self._data = {}
        if self.auth_token and not self._data.get("auth_token_created_at"):
            self._data["auth_token_created_at"] = datetime.now(timezone.utc).isoformat()
            self.save()

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _atomic_write(CONFIG_FILE, json.dumps(self._data, indent=2, ensure_ascii=False))

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    def set_encrypted(self, key: str, value: str):
        self._data[key] = {"__encrypted__": True, "value": encrypt(value)}
        self.save()

    def get_decrypted(self, key: str, default=None) -> Optional[str]:
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
        self._data["auth_token"] = {"__encrypted__": True, "value": encrypt(token)}
        self._data["auth_token_created_at"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def validate_token(self, token: str) -> bool:
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
            if (datetime.now(timezone.utc) - created).days >= self.TOKEN_MAX_AGE_DAYS:
                return False
        except Exception:
            return False
        return secrets.compare_digest(token, stored)

    def reset_auth_tokens(self):
        self._data.pop("auth_token", None)
        self._data.pop("auth_token_created_at", None)
        self.save()


config = Config()
