#!/usr/bin/env bash
# Sets up the LOCAL brain (free, private, works offline) using Ollama.
# Usage:  bash scripts/install-local-model.sh
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
MODEL=$(grep -E '^LOCAL_MODEL=' backend/.env 2>/dev/null | cut -d= -f2); MODEL=${MODEL:-llama3.2:3b}
VISION=$(grep -E '^LOCAL_VISION_MODEL=' backend/.env 2>/dev/null | cut -d= -f2); VISION=${VISION:-moondream}

OLLAMA=""
if command -v ollama >/dev/null 2>&1; then OLLAMA=ollama
elif command -v ollama.exe >/dev/null 2>&1; then OLLAMA=ollama.exe; fi

if [ -z "$OLLAMA" ]; then
  cat <<'TXT'
Ollama is not installed yet. Pick ONE way:

  A) Windows (easiest, uses your graphics card):
     1. Download and install it from  https://ollama.com/download
     2. Run this script again.

  B) Inside WSL (CPU only):
     curl -fsSL https://ollama.com/install.sh | sh
     then run this script again.
TXT
  exit 1
fi

echo "Using: $OLLAMA"
if ! curl -s -m 2 localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Starting the Ollama server..."
  nohup "$OLLAMA" serve > logs/ollama.log 2>&1 &
  sleep 4
fi
echo "Downloading the chat model ($MODEL). This is a one-time download of about 2 GB..."
"$OLLAMA" pull "$MODEL" || exit 1
echo "Downloading the picture model ($VISION), about 1.7 GB, used for 'what do you see'..."
"$OLLAMA" pull "$VISION" || echo "(picture model skipped; the cloud one will be used if you have a Groq key)"
echo
echo "Done. Restart Nemiii (./run.sh). In backend/.env, LLM_PROVIDER=auto uses the local model first,"
echo "LLM_PROVIDER=local makes her fully offline."
echo "For a smarter (but slower) brain, set LOCAL_MODEL=qwen2.5:7b or llama3.1:8b and run this script again."
