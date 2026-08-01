#!/bin/bash
# start-nemiii.sh — starts both halves of Nemiii and opens the browser.
# Run manually to test: bash ~/friday/nemin-ai-assist/scripts/start-nemiii.sh
# Run automatically at Windows login via start-nemiii.bat (see NEMIII_SETUP.md).

set -e
PROJECT_DIR="$HOME/friday/nemin-ai-assist"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "[nemiii] starting backend..."
cd "$PROJECT_DIR/backend"
source venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > "$LOG_DIR/backend.log" 2>&1 &

echo "[nemiii] waiting for backend to be ready..."
for i in $(seq 1 30); do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "[nemiii] backend is up"
    break
  fi
  sleep 1
done

echo "[nemiii] starting frontend (production build)..."
cd "$PROJECT_DIR"
nohup npm run start > "$LOG_DIR/frontend.log" 2>&1 &

echo "[nemiii] waiting for frontend to be ready..."
for i in $(seq 1 30); do
  if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "[nemiii] frontend is up"
    break
  fi
  sleep 1
done

echo "[nemiii] opening browser..."
cmd.exe /c start http://localhost:3000 > /dev/null 2>&1 || true

echo "[nemiii] done. Logs: $LOG_DIR"
