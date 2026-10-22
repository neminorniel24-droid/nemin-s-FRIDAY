#!/usr/bin/env bash
# Nemiii one-step installer (run inside WSL).
#
#   bash scripts/install.sh                      normal install
#   bash scripts/install.sh --video "/path.mp4"  use this video file
#   bash scripts/install.sh --old ~/friday/x     take keys/Gmail login from this older Nemiii folder
#   bash scripts/install.sh --clean              delete node_modules and the python env first
#   bash scripts/install.sh --shortcut           also create the desktop icon (and --autostart to start at login)
#
# What it does: finds your old keys + Gmail login + video and reuses them, sets up Python and
# Node, builds the page, runs the tests, and tells you how to start. It never deletes your old folders.
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
ROOT=$(pwd)
VIDEO_ARG=""; OLD_ARG=""; CLEAN=0; SHORTCUT=0; AUTOSTART=0
while [ $# -gt 0 ]; do
  case "$1" in
    --video) VIDEO_ARG="$2"; shift;;
    --old) OLD_ARG="$2"; shift;;
    --clean) CLEAN=1;;
    --shortcut) SHORTCUT=1;;
    --autostart) SHORTCUT=1; AUTOSTART=1;;
  esac; shift
done
WARN=()
step(){ echo; echo "=== $* ==="; }
warn(){ WARN+=("$*"); echo "!! $*"; }

step "1. Checking your computer"
PYV=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)
NODEV=$(node -v 2>/dev/null | sed 's/v//;s/\..*//')
echo "python $PYV   node ${NODEV:-missing}   npm $(npm -v 2>/dev/null || echo missing)"
[ -z "$PYV" ] && { echo "Python 3 is missing:  sudo apt install -y python3 python3-venv python3-pip"; exit 1; }
if [ -z "$NODEV" ] || [ "$NODEV" -lt 20 ]; then echo "Node 20 or newer is needed (https://nodejs.org or nvm)."; exit 1; fi
echo "memory: $(free -m 2>/dev/null | awk '/Mem:/{print $7" MB available"}')   disk: $(df -h . | tail -1 | awk '{print $4" free"}')"

step "2. Stopping any running Nemiii (so nothing is locked or short of memory)"
python3 scripts/nemiii_ctl.py stop-ours "$ROOT"

step "3. Your keys, Gmail login and video from the older version"
OLD_BACKEND=""
if [ -n "$OLD_ARG" ]; then OLD_BACKEND="${OLD_ARG%/}/backend"; fi
if [ -z "$OLD_BACKEND" ]; then
  while IFS= read -r f; do
    d=$(dirname "$f")
    [ "$d" = "$ROOT/backend" ] && continue
    if grep -qE '^(GROQ_API_KEY|NEWSDATA_KEY)=.+' "$f" 2>/dev/null; then OLD_BACKEND="$d"; break; fi
  done < <(find "$HOME" -maxdepth 4 -path '*/backend/.env' -not -path '*/node_modules/*' -printf '%T@ %p\n' 2>/dev/null | sort -rn | cut -d' ' -f2-)
fi
if [ ! -f backend/.env ]; then
  if [ -n "$OLD_BACKEND" ] && [ -f "$OLD_BACKEND/.env" ]; then
    cp "$OLD_BACKEND/.env" backend/.env; echo "keys copied from $OLD_BACKEND/.env"
  else
    cp backend/.env.example backend/.env; echo "no older keys found: created an empty backend/.env"
  fi
else echo "backend/.env already exists, keeping it"; fi
# add any setting this version knows about that the old file did not have
python3 - <<'PY'
import re
ex = open("backend/.env.example").read().splitlines()
cur = open("backend/.env").read()
have = set(re.findall(r"^([A-Z_]+)=", cur, re.M))
add = [l for l in ex if re.match(r"^[A-Z_]+=", l) and l.split("=", 1)[0] not in have]
if add:
    open("backend/.env", "a").write("\n# ---- added by the v13 installer ----\n" + "\n".join(add) + "\n")
    print("added new settings:", ", ".join(l.split("=")[0] for l in add))
PY
for f in credentials.json token.json; do
  if [ ! -f "backend/$f" ] && [ -n "$OLD_BACKEND" ] && [ -f "$OLD_BACKEND/$f" ]; then cp "$OLD_BACKEND/$f" "backend/$f" && echo "$f copied (Gmail login)"; fi
done
[ -f .env.local ] || cp .env.local.example .env.local
chmod 600 backend/.env 2>/dev/null
echo "keys found (names only): $(grep -E '^[A-Z_]+=.+' backend/.env | cut -d= -f1 | tr '\n' ' ')"

# ---- video ----
VIDEO=""
if [ -n "$VIDEO_ARG" ]; then VIDEO="$VIDEO_ARG"
elif [ ! -f public/nemiii-video.mp4 ]; then
  for d in /mnt/c/Users/*/Downloads /mnt/c/Users/*/OneDrive*/Downloads /mnt/c/Users/*/Videos /mnt/c/Users/*/Desktop /mnt/c/Users/*/OneDrive*/Desktop; do
    [ -d "$d" ] || continue
    f=$(find "$d" -maxdepth 2 -iname 'Hypnotic*Eye*.mp4' 2>/dev/null | head -1)
    [ -n "$f" ] && { VIDEO="$f"; break; }
  done
  [ -z "$VIDEO" ] && [ -n "$OLD_BACKEND" ] && [ -f "$OLD_BACKEND/../public/nemiii-video.mp4" ] && VIDEO="$OLD_BACKEND/../public/nemiii-video.mp4"
fi
if [ -n "$VIDEO" ]; then
  echo "video: $VIDEO"
  bash scripts/prepare-video.sh "$VIDEO"
elif [ -f public/nemiii-video.mp4 ]; then echo "video already in place"
else warn "No video found. Copy yours to $ROOT/public/nemiii-video.mp4  (or run: bash scripts/install.sh --video \"/mnt/c/Users/you/Downloads/file.mp4\")"; fi

step "4. Python (backend)"
[ $CLEAN = 1 ] && rm -rf backend/.venv
if [ ! -x backend/.venv/bin/python ]; then
  python3 -m venv backend/.venv || { echo "Could not create the python environment. Try:  sudo apt install -y python3-venv   then run this again."; exit 1; }
fi
backend/.venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1
backend/.venv/bin/python -m pip install -r backend/requirements.txt || { echo "pip install failed (see above)."; exit 1; }
backend/.venv/bin/python -c "import fastapi, uvicorn, groq, dotenv, requests; print('backend packages OK')" || exit 1

step "5. Node (page)"
[ $CLEAN = 1 ] && rm -rf node_modules .next
if [ ! -f node_modules/next/package.json ]; then
  npm ci --no-audit --no-fund || npm install --no-audit --no-fund || { echo "npm install failed (see above)."; exit 1; }
else echo "node_modules already there"; fi
node scripts/copy-mediapipe.mjs >/dev/null 2>&1
if [ ! -s public/mediapipe/hand_landmarker.task ]; then
  curl -fsSL -m 90 -o public/mediapipe/hand_landmarker.task \
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" 2>/dev/null \
    && echo "hand-tracking model downloaded" || { rm -f public/mediapipe/hand_landmarker.task; echo "(hand model not downloaded; it will load online when you turn gestures on)"; }
fi

step "6. Building the page"
export NODE_OPTIONS="--max-old-space-size=3072"
rm -rf .next
if ! npm run build 2>&1 | tail -12 || [ ! -f .next/BUILD_ID ]; then
  echo "First build failed. Retrying once from a clean state..."
  rm -rf .next
  npm run build 2>&1 | tail -12
fi
if [ ! -f .next/BUILD_ID ]; then
  warn "The page could not be built. Nemiii will start in developer mode instead (slower start). If you saw 'Bus error', close other heavy programs or run:  bash scripts/install.sh --clean"
fi

step "7. Tests"
( cd backend && .venv/bin/python -m pytest -q 2>&1 | tail -3 )

if [ $SHORTCUT = 1 ]; then
  step "8. Desktop shortcut"
  if [ $AUTOSTART = 1 ]; then bash scripts/windows-shortcut.sh --autostart; else bash scripts/windows-shortcut.sh; fi
fi

echo
echo "================  INSTALL FINISHED  ================"
for w in "${WARN[@]}"; do echo "NOTE: $w"; done
echo "Start :   cd $ROOT && ./run.sh --open"
echo "Stop  :   ./stop.sh"
echo "Icon  :   bash scripts/windows-shortcut.sh            (add --autostart to launch when you log in)"
echo "Brain :   $(grep -qE '^GROQ_API_KEY=.+' backend/.env && echo 'Groq key found (cloud brain ready)' || echo 'no Groq key yet') ; for a free local brain run: bash scripts/install-local-model.sh"
echo "Problems: bash scripts/doctor.sh"
