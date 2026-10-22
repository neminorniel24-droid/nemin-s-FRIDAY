"""
Action registry.

An "action" is one thing Nemiii is allowed to do. The language model can ONLY
pick from this list, with arguments we validate. It can never run free-form
commands, so a misheard sentence cannot damage your PC.

  kind="pc"   -> does something on the computer; reply is a short confirmation
  kind="info" -> fetches facts; the result is handed back to the model, which
                 then says it out loud in its own words
"""
from dataclasses import dataclass
from typing import Callable


@dataclass
class Action:
    name: str
    kind: str          # "pc" or "info"
    help: str          # one line shown to the language model
    fn: Callable[[dict], "Result"]


@dataclass
class Result:
    ok: bool
    message: str       # pc: confirmation / error.  info: the facts to speak.


REGISTRY: dict[str, Action] = {}


def action(name: str, kind: str, help: str):
    def deco(fn):
        REGISTRY[name] = Action(name, kind, help, fn)
        return fn
    return deco


def help_text() -> str:
    return "\n".join(f"- {a.name}: {a.help}" for a in REGISTRY.values())


def run(name: str, args: dict | None) -> Result:
    act = REGISTRY.get(name)
    if act is None:
        return Result(False, f"I don't have an action called {name}.")
    try:
        return act.fn(args or {})
    except Exception as e:  # never let one action crash the server
        return Result(False, f"That action failed: {str(e)[:160]}")


def kind_of(name: str) -> str | None:
    act = REGISTRY.get(name)
    return act.kind if act else None


# Importing these modules fills REGISTRY.
from . import pc, info  # noqa: E402,F401
