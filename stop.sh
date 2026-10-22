#!/usr/bin/env bash
# Stops Nemiii (this copy and any older copy still running).   ./stop.sh
cd "$(dirname "$(readlink -f "$0")")" || exit 1
for f in .run/backend.pid .run/frontend.pid; do
  [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null; rm -f "$f"
done
python3 scripts/nemiii_ctl.py stop-ours "$(pwd)"
[ "$1" = "--quiet" ] || echo "Nemiii stopped."
exit 0
