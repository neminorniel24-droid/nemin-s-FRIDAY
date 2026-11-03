"""Small settings that survive restarts (persona, theme, timezone). Stored in backend/data/settings.json."""
import json
import threading

from config import DATA_DIR

_FILE = DATA_DIR / "settings.json"
_LOCK = threading.Lock()


def _load() -> dict:
    try:
        d = json.loads(_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def get(key: str, default=None):
    with _LOCK:
        return _load().get(key, default)


def put(key: str, value) -> None:
    with _LOCK:
        d = _load()
        d[key] = value
        tmp = _FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=2), encoding="utf-8")
        tmp.replace(_FILE)
