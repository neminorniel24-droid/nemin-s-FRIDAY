"""
Things Nemiii can do on your Windows PC (through WSL -> powershell.exe).
Every action validates its input and never runs text the model invented.
"""
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import requests

import config
from . import Result, action
from .winshell import available, ps_quote, run_ps

# ------------------------------------------------------------------ helpers
_DENY_CLOSE = {
    "explorer", "system", "svchost", "csrss", "winlogon", "lsass", "services", "wininit",
    "dwm", "smss", "powershell", "wsl", "wslhost", "conhost", "claude", "ollama",
}


def _clean(s, limit: int = 60) -> str:
    return re.sub(r"[^A-Za-z0-9 ._+&'-]", "", str(s or "")).strip()[:limit]


def _ps(script: str, ok_msg: str, timeout: int = 25) -> Result:
    ok, out = run_ps(script, timeout)
    return Result(True, ok_msg) if ok else Result(False, out)


def _open_url(url: str) -> Result:
    u = urlparse(url)
    if u.scheme not in ("http", "https", "steam", "whatsapp", "spotify") or not (u.netloc or u.path):
        return Result(False, "That doesn't look like a safe link.")
    return _ps(f"Start-Process {ps_quote(url)}", "Opened.")


# --------------------------------------------------------------------- apps
APPS = {
    "chrome": "Start-Process chrome",
    "google chrome": "Start-Process chrome",
    "edge": "Start-Process msedge",
    "notepad": "Start-Process notepad",
    "calculator": "Start-Process calc",
    "calc": "Start-Process calc",
    "paint": "Start-Process mspaint",
    "file explorer": "Start-Process explorer",
    "explorer": "Start-Process explorer",
    "settings": "Start-Process ms-settings:",
    "terminal": "Start-Process wt",
    "task manager": "Start-Process taskmgr",
    "command prompt": "Start-Process cmd",
    "cmd": "Start-Process cmd",
    "powershell": "Start-Process powershell",
    "word": "Start-Process winword",
    "excel": "Start-Process excel",
    "powerpoint": "Start-Process powerpnt",
    "snipping tool": "Start-Process snippingtool",
    "camera": "Start-Process microsoft.windows.camera:",
    "whatsapp": "Start-Process whatsapp:",
    "spotify": "Start-Process spotify:",
    "steam": "Start-Process steam:",
}
# Steam games start straight from their Steam id.
STEAM_GAMES = {"pubg": 578080, "pubg battlegrounds": 578080, "cs2": 730, "counter strike": 730,
               "counter strike 2": 730, "dota 2": 570, "dota": 570, "gta 5": 271590, "gta v": 271590}


@action("open_app", "pc", 'Open any installed program or game. args: {"name": "chrome" | "steam" | "pubg" | "vs code" ...}')
def open_app(a: dict) -> Result:
    name = _clean(a.get("name"))
    if not name:
        return Result(False, "Which app should I open?")
    key = name.lower()
    if key in STEAM_GAMES:
        return _ps(f"Start-Process 'steam://rungameid/{STEAM_GAMES[key]}'", f"Starting {name} through Steam.")
    if key in APPS:
        return _ps(APPS[key], f"Opening {name}.")
    # Anything else: search the Start Menu list of installed apps.
    script = (
        f"$n = {ps_quote(name)}\n"
        "$a = Get-StartApps | Where-Object { $_.Name -like \"*$n*\" } | Select-Object -First 1\n"
        "if ($a) { Start-Process ('shell:AppsFolder\\' + $a.AppID); 'OK:' + $a.Name } else { 'NOTFOUND' }"
    )
    ok, out = run_ps(script)
    if not ok:
        return Result(False, out)
    if "NOTFOUND" in out:
        return Result(False, f"I couldn't find an app called {name} on this PC.")
    return Result(True, f"Opening {out.replace('OK:', '').strip() or name}.")


@action("close_app", "pc", 'Close a running program politely. args: {"name": "chrome"}')
def close_app(a: dict) -> Result:
    name = _clean(a.get("name"))
    key = name.lower().replace(" ", "")
    aliases = {"vscode": "Code", "visualstudiocode": "Code", "googlechrome": "chrome", "whatsapp": "WhatsApp"}
    proc = aliases.get(key, name.replace(" ", ""))
    if not proc or proc.lower() in _DENY_CLOSE:
        return Result(False, "I won't close that one.")
    script = (
        f"$n = {ps_quote(proc)}\n"
        "$p = Get-Process | Where-Object { $_.ProcessName -like \"*$n*\" -and $_.MainWindowHandle -ne 0 }\n"
        "if (-not $p) { 'NONE' } else { $p | ForEach-Object { $_.CloseMainWindow() | Out-Null }; 'CLOSED' }"
    )
    ok, out = run_ps(script)
    if not ok:
        return Result(False, out)
    return Result(True, f"Closed {name}.") if "CLOSED" in out else Result(False, f"{name} doesn't seem to be open.")


# ---------------------------------------------------------------- web/media
@action("open_url", "pc", 'Open a web address. args: {"url": "https://..."}')
def open_url(a: dict) -> Result:
    url = str(a.get("url", "")).strip()
    # "javascript:", "file:", "ms-msdt:" and every other scheme are refused: web links only.
    if re.match(r"^[a-z][a-z0-9+.-]*:(?!//)(?!\d)", url, re.I) or re.match(r"^(?!https?://)[a-z][a-z0-9+.-]*://", url, re.I):
        return Result(False, "I only open normal web links.")
    if url and not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return _open_url(url)


@action("search_web", "pc", 'Search Google in the browser. args: {"query": "..."}')
def search_web(a: dict) -> Result:
    q = str(a.get("query", "")).strip()
    if not q:
        return Result(False, "What should I search for?")
    r = _open_url("https://www.google.com/search?q=" + quote_plus(q))
    return Result(True, f"Searching for {q}.") if r.ok else r


@action("play_youtube", "pc", 'Play a song or video on YouTube. args: {"query": "song or video name"}')
def play_youtube(a: dict) -> Result:
    q = str(a.get("query", "")).strip()
    if not q:
        return Result(False, "What should I play?")
    url = "https://www.youtube.com/results?search_query=" + quote_plus(q)
    if config.YOUTUBE_API_KEY:
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
                "part": "snippet", "q": q, "type": "video", "maxResults": 1, "key": config.YOUTUBE_API_KEY,
            }, timeout=8)
            items = r.json().get("items", [])
            if items:
                url = "https://www.youtube.com/watch?v=" + items[0]["id"]["videoId"]
        except Exception:
            pass  # fall back to the search page
    r = _open_url(url)
    return Result(True, f"Playing {q}.") if r.ok else r


@action("media_control", "pc", 'Control music/video playback. args: {"command": "play_pause" | "next" | "previous" | "stop"}')
def media_control(a: dict) -> Result:
    keys = {"play_pause": 179, "pause": 179, "play": 179, "next": 176, "previous": 177, "stop": 178}
    cmd = str(a.get("command", "")).lower()
    if cmd not in keys:
        return Result(False, "I can play, pause, skip or go back.")
    return _ps(f"(New-Object -ComObject WScript.Shell).SendKeys([char]{keys[cmd]})", "Done.")


@action("set_volume", "pc", 'Change the sound. args: {"level": 0-100} or {"change": "up" | "down" | "mute"}')
def set_volume(a: dict) -> Result:
    shell = "$w = New-Object -ComObject WScript.Shell\n"
    if a.get("level") is not None:
        level = max(0, min(100, int(float(a["level"]))))
        steps = round(level / 2)  # each key press is 2 percent
        script = shell + "1..50 | ForEach-Object { $w.SendKeys([char]174) }\n" + (
            f"1..{steps} | ForEach-Object {{ $w.SendKeys([char]175) }}" if steps else "")
        return _ps(script, f"Volume set to {level} percent.", timeout=40)
    change = str(a.get("change", "")).lower()
    codes = {"up": 175, "down": 174, "mute": 173}
    if change not in codes:
        return Result(False, "Should I turn it up, down, or mute it?")
    reps = 5 if change != "mute" else 1
    return _ps(shell + f"1..{reps} | ForEach-Object {{ $w.SendKeys([char]{codes[change]}) }}", "Done.")


@action("set_brightness", "pc", 'Screen brightness (laptops). args: {"level": 0-100}')
def set_brightness(a: dict) -> Result:
    level = max(0, min(100, int(float(a.get("level", 50)))))
    return _ps(
        f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})",
        f"Brightness set to {level} percent.")


# ----------------------------------------------------------------- the desk
_FOLDERS = {
    "downloads": "(New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path",
    "documents": "[Environment]::GetFolderPath('MyDocuments')",
    "desktop": "[Environment]::GetFolderPath('Desktop')",
    "pictures": "[Environment]::GetFolderPath('MyPictures')",
    "music": "[Environment]::GetFolderPath('MyMusic')",
    "videos": "[Environment]::GetFolderPath('MyVideos')",
}


@action("open_folder", "pc", 'Open a common folder. args: {"name": "downloads" | "documents" | "desktop" | "pictures" | "music" | "videos"}')
def open_folder(a: dict) -> Result:
    name = str(a.get("name", "")).lower().strip()
    if name not in _FOLDERS:
        return Result(False, "I can open downloads, documents, desktop, pictures, music or videos.")
    return _ps(f"$p = {_FOLDERS[name]}\nStart-Process explorer.exe $p", f"Opening your {name} folder.")


@action("screenshot", "pc", "Take a screenshot and save it in Pictures. args: {}")
def screenshot(a: dict) -> Result:
    script = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing\n"
        "$b = [System.Windows.Forms.SystemInformation]::VirtualScreen\n"
        "$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height\n"
        "$g = [System.Drawing.Graphics]::FromImage($bmp)\n"
        "$g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)\n"
        "$f = Join-Path ([Environment]::GetFolderPath('MyPictures')) ('Nemiii-' + (Get-Date -Format yyyyMMdd-HHmmss) + '.png')\n"
        "$bmp.Save($f); $g.Dispose(); $bmp.Dispose(); $f"
    )
    ok, out = run_ps(script, 30)
    return Result(True, "Screenshot saved in your Pictures folder.") if ok else Result(False, out)


@action("lock_pc", "pc", "Lock the computer. args: {}")
def lock_pc(a: dict) -> Result:
    return _ps("rundll32.exe user32.dll,LockWorkStation", "Locking your PC.")


@action("minimize_all", "pc", "Minimise every window (show the desktop). args: {}")
def minimize_all(a: dict) -> Result:
    return _ps("(New-Object -ComObject Shell.Application).MinimizeAll()", "Done.")


@action("restore_windows", "pc", "Bring back the windows that were minimised. args: {}")
def restore_windows(a: dict) -> Result:
    return _ps("(New-Object -ComObject Shell.Application).UndoMinimizeAll()", "Done.")


@action("switch_tab", "pc", 'Switch browser tab. args: {"direction": "next" | "previous"}')
def switch_tab(a: dict) -> Result:
    keys = "^{TAB}" if str(a.get("direction", "next")).lower() == "next" else "^+{TAB}"
    return _ps(f"(New-Object -ComObject WScript.Shell).SendKeys({ps_quote(keys)})", "Done.")


@action("copy_selection", "pc", "Copy whatever is selected (Ctrl+C). args: {}")
def copy_selection(a: dict) -> Result:
    return _ps("(New-Object -ComObject WScript.Shell).SendKeys('^c')", "Copied.")


@action("paste_clipboard", "pc", "Paste (Ctrl+V). args: {}")
def paste_clipboard(a: dict) -> Result:
    return _ps("(New-Object -ComObject WScript.Shell).SendKeys('^v')", "Pasted.")


def _type_script(text: str, switch_window: bool) -> str:
    # Put the text on the clipboard and paste it: handles every character safely.
    pre = "$w.SendKeys('%{TAB}'); Start-Sleep -Milliseconds 700\n" if switch_window else ""
    return f"$w = New-Object -ComObject WScript.Shell\nSet-Clipboard -Value {ps_quote(text)}\n{pre}$w.SendKeys('^v')"


@action("type_text", "pc", 'Type text into the window you were just using. args: {"text": "..."}')
def type_text(a: dict) -> Result:
    text = str(a.get("text", ""))
    if not text:
        return Result(False, "What should I type?")
    return _ps(_type_script(text[:2000], switch_window=True), "Typed it.")


@action("open_and_type", "pc", 'Open an app, then type text in it. args: {"app": "notepad", "text": "..."}')
def open_and_type(a: dict) -> Result:
    opened = open_app({"name": a.get("app")})
    if not opened.ok:
        return opened
    time.sleep(2.5)
    return _ps(_type_script(str(a.get("text", ""))[:2000], switch_window=False), f"Typed it in {a.get('app')}.")


@action("whatsapp_message", "pc",
        'Open WhatsApp with a message ready to send (you press send). args: {"text": "...", "number": "optional digits with country code"}')
def whatsapp_message(a: dict) -> Result:
    number = re.sub(r"\D", "", str(a.get("number") or config.WHATSAPP_DEFAULT_NUMBER))
    text = str(a.get("text", "")).strip()
    if not text:
        return Result(False, "What should the message say?")
    base = f"https://wa.me/{number}" if number else "https://wa.me/"
    r = _open_url(f"{base}?text={quote_plus(text)}")
    return Result(True, "WhatsApp is open with your message ready. Press send when you're happy with it.") if r.ok else r


# ----------------------------------------------------------------- projects
@action("open_project", "pc", 'Open a coding project in VS Code. args: {"name": "<project name>"}')
def open_project(a: dict) -> Result:
    name = str(a.get("name", "")).lower().strip()
    paths = config.project_paths()
    path = paths.get(name) or next((p for k, p in paths.items() if name and name in k), None)
    if not path or not Path(path).exists():
        known = ", ".join(paths) or "none set"
        return Result(False, f"I don't know a project called {name}. Known projects: {known}.")
    try:
        subprocess.Popen(["code", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return Result(False, "VS Code's 'code' command isn't available inside WSL.")
    return Result(True, f"Opening {name} in VS Code.")


@action("open_github_repo", "pc", 'Open one of your GitHub repositories in the browser. args: {"name": "repo-name"}')
def open_github_repo(a: dict) -> Result:
    repo = _clean(a.get("name")).replace(" ", "-")
    if not config.GITHUB_USERNAME or not repo:
        return Result(False, "I need your GitHub username and a repository name.")
    r = _open_url(f"https://github.com/{config.GITHUB_USERNAME}/{repo}")
    return Result(True, f"Opening {repo} on GitHub.") if r.ok else r


__all__ = ["available"]
