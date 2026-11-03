"""
Fast, reliable intents that do NOT need the language model: confirmations, switching her mode,
changing the theme and the morning briefing. Everything else goes to the model.
"""
import re

import personas
from actions import ui

YES = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed", "proceed", "affirmative",
       "do it", "go ahead", "yes please", "please do", "yes do it", "ok do it", "okay do it", "sure do it"}
NO = {"no", "nope", "nah", "cancel", "stop", "abort", "negative", "never mind", "nevermind", "dont", "don't",
      "do not", "no thanks", "no thank you", "leave it", "forget it"}
BRIEFING = {"good morning", "morning briefing", "daily briefing", "brief me", "give me the briefing", "give me my briefing",
            "start my day", "status report", "morning report", "daily report", "what's my day", "whats my day"}

_NAMES = "jarvis|friday|edith|nemiii|nemi"
PERSONA_RE = re.compile(rf"\b(?:switch|change|go|swap|turn|activate|enable|use|become|be|call)\b(?: back)?(?: to| into)?(?: the)?\s+({_NAMES})\b(?: mode)?")
PERSONA_ONLY_RE = re.compile(rf"^({_NAMES}) mode$")
THEME_WORDS = "peacock|teal|green|red alert|red|alert|gold|yellow|amber|ice|blue"
THEME_RE = re.compile(rf"\b(?:theme|colou?rs?)\b(?: to| as)?\s+({THEME_WORDS})\b|\b(?:switch|change|go) to\s+({THEME_WORDS})\s+(?:theme|colou?rs?|mode)\b|^({THEME_WORDS}) theme$|^red alert$")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", s.lower())).strip()


def classify(text: str, has_pending: bool) -> dict | None:
    t = norm(text)
    if not t:
        return None
    if has_pending:
        if t in YES or any(t.startswith(y + " ") for y in ("yes", "yeah", "sure", "okay", "ok")) and len(t) < 25:
            return {"type": "yes"}
        if t in NO or any(t.startswith(n + " ") for n in ("no", "nope", "cancel")) and len(t) < 25:
            return {"type": "no"}
    m = PERSONA_RE.search(t) or PERSONA_ONLY_RE.match(t)
    if m:
        return {"type": "persona", "mode": m.group(1)}
    if t == "red alert":
        return {"type": "theme", "theme": "red"}
    m = THEME_RE.search(t)
    if m:
        word = next(g for g in m.groups() if g)
        key = ui.theme_key(word)
        if key:
            return {"type": "theme", "theme": key}
    if t in BRIEFING or t.startswith("good morning"):
        return {"type": "briefing"}
    return None


def persona_for_name(word: str) -> str | None:
    """'jarvis' -> 'jarvis'. Used when you call her by that name."""
    w = (word or "").lower().strip()
    if w in ("nemi",):
        w = "nemiii"
    return w if w in personas.PERSONAS else None
