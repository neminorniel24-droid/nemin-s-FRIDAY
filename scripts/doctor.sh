#!/usr/bin/env bash
# Prints what is working and what is not. Send me this output if something is wrong.
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
echo "=== system ==="
echo "node   : $(node -v 2>&1)    npm: $(npm -v 2>&1)"
echo "python : $(python3 --version 2>&1)"
echo "disk   : $(df -h . | tail -1 | awk '{print $4" free of "$2}')"
echo "memory : $(free -m 2>/dev/null | awk '/Mem:/{print $7" MB available of "$2" MB"}')"
echo "=== files ==="
for f in backend/.env backend/.venv/bin/python node_modules/next/package.json .next/BUILD_ID public/nemiii-video.mp4 public/mediapipe/hand_landmarker.task; do
  [ -e "$f" ] && echo "OK       $f" || echo "MISSING  $f"
done
echo "keys set (names only): $(grep -E '^[A-Z_]+=.+' backend/.env 2>/dev/null | cut -d= -f1 | tr '\n' ' ')"
if [ -f public/nemiii-video.mp4 ] && command -v ffprobe >/dev/null 2>&1; then
  echo "video  : $(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,sample_aspect_ratio -of csv=p=0 public/nemiii-video.mp4)  (codec,width,height,pixel shape; 1:1 is correct)"
fi
echo "=== backend ==="
curl -s -m 5 localhost:8001/health | python3 -m json.tool 2>/dev/null || echo "backend not answering on port 8001"
echo "=== last backend log ==="; tail -8 logs/backend.log 2>/dev/null
echo "=== last page log ===";    tail -8 logs/frontend.log 2>/dev/null
echo "=== kernel crashes (Bus error / segfault) ==="; (dmesg 2>/dev/null | grep -iE "bus error|segfault|out of memory|killed process" | tail -3) || true
