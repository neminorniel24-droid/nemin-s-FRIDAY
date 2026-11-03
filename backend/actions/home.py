"""
Smart home through Home Assistant (optional). Lights, switches, fans, covers and scenes only.
Doors, locks and alarms are deliberately left out. Set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN in backend/.env.
"""
import requests

import config
from . import Result, action

DOMAINS = ("light", "switch", "fan", "cover", "scene", "input_boolean")


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.HOME_ASSISTANT_TOKEN}", "Content-Type": "application/json"}


def _configured() -> bool:
    return bool(config.HOME_ASSISTANT_URL and config.HOME_ASSISTANT_TOKEN)


def _states() -> list[dict]:
    r = requests.get(config.HOME_ASSISTANT_URL + "/api/states", headers=_headers(), timeout=8)
    r.raise_for_status()
    return [s for s in r.json() if s["entity_id"].split(".")[0] in DOMAINS]


def _find(states: list[dict], name: str) -> dict | None:
    words = [w for w in name.lower().replace("the ", "").split() if w]
    for s in states:
        friendly = str(s.get("attributes", {}).get("friendly_name", s["entity_id"])).lower()
        if words and all(w in friendly or w in s["entity_id"] for w in words):
            return s
    return None


@action("home_devices", "info", "List your smart-home lights, switches and fans and whether they are on. args: {}")
def home_devices(a: dict) -> Result:
    if not _configured():
        return Result(False, "Smart home isn't set up. Add HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN in backend/.env.")
    st = _states()
    if not st:
        return Result(True, "Home Assistant has no lights or switches I can use.")
    return Result(True, "Devices: " + "; ".join(
        f"{s.get('attributes', {}).get('friendly_name', s['entity_id'])} is {s['state']}" for s in st[:15]))


@action("home_control", "pc",
        'Control a smart-home device. args: {"name": "bedroom light", "command": "on" | "off" | "toggle" | "open" | "close"}')
def home_control(a: dict) -> Result:
    if not _configured():
        return Result(False, "Smart home isn't set up. Add HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN in backend/.env.")
    name, cmd = str(a.get("name", "")).strip(), str(a.get("command", "")).lower().strip()
    dev = _find(_states(), name)
    if not dev:
        return Result(False, f"I couldn't find a device called {name}.")
    domain = dev["entity_id"].split(".")[0]
    if domain == "cover":
        service = {"open": "open_cover", "close": "close_cover", "on": "open_cover", "off": "close_cover"}.get(cmd)
    elif domain == "scene":
        service = "turn_on"
    else:
        service = {"on": "turn_on", "off": "turn_off", "toggle": "toggle"}.get(cmd)
    if not service:
        return Result(False, "Should I turn it on, off, or toggle it?")
    r = requests.post(f"{config.HOME_ASSISTANT_URL}/api/services/{domain}/{service}",
                      headers=_headers(), json={"entity_id": dev["entity_id"]}, timeout=8)
    if not r.ok:
        return Result(False, f"Home Assistant said no ({r.status_code}).")
    label = dev.get("attributes", {}).get("friendly_name", dev["entity_id"])
    return Result(True, f"Done. {label}: {cmd}.")
