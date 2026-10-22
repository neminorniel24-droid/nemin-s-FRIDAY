#!/usr/bin/env bash
# Puts a "Nemiii" icon on your Windows desktop.
#   bash scripts/windows-shortcut.sh               desktop icon
#   bash scripts/windows-shortcut.sh --autostart   desktop icon + start Nemiii when you log in to Windows
#   bash scripts/windows-shortcut.sh --remove      remove both
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
ROOT=$(pwd)
command -v powershell.exe >/dev/null 2>&1 || { echo "Run this inside WSL on Windows."; exit 1; }
AUTO=0; REM=0
for a in "$@"; do case "$a" in --autostart) AUTO=1;; --remove) REM=1;; esac; done
cd /mnt/c 2>/dev/null
WLOCAL=$(cmd.exe /c "echo %LOCALAPPDATA%" 2>/dev/null | tr -d '\r')
WTEMP=$(cmd.exe /c "echo %TEMP%" 2>/dev/null | tr -d '\r')
LOCAL_WSL=$(wslpath -u "$WLOCAL")/Nemiii
TEMP_WSL=$(wslpath -u "$WTEMP")
mkdir -p "$LOCAL_WSL"
cp -f "$ROOT/windows/nemiii.ico" "$LOCAL_WSL/nemiii.ico"
cp -f "$ROOT/windows/create-shortcut.ps1" "$TEMP_WSL/nemiii-shortcut.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w "$TEMP_WSL/nemiii-shortcut.ps1")" \
  -Distro "${WSL_DISTRO_NAME:-Ubuntu}" -Root "$ROOT" -Icon "$WLOCAL\\Nemiii\\nemiii.ico" -Autostart "$AUTO" -Remove "$REM" | tr -d '\r'
rm -f "$TEMP_WSL/nemiii-shortcut.ps1"
[ $REM = 1 ] || echo "Done. Double-click Nemiii on your desktop. Closing its (minimised) window stops her."
