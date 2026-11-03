"""Changes to the screen itself: her personality and the colour theme. The page applies the `ui` part."""
import personas
from . import Result, action

THEMES = {"peacock": "peacock", "teal": "peacock", "green": "peacock",
          "red": "red", "alert": "red", "red alert": "red",
          "gold": "gold", "yellow": "gold", "amber": "gold",
          "ice": "ice", "blue": "ice"}


def theme_key(word: str) -> str | None:
    return THEMES.get((word or "").lower().strip())


@action("set_persona", "pc", 'Change her personality. args: {"mode": "jarvis" | "friday" | "edith" | "nemiii"}')
def set_persona(a: dict) -> Result:
    p = personas.set_current(str(a.get("mode", "")))
    if not p:
        return Result(False, "I know four modes: Nemiii, Jarvis, Friday and Edith.")
    return Result(True, personas.fill(p.greeting), ui={"persona": personas.info(p)})


@action("set_theme", "pc", 'Change the screen colours. args: {"theme": "peacock" | "red" | "gold" | "ice"}')
def set_theme(a: dict) -> Result:
    key = theme_key(str(a.get("theme", "")))
    if not key:
        return Result(False, "I have peacock, red, gold and ice.")
    import settings
    settings.put("theme", key)
    return Result(True, f"Theme changed to {key}.", ui={"theme": key})
