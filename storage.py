"""
Minimal persistence for per-user target-language preferences.

Uses a local JSON file. Good enough for a single Railway service with
light traffic. For production-grade durability (survives redeploys,
scales across instances) swap this out for Postgres/Redis - Railway
can provision either with one click and you'd just change the two
functions below to read/write from that instead.
"""

import json
import os
import threading

_LOCK = threading.Lock()
_FILE = os.path.join(os.path.dirname(__file__), "user_prefs.json")


def _load() -> dict:
    if not os.path.exists(_FILE):
        return {}
    try:
        with open(_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_user_lang(user_id: int, default: str = "en") -> str:
    with _LOCK:
        data = _load()
        return data.get(str(user_id), default)


def set_user_lang(user_id: int, lang_code: str) -> None:
    with _LOCK:
        data = _load()
        data[str(user_id)] = lang_code
        _save(data)
