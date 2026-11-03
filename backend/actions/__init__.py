"""
Action registry.

An "action" is one thing Nemiii is allowed to do. The language model can ONLY
pick from this list, with arguments we validate. It can never run free-form
commands, so a misheard sentence cannot damage your PC.

  kind="pc"   -> does something on the computer; reply is a short confirmation
  kind="info" -> fetches facts; the result is handed back to the model, which
                 then says it out loud in its own words
"""
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import activity


@dataclass
class Action:
    name: str
    kind: str          # "pc" or "info"
    help: str          # one line shown to the language model
    fn: Callable[[dict], "Result"]
    risky: "bool | Callable[[dict], bool]" = False   # True = she must ask you to confirm first
    describe: Callable[[dict], str] | None = None  # "close Chrome" (used when asking to confirm)


@dataclass
class Result:
    ok: bool
    message: str       # pc: confirmation / error.  info: the facts to speak.
    ui: dict | None = None   # optional change for the screen, e.g. {"theme": "red"}


REGISTRY: dict[str, Action] = {}


def action(name: str, kind: str, help: str, risky: "bool | Callable[[dict], bool]" = False, describe: Callable[[dict], str] | None = None):
    def deco(fn):
        REGISTRY[name] = Action(name, kind, help, fn, risky, describe)
        return fn
    return deco


def describe(name: str, args: dict | None) -> str:
    """Plain words for what an action would do, e.g. 'close Chrome'."""
    act = REGISTRY.get(name)
    if act and act.describe:
        try:
            return act.describe(args or {})
        except Exception:
            pass
    return name.replace("_", " ")


def is_risky(name: str, args: dict | None = None) -> bool:
    act = REGISTRY.get(name)
    if not act:
        return False
    return bool(act.risky(args or {})) if callable(act.risky) else bool(act.risky)


def help_text() -> str:
    return "\n".join(f"- {a.name}: {a.help}" for a in REGISTRY.values())


def run(name: str, args: dict | None, source: str = "chat") -> Result:
    act = REGISTRY.get(name)
    if act is None:
        res = Result(False, f"I don't have an action called {name}.")
    else:
        try:
            res = act.fn(args or {})
        except Exception as e:  # never let one action crash the server
            res = Result(False, f"That action failed: {str(e)[:160]}")
    activity.record(source, name, args or {}, res.ok, res.message)  # everything she does is logged
    return res


def kind_of(name: str) -> str | None:
    act = REGISTRY.get(name)
    return act.kind if act else None


# Importing these modules fills REGISTRY.
from . import pc, info, tasks, files, system, security, home, ui, studio_actions  # noqa: E402,F401


def load_plugins() -> list[str]:
    """Load every backend/plugins/*.py (files starting with _ are skipped). One bad plugin never stops the rest."""
    loaded = []
    folder = Path(__file__).resolve().parent.parent / "plugins"
    if not folder.is_dir():
        return loaded
    for f in sorted(folder.glob("*.py")):
        if f.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"nemiii_plugin_{f.stem}", f)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)  # the plugin registers itself with @action
            loaded.append(f.stem)
        except Exception as e:  # noqa: BLE001
            print(f"[plugins] {f.name} failed to load: {e}")
    return loaded


PLUGINS = load_plugins()
