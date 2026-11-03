"""
One place that knows what time it is for YOU.

WSL often runs in UTC even when Windows is in India, which would make "remind me at 6 pm" fire at
the wrong time. Your browser tells us its real timezone on every request, and we use that.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import config
import settings


def tz():
    name = config.TIMEZONE or settings.get("tz", "")
    if name:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    return datetime.now().astimezone().tzinfo or timezone.utc


def remember_tz(name: str | None) -> None:
    """Called with the browser's timezone. Ignored if it is not a real zone name."""
    if not name or name == settings.get("tz", ""):
        return
    try:
        ZoneInfo(name)
    except Exception:
        return
    settings.put("tz", name)


def now() -> datetime:
    return datetime.now(tz())
