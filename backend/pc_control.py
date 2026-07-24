"""
pc_control.py

Executes a *whitelisted* set of actions on the Windows host from inside WSL,
by shelling out to powershell.exe (WSL <-> Windows interop, enabled by default).

Design principle: the LLM never gets to run arbitrary shell text. It can only
select one of the ACTIONS below and supply the specific argument that action
expects. This keeps "voice control your PC" from turning into "voice-controlled
remote code execution."
"""

from __future__ import annotations

import os
import subprocess
import urllib.parse
from dataclasses import dataclass
from typing import Callable

import news

TIMEOUT_SECONDS = 10

WHATSAPP_DEFAULT_NUMBER = os.environ.get("WHATSAPP_DEFAULT_NUMBER", "")

# Apps you're willing to let the assistant launch by name.
# Add more entries as you need them — key is what the LLM will say,
# value is what Windows actually runs.
APP_WHITELIST: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "firefox": "firefox.exe",
    "explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "settings": "ms-settings:",
    "task_manager": "taskmgr.exe",
    "vscode": "code",
    "spotify": "spotify.exe",
    "camera": "microsoft.windows.camera:",
    "photos": "ms-photos:",
    "store": "ms-windows-store:",
    "terminal": "wt.exe",
    "whatsapp": "whatsapp://",
}

# Common folders — key is what the LLM will say, value is a PowerShell
# expression that resolves to the path (kept as literal env-var refs so we
# never interpolate a user-supplied path directly).
FOLDER_WHITELIST: dict[str, str] = {
    "documents": "$env:USERPROFILE\\Documents",
    "downloads": "$env:USERPROFILE\\Downloads",
    "desktop": "$env:USERPROFILE\\Desktop",
    "pictures": "$env:USERPROFILE\\Pictures",
}


@dataclass
class ActionResult:
    ok: bool
    message: str


def _run_powershell(command: str, timeout: int = TIMEOUT_SECONDS) -> ActionResult:
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode == 0:
            return ActionResult(True, proc.stdout.strip() or "done")
        return ActionResult(False, proc.stderr.strip() or f"exit code {proc.returncode}")
    except FileNotFoundError:
        return ActionResult(
            False,
            "powershell.exe not found — is this running inside WSL with interop enabled?",
        )
    except subprocess.TimeoutExpired:
        return ActionResult(False, "command timed out")


def open_app(name: str) -> ActionResult:
    exe = APP_WHITELIST.get(name.lower().strip())
    if not exe:
        return ActionResult(False, f"'{name}' isn't in the app whitelist")
    return _run_powershell(f"Start-Process '{exe}'")


def open_url(url: str) -> ActionResult:
    if not (url.startswith("http://") or url.startswith("https://")):
        return ActionResult(False, "only http(s) URLs are allowed")
    # Escape single quotes defensively before interpolating into PowerShell.
    safe_url = url.replace("'", "")
    return _run_powershell(f"Start-Process '{safe_url}'")


def take_screenshot(_: str = "") -> ActionResult:
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
        "$b = [System.Windows.Forms.SystemInformation]::VirtualScreen; "
        "$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height; "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
        "$path = Join-Path $env:USERPROFILE 'Pictures\\friday_screenshot.png'; "
        "$bmp.Save($path); "
        "Write-Output $path"
    )
    return _run_powershell(ps, timeout=15)


def set_volume(direction: str) -> ActionResult:
    direction = direction.lower().strip()
    key_map = {
        "up": "([char]175)",
        "down": "([char]174)",
        "mute": "([char]173)",
    }
    key = key_map.get(direction)
    if not key:
        return ActionResult(False, "direction must be up, down, or mute")
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.SendKeys]::SendWait({key})"
    )
    return _run_powershell(ps)


def lock_workstation(_: str = "") -> ActionResult:
    return _run_powershell("rundll32.exe user32.dll,LockWorkStation")


def type_text(text: str) -> ActionResult:
    # Sent to whatever window currently has focus on the Windows host.
    escaped = text.replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.SendKeys]::SendWait('{escaped}')"
    )
    return _run_powershell(ps)


def close_app(name: str) -> ActionResult:
    exe = APP_WHITELIST.get(name.lower().strip())
    if not exe:
        return ActionResult(False, f"'{name}' isn't in the app whitelist")
    # Strip a trailing ':' (URI-scheme style entries like ms-settings: aren't processes)
    proc_name = exe.replace(".exe", "").rstrip(":")
    if not exe.endswith(".exe"):
        return ActionResult(False, f"'{name}' isn't a closeable process")
    return _run_powershell(f"Stop-Process -Name '{proc_name}' -Force -ErrorAction SilentlyContinue")


def open_folder(name: str) -> ActionResult:
    path_expr = FOLDER_WHITELIST.get(name.lower().strip())
    if not path_expr:
        return ActionResult(False, f"'{name}' isn't in the folder whitelist")
    return _run_powershell(f"Start-Process '{path_expr}'")


def search_web(query: str) -> ActionResult:
    if not query.strip():
        return ActionResult(False, "no search query given")
    safe_query = query.replace("'", "")
    ps = (
        "Add-Type -AssemblyName System.Web; "
        f"$q = [System.Uri]::EscapeDataString('{safe_query}'); "
        "Start-Process \"https://www.google.com/search?q=$q\""
    )
    return _run_powershell(ps)


def media_control(action: str) -> ActionResult:
    key_map = {
        "play_pause": "([char]179)",
        "next": "([char]176)",
        "previous": "([char]177)",
        "stop": "([char]178)",
    }
    key = key_map.get(action.lower().strip())
    if not key:
        return ActionResult(False, "action must be play_pause, next, previous, or stop")
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.SendKeys]::SendWait({key})"
    )
    return _run_powershell(ps)


def send_whatsapp_news(phone: str) -> ActionResult:
    number = phone.strip() or WHATSAPP_DEFAULT_NUMBER
    if not number:
        return ActionResult(
            False,
            "no phone number given and WHATSAPP_DEFAULT_NUMBER isn't set in backend/.env",
        )

    summary = news.fetch_world_news(limit=5)
    encoded_text = urllib.parse.quote(summary)
    encoded_number = urllib.parse.quote(number.replace(" ", ""))
    link = f"https://wa.me/{encoded_number}?text={encoded_text}"

    # Opens the chat with the message pre-filled. Deliberately does NOT
    # auto-press send — WhatsApp's load time varies too much to reliably
    # time a scripted Enter keypress, and auto-sending an unreviewed
    # message is worth avoiding. Review it, then hit send yourself.
    result = _run_powershell(f"Start-Process '{link}'")
    if result.ok:
        return ActionResult(True, f"Opened WhatsApp chat with {number}, news pre-filled — review and hit send.")
    return result


ACTIONS: dict[str, Callable[[str], ActionResult]] = {
    "open_app": open_app,
    "close_app": close_app,
    "open_url": open_url,
    "open_folder": open_folder,
    "search_web": search_web,
    "screenshot": take_screenshot,
    "set_volume": set_volume,
    "media_control": media_control,
    "lock": lock_workstation,
    "type_text": type_text,
    "send_whatsapp_news": send_whatsapp_news,
}


def execute(action_type: str, arg: str = "") -> ActionResult:
    fn = ACTIONS.get(action_type)
    if not fn:
        return ActionResult(False, f"unknown action '{action_type}'")
    return fn(arg)
