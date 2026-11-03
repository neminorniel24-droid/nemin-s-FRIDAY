#!/usr/bin/env bash
# Sets up the NEMIII studio on your external SSD. Nothing is downloaded until you run this.
#
#   bash scripts/studio-setup.sh /mnt/d/NemiiiStudio              folders + settings only (tiny)
#   bash scripts/studio-setup.sh /mnt/d/NemiiiStudio --tools      + music, voice and transcribe tools (about 4-6 GB)
#   bash scripts/studio-setup.sh /mnt/d/NemiiiStudio --comfy      + ComfyUI for pictures (about 5 GB)
#   bash scripts/studio-setup.sh /mnt/d/NemiiiStudio --ollama    + store Ollama's models on the SSD (Windows setting)
# Flags can be combined. Run it again any time to add one.
set -u
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
ROOT="${1:-}"; shift || true
TOOLS=0; COMFY=0; OLLAMA=0
for f in "$@"; do case "$f" in --tools) TOOLS=1;; --comfy) COMFY=1;; --ollama) OLLAMA=1;; *) echo "Unknown option $f"; exit 1;; esac; done

if [ -z "$ROOT" ]; then
  echo "Give me the folder on your SSD, for example:"
  echo "  bash scripts/studio-setup.sh /mnt/d/NemiiiStudio"
  echo "Your drives are here:"; ls /mnt
  exit 1
fi
ROOT="${ROOT%/}"
PARENT="$(dirname "$ROOT")"
[ -d "$PARENT" ] || { echo "I can't see $PARENT. Is the SSD plugged in? (run: ls /mnt)"; exit 1; }
case "$ROOT" in /mnt/c|/mnt/c/*) echo "Warning: that is your C: drive, not the external SSD. Continue anyway? [y/N]"; read -r a; [ "$a" = y ] || exit 1;; esac
mkdir -p "$ROOT"/{models,outputs/{images,music,speech,transcripts},ollama,cache,logs} || { echo "Can't create folders in $ROOT"; exit 1; }
touch "$ROOT/.w" 2>/dev/null && rm -f "$ROOT/.w" || { echo "I can't write to $ROOT"; exit 1; }
echo "Free space on that drive: $(df -h "$ROOT" | awk 'NR==2{print $4}')"

# remember the folder in backend/.env
ENVF=backend/.env; touch "$ENVF"
if grep -q '^MODELS_ROOT=' "$ENVF"; then sed -i "s|^MODELS_ROOT=.*|MODELS_ROOT=$ROOT|" "$ENVF"; else echo "MODELS_ROOT=$ROOT" >> "$ENVF"; fi
echo "Saved MODELS_ROOT=$ROOT in backend/.env"

# keep pip and temp files OFF your small laptop drive while installing
export PIP_CACHE_DIR="$ROOT/cache/pip" TMPDIR="$ROOT/cache"

if [ "$TOOLS" = 1 ]; then
  echo "== Studio tools (music, voice, transcribe) =="
  python3 -m venv --copies "$ROOT/venv" || { echo "Could not create a virtual environment on the SSD (python3-venv missing?)"; exit 1; }
  "$ROOT/venv/bin/pip" install -q -U pip
  "$ROOT/venv/bin/pip" install -q numpy scipy soundfile huggingface_hub faster-whisper kokoro-onnx transformers torch \
    && echo "Tools installed." || echo "Some tools failed to install. Run again, or run: bash scripts/doctor.sh"
fi

if [ "$COMFY" = 1 ]; then
  echo "== ComfyUI (pictures) =="
  command -v git >/dev/null || { echo "git is needed"; exit 1; }
  [ -d "$ROOT/comfyui" ] || git clone --depth 1 https://github.com/comfyanonymous/ComfyUI "$ROOT/comfyui" || exit 1
  python3 -m venv --copies "$ROOT/comfyui-venv" || exit 1
  "$ROOT/comfyui-venv/bin/pip" install -q -U pip
  "$ROOT/comfyui-venv/bin/pip" install -q torch torchvision torchaudio || { echo "torch install failed"; exit 1; }
  "$ROOT/comfyui-venv/bin/pip" install -q -r "$ROOT/comfyui/requirements.txt" || { echo "ComfyUI requirements failed"; exit 1; }
  cat > "$ROOT/comfyui/extra_model_paths.yaml" <<YAML
nemiii:
    base_path: $ROOT/models/
    checkpoints: checkpoints/
    loras: loras/
    vae: vae/
YAML
  mkdir -p "$ROOT/models"/{checkpoints,loras,vae}
  echo "ComfyUI installed. Start it with: bash scripts/studio-start.sh"
fi

if [ "$OLLAMA" = 1 ]; then
  echo "== Ollama models on the SSD =="
  WIN="$(wslpath -w "$ROOT/ollama" 2>/dev/null)"
  if command -v powershell.exe >/dev/null && [ -n "$WIN" ]; then
    powershell.exe -NoProfile -Command "[Environment]::SetEnvironmentVariable('OLLAMA_MODELS','$WIN','User')" \
      && echo "Set OLLAMA_MODELS=$WIN for your Windows account. Quit Ollama from the tray and start it again for it to apply."
  else
    echo "Add this line to your shell profile, then restart Ollama: export OLLAMA_MODELS=$ROOT/ollama"
  fi
fi

echo
echo "Studio folder ready: $ROOT"
echo "Next: restart Nemiii (./run.sh), then say:  'studio status'  and  'install Whisper' / 'install the image model' ..."
