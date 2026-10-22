"""
Memory that survives restarts.

  history : the last few messages (so she follows the conversation)
  facts   : things you told her to remember ("remember my exam is on Friday")

Stored in backend/data/memory.json.
"""
import json
import threading
from datetime import datetime

from config import DATA_DIR

_FILE = DATA_DIR / "memory.json"
_LOCK = threading.Lock()
MAX_HISTORY = 24   # messages kept
MAX_FACTS = 60


def _load() -> dict:
    try:
        data = json.loads(_FILE.read_text(encoding="utf-8"))
        data.setdefault("history", [])
        data.setdefault("facts", [])
        return data
    except Exception:
        return {"history": [], "facts": []}


def _save(data: dict) -> None:
    tmp = _FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_FILE)


def get_history() -> list[dict]:
    with _LOCK:
        return list(_load()["history"])


def add_message(role: str, content: str) -> None:
    with _LOCK:
        data = _load()
        data["history"].append({"role": role, "content": content})
        data["history"] = data["history"][-MAX_HISTORY:]
        _save(data)


def get_facts() -> list[str]:
    with _LOCK:
        return [f["text"] for f in _load()["facts"]]


def add_fact(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    with _LOCK:
        data = _load()
        if any(f["text"].lower() == text.lower() for f in data["facts"]):
            return True
        data["facts"].append({"text": text, "at": datetime.now().isoformat(timespec="minutes")})
        data["facts"] = data["facts"][-MAX_FACTS:]
        _save(data)
    return True


def forget_fact(keyword: str) -> int:
    keyword = keyword.strip().lower()
    with _LOCK:
        data = _load()
        before = len(data["facts"])
        data["facts"] = [f for f in data["facts"] if keyword not in f["text"].lower()]
        _save(data)
        return before - len(data["facts"])


def clear_history() -> None:
    with _LOCK:
        data = _load()
        data["history"] = []
        _save(data)


def clear_all() -> None:
    with _LOCK:
        _save({"history": [], "facts": []})
