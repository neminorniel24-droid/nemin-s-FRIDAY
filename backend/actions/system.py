"""PC vitals and power. Power commands are risky, so she always asks first and gives 30 seconds to cancel."""
import json

from . import Result, action
from .winshell import run_ps

_STATUS_PS = r"""
$os = Get-CimInstance Win32_OperatingSystem
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
$d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$b = Get-CimInstance Win32_Battery | Select-Object -First 1
[pscustomobject]@{
  cpu = [int]$cpu
  mem_total_gb = [math]::Round($os.TotalVisibleMemorySize/1MB,1)
  mem_free_gb = [math]::Round($os.FreePhysicalMemory/1MB,1)
  disk_free_gb = [math]::Round($d.FreeSpace/1GB,0)
  disk_total_gb = [math]::Round($d.Size/1GB,0)
  battery = if ($b) { [int]$b.EstimatedChargeRemaining } else { $null }
  charging = if ($b) { $b.BatteryStatus -eq 2 } else { $null }
  uptime_h = [math]::Round(((Get-Date) - $os.LastBootUpTime).TotalHours,1)
} | ConvertTo-Json -Compress
"""


def format_status(d: dict) -> str:
    used = d["mem_total_gb"] - d["mem_free_gb"]
    pct = round(100 * used / d["mem_total_gb"]) if d["mem_total_gb"] else 0
    parts = [f"CPU at {d['cpu']} percent", f"memory {pct} percent used of {d['mem_total_gb']} gigabytes",
             f"disk C has {d['disk_free_gb']:.0f} of {d['disk_total_gb']:.0f} gigabytes free"]
    if d.get("battery") is not None:
        parts.append(f"battery {d['battery']} percent" + (", charging" if d.get("charging") else ", on battery"))
    parts.append(f"up for {d['uptime_h']} hours")
    return "System status: " + ", ".join(parts) + "."


@action("system_status", "info", "PC vitals: CPU, memory, disk, battery, uptime. args: {}")
def system_status(a: dict) -> Result:
    ok, out = run_ps(_STATUS_PS, 30)
    if not ok:
        return Result(False, out)
    try:
        return Result(True, format_status(json.loads(out)))
    except Exception:
        return Result(False, "I couldn't read the system status.")


@action("top_processes", "info", "Which programs use the most memory right now. args: {}")
def top_processes(a: dict) -> Result:
    ok, out = run_ps("Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 "
                     "@{n='n';e={$_.ProcessName}}, @{n='mb';e={[int]($_.WorkingSet64/1MB)}} | ConvertTo-Json -Compress")
    if not ok:
        return Result(False, out)
    try:
        rows = json.loads(out)
        rows = rows if isinstance(rows, list) else [rows]
        return Result(True, "Biggest memory users: " + ", ".join(f"{r['n']} {r['mb']} megabytes" for r in rows) + ".")
    except Exception:
        return Result(False, "I couldn't read the process list.")


_POWER = {
    "sleep": ("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", "Putting the PC to sleep."),
    "restart": ("shutdown.exe /r /t 30", "Restarting in 30 seconds. Say cancel shutdown to stop it."),
    "shutdown": ("shutdown.exe /s /t 30", "Shutting down in 30 seconds. Say cancel shutdown to stop it."),
    "cancel": ("shutdown.exe /a", "Cancelled. The PC stays on."),
}


def _power_desc(a: dict) -> str:
    cmd = str(a.get("command", "")).lower()
    return {"sleep": "put the PC to sleep", "restart": "restart the PC", "shutdown": "shut the PC down"}.get(cmd, "change the PC power state")


@action("power_action", "pc", 'Power: args: {"command": "sleep" | "restart" | "shutdown" | "cancel"} (cancel stops a pending restart or shutdown)',
        risky=lambda a: str(a.get("command", "")).lower().strip() != "cancel", describe=_power_desc)
def power_action(a: dict) -> Result:
    cmd = str(a.get("command", "")).lower().strip()
    if cmd not in _POWER:
        return Result(False, "I can sleep, restart, shut down or cancel.")
    script, msg = _POWER[cmd]
    ok, out = run_ps(script)
    return Result(True, msg) if ok else Result(False, out)
