"""
Reminders, timers and alarms. Saved in backend/data/reminders.json so they survive restarts.

The page asks /reminders/due every few seconds and she speaks them. If the page is closed, a
background thread in the backend shows a Windows notification instead (see sweep()).
"""
import json
import re
import threading
import uuid
from datetime import datetime, timedelta

import clock
from config import DATA_DIR

_FILE = DATA_DIR / "reminders.json"
_LOCK = threading.Lock()
GRACE_SECONDS = 20  # the page gets this long to say it out loud before we fall back to a notification


def _load() -> list[dict]:
    try:
        d = json.loads(_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    tmp = _FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items[-200:], ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_FILE)


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


# ------------------------------------------------------------- understanding times
def parse_when(args: dict, now: datetime | None = None) -> datetime | None:
    """
    Accepts  {"seconds": 90} {"minutes": 20} {"hours": 2}  or  {"at": "18:30"}  {"at": "6:30 pm"}
    {"at": "2026-11-02 09:00"}  {"at": "tomorrow 7:00"}. Returns None if it cannot tell.
    """
    now = now or clock.now()
    total = 0.0
    for key, mult in (("seconds", 1), ("minutes", 60), ("hours", 3600), ("days", 86400)):
        try:
            v = float(args.get(key) or 0)
        except (TypeError, ValueError):
            v = 0
        total += v * mult
    if total > 0:
        return now + timedelta(seconds=total)

    at = str(args.get("at") or args.get("time") or "").strip().lower()
    if not at:
        return None
    day = now.date()
    if at.startswith("tomorrow"):
        day = day + timedelta(days=1)
        at = at[len("tomorrow"):].strip(" ,")
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[ t]+(.+)$", at)
    explicit_day = False
    if m:
        try:
            day = datetime(int(m[1]), int(m[2]), int(m[3])).date()
        except ValueError:
            return None
        at, explicit_day = m[4].strip(), True
    t = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", at)
    if not t:
        return None
    hour, minute, ampm = int(t[1]), int(t[2] or 0), t[3]
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    due = datetime(day.year, day.month, day.day, hour, minute, tzinfo=now.tzinfo)
    if due <= now and not explicit_day and not str(args.get("at", "")).lower().startswith("tomorrow"):
        due += timedelta(days=1)  # "at 7:00" said at 9 pm means tomorrow 7:00
    return due


# ------------------------------------------------------------------- the list
def add(text: str, due: datetime, repeat: str = "") -> dict:
    item = {"id": uuid.uuid4().hex[:8], "text": text.strip()[:200] or "Reminder", "due": due.isoformat(timespec="seconds"),
            "repeat": "daily" if repeat == "daily" else "", "status": "pending", "delivered": False,
            "created": clock.now().isoformat(timespec="seconds")}
    with _LOCK:
        items = _load()
        items.append(item)
        _save(items)
    return item


def upcoming() -> list[dict]:
    with _LOCK:
        items = [i for i in _load() if i["status"] == "pending"]
    return sorted(items, key=lambda i: i["due"])


def today(now: datetime | None = None) -> list[dict]:
    now = now or clock.now()
    return [i for i in upcoming() if _dt(i["due"]).date() == now.date()]


def cancel(keyword: str) -> int:
    kw = keyword.strip().lower()
    with _LOCK:
        items = _load()
        n = 0
        for i in items:
            if i["status"] == "pending" and (kw in i["text"].lower() or kw == i["id"] or kw in ("all", "everything")):
                i["status"] = "cancelled"
                n += 1
        _save(items)
    return n


def cancel_id(rid: str) -> bool:
    with _LOCK:
        items = _load()
        hit = False
        for i in items:
            if i["id"] == rid and i["status"] == "pending":
                i["status"] = "cancelled"
                hit = True
        _save(items)
    return hit


def take_due(now: datetime | None = None, older_than: float = 0.0) -> list[dict]:
    """Return reminders whose time has come and mark them delivered (daily ones are re-armed for tomorrow)."""
    now = now or clock.now()
    out = []
    with _LOCK:
        items = _load()
        for i in items:
            if i["status"] != "pending" or i["delivered"]:
                continue
            due = _dt(i["due"])
            if due <= now and (now - due).total_seconds() >= older_than:
                out.append(dict(i))
                if i["repeat"] == "daily":
                    nxt = due
                    while nxt <= now:
                        nxt += timedelta(days=1)
                    i["due"] = nxt.isoformat(timespec="seconds")
                else:
                    i["status"], i["delivered"] = "fired", True
        _save(items)
    return out


def sweep(notify, now: datetime | None = None) -> int:
    """Background check: anything overdue that the page never delivered gets a notification."""
    due = take_due(now, older_than=GRACE_SECONDS)
    for i in due:
        try:
            notify("Nemiii reminder", i["text"])
        except Exception:
            pass
    return len(due)


def pretty(i: dict, now: datetime | None = None) -> str:
    now = now or clock.now()
    d = _dt(i["due"])
    when = d.strftime("%I:%M %p").lstrip("0")
    if d.date() == now.date():
        day = "today"
    elif d.date() == (now + timedelta(days=1)).date():
        day = "tomorrow"
    else:
        day = d.strftime("%A %d %B")
    return f"{i['text']} at {when} {day}" + (" (every day)" if i["repeat"] else "")
