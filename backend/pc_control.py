"""
pc_control.py

Executes a *whitelisted* set of actions on the Windows host from inside WSL,
by shelling out to powershell.exe (WSL <-> Windows interop, enabled by default),
or — for dev tooling specifically — directly in WSL, since that's where the
project files and `code` CLI actually live.

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

import requests

import news

TIMEOUT_SECONDS = 10

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

FOLDER_WHITELIST: dict[str, str] = {
    "documents": "Documents",
    "downloads": "Downloads",
    "desktop": "Desktop",
    "pictures": "Pictures",
}

WHATSAPP_DEFAULT_NUMBER = os.environ.get("WHATSAPP_DEFAULT_NUMBER", "")


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
    key = name.lower().strip()
    exe = APP_WHITELIST.get(key)
    if exe:
        return _run_powershell(f"Start-Process '{exe}'")

    safe_name = key.replace("'", "''")
    ps = (
        f"$app = Get-StartApps | Where-Object {{ $_.Name -like '*{safe_name}*' }} | Select-Object -First 1; "
        "if ($app) { Start-Process \"shell:AppsFolder\\$($app.AppID)\"; Write-Output $app.Name } "
        "else { Write-Error 'no matching app found' }"
    )
    result = _run_powershell(ps)
    if not result.ok:
        return ActionResult(False, f"couldn't find an installed app matching '{name}'")
    return ActionResult(True, f"launched {result.message}")


def close_app(name: str) -> ActionResult:
    key = name.lower().strip()
    exe = APP_WHITELIST.get(key)
    if exe and exe.endswith(".exe"):
        proc_name = exe.replace(".exe", "")
        return _run_powershell(f"Stop-Process -Name '{proc_name}' -Force -ErrorAction SilentlyContinue")

    safe_name = key.replace("'", "''")
    ps = (
        f"$procs = Get-Process | Where-Object {{ $_.ProcessName -like '*{safe_name}*' }}; "
        "if ($procs) { $procs | Stop-Process -Force; ($procs | Select-Object -Unique -ExpandProperty ProcessName) -join ', ' } "
        "else { Write-Error 'no matching process found' }"
    )
    result = _run_powershell(ps)
    if not result.ok:
        return ActionResult(False, f"no running process matching '{name}'")
    return ActionResult(True, f"closed: {result.message}")


def open_url(url: str) -> ActionResult:
    if not (url.startswith("http://") or url.startswith("https://")):
        return ActionResult(False, "only http(s) URLs are allowed")
    safe_url = url.replace("'", "")
    return _run_powershell(f"Start-Process '{safe_url}'")


def open_folder(name: str) -> ActionResult:
    subfolder = FOLDER_WHITELIST.get(name.lower().strip())
    if not subfolder:
        return ActionResult(False, f"'{name}' isn't in the folder whitelist")
    return _run_powershell(f"Start-Process (Join-Path $env:USERPROFILE '{subfolder}')")


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


def _send_vk(char_code: str) -> ActionResult:
    ps = (
        "$wshell = New-Object -ComObject WScript.Shell; "
        f"$wshell.SendKeys([char]{char_code})"
    )
    return _run_powershell(ps)


def set_volume(direction: str) -> ActionResult:
    vk_map = {"up": "0xAF", "down": "0xAE", "mute": "0xAD"}
    vk = vk_map.get(direction.lower().strip())
    if not vk:
        return ActionResult(False, "direction must be up, down, or mute")
    return _send_vk(vk)


def media_control(action: str) -> ActionResult:
    vk_map = {"play_pause": "0xB3", "next": "0xB0", "previous": "0xB1", "stop": "0xB2"}
    vk = vk_map.get(action.lower().strip())
    if not vk:
        return ActionResult(False, "action must be play_pause, next, previous, or stop")
    return _send_vk(vk)


def lock_workstation(_: str = "") -> ActionResult:
    return _run_powershell("rundll32.exe user32.dll,LockWorkStation")


def type_text(text: str) -> ActionResult:
    escaped = text.replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.SendKeys]::SendWait('{escaped}')"
    )
    return _run_powershell(ps)


def open_and_type(arg: str) -> ActionResult:
    if "::" not in arg:
        return ActionResult(False, "expected format 'app_name::text to type'")
    app_name, text = arg.split("::", 1)
    app_name, text = app_name.strip(), text.strip()

    open_result = open_app(app_name)
    if not open_result.ok:
        return open_result

    escaped = text.replace("'", "''")
    ps = (
        "Start-Sleep -Milliseconds 1200; "
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.SendKeys]::SendWait('{escaped}')"
    )
    result = _run_powershell(ps)
    if result.ok:
        return ActionResult(True, f"opened {app_name} and typed the text")
    return result


YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def _open_youtube_search(query: str) -> ActionResult:
    safe_query = query.replace("'", "")
    ps = (
        "Add-Type -AssemblyName System.Web; "
        f"$q = [System.Uri]::EscapeDataString('{safe_query}'); "
        "Start-Process \"https://www.youtube.com/results?search_query=$q\""
    )
    result = _run_powershell(ps)
    if result.ok:
        return ActionResult(True, "opened YouTube search results (add YOUTUBE_API_KEY to backend/.env for direct auto-play)")
    return result


def play_youtube(query: str) -> ActionResult:
    if not query.strip():
        return ActionResult(False, "no song/video name given")

    if not YOUTUBE_API_KEY:
        return _open_youtube_search(query)

    try:
        resp = requests.get(
            YOUTUBE_SEARCH_URL,
            params={"part": "snippet", "q": query, "type": "video", "maxResults": 1, "key": YOUTUBE_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except requests.RequestException as e:
        return ActionResult(False, f"YouTube search failed: {e}")

    if not items:
        return ActionResult(False, f"no YouTube results for '{query}'")

    video_id = items[0]["id"]["videoId"]
    title = items[0]["snippet"]["title"]
    result = _run_powershell(f"Start-Process 'https://www.youtube.com/watch?v={video_id}'")
    if result.ok:
        return ActionResult(True, f"playing: {title}")
    return result


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


def minimize_all(_: str = "") -> ActionResult:
    ps = "(New-Object -ComObject Shell.Application).MinimizeAll()"
    return _run_powershell(ps)


def switch_tab(direction: str) -> ActionResult:
    keys = "^{TAB}" if direction.lower().strip() != "previous" else "^+{TAB}"
    ps = (
        "$wshell = New-Object -ComObject WScript.Shell; "
        f"$wshell.SendKeys('{keys}')"
    )
    return _run_powershell(ps)


def copy_selection(_: str = "") -> ActionResult:
    ps = "$wshell = New-Object -ComObject WScript.Shell; $wshell.SendKeys('^c')"
    return _run_powershell(ps)


def paste_clipboard(_: str = "") -> ActionResult:
    ps = "$wshell = New-Object -ComObject WScript.Shell; $wshell.SendKeys('^v')"
    return _run_powershell(ps)


def set_brightness(arg: str) -> ActionResult:
    """
    Adjusts screen brightness via WMI. Only works on laptop displays or
    monitors with DDC/CI support recognized by Windows — external
    monitors without that support will fail, which is a hardware
    limitation, not a bug here.
    """
    direction = arg.strip().lower()
    if direction in ("up", "down"):
        ps = (
            "$b = (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness; "
            f"$new = [Math]::Max(0, [Math]::Min(100, $b {'+ 20' if direction == 'up' else '- 20'})); "
            "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, $new); "
            "Write-Output $new"
        )
    else:
        try:
            level = max(0, min(100, int(direction)))
        except ValueError:
            return ActionResult(False, "brightness must be 'up', 'down', or a number 0-100")
        ps = (
            f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level}); "
            f"Write-Output {level}"
        )

    result = _run_powershell(ps)
    if result.ok:
        return ActionResult(True, f"brightness set to {result.message}%")
    return ActionResult(
        False,
        f"couldn't change brightness (only works on laptop screens or DDC/CI-capable monitors): {result.message}",
    )


def _parse_project_paths() -> dict[str, str]:
    raw = os.environ.get("PROJECT_PATHS", "")
    result: dict[str, str] = {}
    for pair in raw.split(","):
        if "=" in pair:
            name, path = pair.split("=", 1)
            result[name.strip().lower()] = path.strip()
    return result


PROJECT_WHITELIST = _parse_project_paths()

GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "")


def open_project(name: str) -> ActionResult:
    path = PROJECT_WHITELIST.get(name.lower().strip())
    if not path:
        return ActionResult(False, f"'{name}' isn't configured — add it to PROJECT_PATHS in backend/.env")
    try:
        proc = subprocess.run(["code", path], capture_output=True, text=True, timeout=15)
        if proc.returncode == 0:
            return ActionResult(True, f"opened {name} in VS Code")
        return ActionResult(False, proc.stderr.strip() or "failed to open VS Code")
    except FileNotFoundError:
        return ActionResult(False, "'code' command not found in WSL — install the VS Code WSL extension first")
    except subprocess.TimeoutExpired:
        return ActionResult(False, "timed out opening VS Code")


def open_github_repo(name: str) -> ActionResult:
    username = GITHUB_USERNAME
    if not username:
        return ActionResult(False, "No GITHUB_USERNAME configured in backend/.env")
    repo = name.strip().replace(" ", "-")
    url = f"https://github.com/{username}/{repo}"
    return _run_powershell(f"Start-Process '{url}'")


def send_whatsapp_news(phone: str) -> ActionResult:
    number = phone.strip() or WHATSAPP_DEFAULT_NUMBER
    if not number:
        return ActionResult(False, "no phone number given and WHATSAPP_DEFAULT_NUMBER isn't set in backend/.env")

    summary = news.fetch_world_news(limit=5)
    encoded_text = urllib.parse.quote(summary)
    encoded_number = urllib.parse.quote(number.replace(" ", ""))
    link = f"https://wa.me/{encoded_number}?text={encoded_text}"

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
    "open_and_type": open_and_type,
    "send_whatsapp_news": send_whatsapp_news,
    "play_youtube": play_youtube,
    "minimize_all": minimize_all,
    "switch_tab": switch_tab,
    "copy_selection": copy_selection,
    "paste_clipboard": paste_clipboard,
    "set_brightness": set_brightness,
    "open_project": open_project,
    "open_github_repo": open_github_repo,
}


def execute(action_type: str, arg: str = "") -> ActionResult:
    fn = ACTIONS.get(action_type)
    if not fn:
        return ActionResult(False, f"unknown action '{action_type}'")
    return fn(arg)
