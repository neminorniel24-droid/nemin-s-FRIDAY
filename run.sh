#!/usr/bin/env bash
# Starts Nemiii.      ./run.sh [--open] [--hold] [--dev]
#   --open  open the browser when she is ready
#   --hold  stay in the foreground; closing the window / Ctrl+C stops her (used by the desktop shortcut)
#   --dev   developer mode (slower start, but picks up code edits without rebuilding)
cd "$(dirname "$(readlink -f "$0")")" || exit 1
ROOT=$(pwd)
mkdir -p .run logs
OPEN=0; HOLD=0; DEV=0
for a in "$@"; do case "$a" in --open) OPEN=1;; --hold) HOLD=1;; --dev) DEV=1;; esac; done

./stop.sh --quiet

# ---- choose the page port: first one that nothing (in WSL *or* Windows) is using ----
FRONT=""
for p in 3000 3001 3002 3003; do
  python3 scripts/nemiii_ctl.py busy "$p" && continue
  if command -v powershell.exe >/dev/null 2>&1; then
    r=$(cd /mnt/c 2>/dev/null && powershell.exe -NoProfile -Command "try{(New-Object Net.Sockets.TcpClient('127.0.0.1',$p)).Close();'busy'}catch{'free'}" 2>/dev/null | tr -d '\r')
    [ "$r" = "busy" ] && { echo "Port $p is used by another program on Windows, trying the next one."; continue; }
  fi
  FRONT=$p; break
done
[ -z "$FRONT" ] && { echo "No free port between 3000 and 3003."; exit 1; }
URL="http://localhost:$FRONT"

# ---- backend (only listens on this computer; it can control your PC, so it is never exposed to the network) ----
if [ ! -x backend/.venv/bin/python ]; then echo "Not installed yet. Run:  bash scripts/install.sh"; exit 1; fi
( cd backend && exec nohup .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001 ) > logs/backend.log 2>&1 < /dev/null &
echo $! > .run/backend.pid

# ---- frontend ----
if [ "$DEV" = 1 ] || [ ! -f .next/BUILD_ID ]; then
  [ "$DEV" = 1 ] || echo "(no production build found, starting in developer mode)"
  nohup ./node_modules/.bin/next dev --webpack -p "$FRONT" -H 127.0.0.1 > logs/frontend.log 2>&1 < /dev/null &
else
  nohup ./node_modules/.bin/next start -p "$FRONT" -H 127.0.0.1 > logs/frontend.log 2>&1 < /dev/null &
fi
echo $! > .run/frontend.pid

# ---- wait until both answer ----
ok_b=0; ok_f=0
for i in $(seq 1 90); do
  [ $ok_b = 0 ] && curl -s -m 2 localhost:8001/health >/dev/null 2>&1 && ok_b=1
  [ $ok_f = 0 ] && curl -s -m 5 -o /dev/null "$URL" 2>/dev/null && ok_f=1
  [ $ok_b = 1 ] && [ $ok_f = 1 ] && break
  sleep 1
done
echo "Backend : $([ $ok_b = 1 ] && echo OK || echo 'NOT ANSWERING  (see logs/backend.log)')"
echo "Page    : $([ $ok_f = 1 ] && echo OK || echo 'NOT ANSWERING  (see logs/frontend.log)')"
if [ $ok_b = 1 ]; then curl -s localhost:8001/health | python3 -c "
import sys, json
h = json.load(sys.stdin); l = h['local']
print('Brain   :', ('local ' + l['model']) if l['ready'] else ('Groq (cloud)' if h['groq_configured'] else 'NONE - add GROQ_API_KEY to backend/.env or run scripts/install-local-model.sh'))
print('PC      :', 'linked' if h['pc_control_available'] else 'not available (run inside WSL on Windows)')
" 2>/dev/null; fi
echo "Open    : $URL"
[ $ok_b = 1 ] && [ $ok_f = 1 ] || { echo "Something did not start. Run: bash scripts/doctor.sh"; }

if [ $OPEN = 1 ] && [ $ok_f = 1 ]; then
  ( cd /mnt/c 2>/dev/null
    cmd.exe /c start "" chrome "--app=$URL" >/dev/null 2>&1 \
      || powershell.exe -NoProfile -Command "Start-Process '$URL'" >/dev/null 2>&1 )
fi

if [ $HOLD = 1 ]; then
  trap './stop.sh --quiet; exit 0' INT TERM HUP EXIT
  echo "Nemiii is running. Close this window to stop her."
  while kill -0 "$(cat .run/backend.pid 2>/dev/null)" 2>/dev/null && kill -0 "$(cat .run/frontend.pid 2>/dev/null)" 2>/dev/null; do sleep 3; done
fi
