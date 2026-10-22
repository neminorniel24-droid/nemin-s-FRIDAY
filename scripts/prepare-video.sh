#!/usr/bin/env bash
# Cleans up your video so it ALWAYS shows with the right shape:
#   square pixels, even size, at most 1920 wide, no sound, fast start.
# Usage:  bash scripts/prepare-video.sh "/path/to/your video.mp4"
# Output: public/nemiii-video.mp4
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
IN="$1"
[ -f "$IN" ] || { echo "Usage: bash scripts/prepare-video.sh \"/path/to/video.mp4\""; exit 1; }
mkdir -p public
OUT="public/nemiii-video.mp4"
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is not installed, so the video is copied as it is."
  echo "(Optional, for the cleanup step: sudo apt install -y ffmpeg   then run this again.)"
  cp -f "$IN" "$OUT"; exit 0
fi
echo "Your file:"
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,sample_aspect_ratio,duration -of default=nw=1 "$IN" 2>/dev/null | sed 's/^/   /'
TMP="public/.nemiii-video.tmp.mp4"
if ffmpeg -y -v error -i "$IN" -an \
     -vf "scale='trunc(iw*sar/2)*2':ih,setsar=1,scale='min(1920,iw)':-2,format=yuv420p" \
     -c:v libx264 -preset medium -crf 20 -movflags +faststart "$TMP"; then
  mv -f "$TMP" "$OUT"
  echo "Cleaned video saved:"
  ffprobe -v error -select_streams v:0 -show_entries stream=width,height,sample_aspect_ratio -of default=nw=1 "$OUT" | sed 's/^/   /'
else
  rm -f "$TMP"; echo "Cleanup failed, copying the original instead."; cp -f "$IN" "$OUT"
fi
