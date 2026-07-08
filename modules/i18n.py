"""Internationalisierung — mehrsprachige Text-Wiedergabe.

Füge einfach eine neue .json-Datei in i18n/ hinzu, z.B. i18n/fr.json.
Die Sprache wird über config["lang"] gesteuert.
"""
import json
from pathlib import Path

I18N_DIR = Path(__file__).parent.parent / "i18n"
AVAILABLE_LANGUAGES = ["de", "en"]

MAX_CACHED_LANGUAGES = 10
_cache: dict[str, dict] = {}
_cache_order: list[str] = []

def _load(lang: str) -> dict:
    lang = lang or "de"
    if lang not in _cache:
        if len(_cache) >= MAX_CACHED_LANGUAGES:
            oldest = _cache_order.pop(0)
            _cache.pop(oldest, None)
        path = I18N_DIR / f"{lang}.json"
        if path.exists():
            _cache[lang] = json.loads(path.read_text())
        else:
            _cache[lang] = {}
        _cache_order.append(lang)
    return _cache[lang]

def flattened(lang: str) -> dict[str, str]:
    """Flatten translation dict to dot-separated keys for JS."""
    result = {}
    def _walk(d, prefix=""):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                _walk(v, key)
            elif isinstance(v, str):
                result[key] = v
    _walk(_load(lang))
    return result

def t(key: str, lang: str = "de", **kwargs) -> str:
    """Hole Übersetzung für einen Punkt-Notation-Key.

    >>> t("header.title", "de")
    'Grot2Buy'
    >>> t("header.title", "en")
    'Grot2Buy'
    >>> t("item.added", "en", name="Milk")
    'Milk added.'
    """
    data = _load(lang)
    parts = key.split(".")
    val = data
    for p in parts:
        if isinstance(val, dict) and p in val:
            val = val[p]
        else:
            return key
    if not isinstance(val, str):
        return key
    if kwargs:
        try:
            return val.format(**kwargs)
        except KeyError:
            return val
    return val

def reload():
    """Leert den Cache – beim nächsten t()-Aufruf wird neu geladen."""
    _cache.clear()
    _cache_order.clear()
