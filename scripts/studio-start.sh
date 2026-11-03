#!/usr/bin/env bash
# Starts ComfyUI (the picture engine) from your SSD, in low-memory mode for a 6 GB graphics card.
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
ROOT=$(grep -E '^MODELS_ROOT=' backend/.env 2>/dev/null | cut -d= -f2)
[ -n "$ROOT" ] && [ -d "$ROOT/comfyui" ] || { echo "ComfyUI isn't installed. Run: bash scripts/studio-setup.sh <ssd folder> --comfy"; exit 1; }
if curl -s -m 2 localhost:8188/system_stats >/dev/null; then echo "ComfyUI is already running."; exit 0; fi
mkdir -p logs "$ROOT/outputs/comfy"
cd "$ROOT/comfyui" && nohup "$ROOT/comfyui-venv/bin/python" main.py --lowvram --port 8188 --output-directory "$ROOT/outputs/comfy" \
  > "$OLDPWD/logs/comfyui.log" 2>&1 &
echo "Starting ComfyUI (first start takes a minute). Log: logs/comfyui.log"
