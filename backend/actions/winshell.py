"""
Runs PowerShell on the Windows side from inside WSL.

The script is sent as a base64 -EncodedCommand, so quotes, $ signs and
backslashes can never break the command.
"""
import base64
import shutil
import subprocess


def available() -> bool:
    return shutil.which("powershell.exe") is not None


def run_ps(script: str, timeout: int = 25) -> tuple[bool, str]:
    exe = shutil.which("powershell.exe")
    if not exe:
        return False, "PowerShell was not found. Nemiii must run inside WSL on Windows to control the PC."
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        p = subprocess.run(
            [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "Windows took too long to answer."
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if p.returncode != 0:
        return False, (err or out or "PowerShell returned an error")[:300]
    return True, out


def ps_quote(s: str) -> str:
    """Make a Python string safe inside a PowerShell single-quoted string."""
    return "'" + str(s).replace("'", "''") + "'"
