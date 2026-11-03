"""
The action log: every single thing she does is written here, so you can always see what happened.
One JSON line per action in backend/data/activity.log (kept under about 1 MB).
"""
import json
import threading

import clock
from config import DATA_DIR

_FILE = DATA_DIR / "activity.log"
_LOCK = threading.Lock()
MAX_BYTES = 1_000_000
_SECRET_WORDS = ("password", "token", "secret", "key")


def _clip(v, n=120):
    s = str(v)
    return s if len(s) <= n else s[: n - 1] + "…"


def _safe_args(args: dict) -> dict:
    out = {}
    for k, v in (args or {}).items():
        out[k] = "***" if any(w in str(k).lower() for w in _SECRET_WORDS) else _clip(v)
    return out


def record(source: str, name: str, args: dict, ok: bool, message: str) -> None:
    line = json.dumps({
        "at": clock.now().isoformat(timespec="seconds"), "source": source, "action": name,
        "args": _safe_args(args), "ok": bool(ok), "message": _clip(message, 160),
    }, ensure_ascii=False)
    with _LOCK:
        try:
            if _FILE.exists() and _FILE.stat().st_size > MAX_BYTES:
                keep = _FILE.read_text(encoding="utf-8").splitlines()[-1500:]
                _FILE.write_text("\n".join(keep) + "\n", encoding="utf-8")
            with _FILE.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass  # logging must never break an action


def recent(limit: int = 50) -> list[dict]:
    with _LOCK:
        try:
            lines = _FILE.read_text(encoding="utf-8").splitlines()[-max(1, limit):]
        except OSError:
            return []
    out = []
    for ln in reversed(lines):
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def summary_text(limit: int = 8) -> str:
    items = recent(200)
    if not items:
        return "I haven't done anything yet."
    today = clock.now().date().isoformat()
    todays = [i for i in items if i["at"].startswith(today)]
    failed = [i for i in todays if not i["ok"]]
    lines = [f"Today I ran {len(todays)} action{'s' if len(todays) != 1 else ''}, {len(failed)} failed."]
    for i in items[:limit]:
        lines.append(f"{i['at'][11:16]} {i['action']} {'ok' if i['ok'] else 'FAILED'}: {i['message']}")
    return "\n".join(lines)
