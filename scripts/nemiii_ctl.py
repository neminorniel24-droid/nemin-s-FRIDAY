#!/usr/bin/env python3
"""
Tiny helper used by run.sh / stop.sh so they work without ss / lsof / fuser.

  nemiii_ctl.py busy PORT          exit 0 if something listens on PORT inside WSL
  nemiii_ctl.py pids PORT          print the pids listening on PORT
  nemiii_ctl.py stop-ours ROOT     stop any Nemiii backend/frontend (this copy or an older copy)
"""
import os
import signal
import sys
import time

PORTS = [8001, 3000, 3001, 3002, 3003]


def listening_inodes(port: int) -> set:
    inodes = set()
    for f in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = open(f).read().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            p = line.split()
            if len(p) > 9 and p[3] == "0A" and int(p[1].rsplit(":", 1)[1], 16) == port:
                inodes.add(p[9])
    return inodes


def pids_on(port: int) -> list:
    inodes = listening_inodes(port)
    out = []
    if not inodes:
        return out
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            for fd in os.listdir(f"/proc/{pid}/fd"):
                link = os.readlink(f"/proc/{pid}/fd/{fd}")
                if link.startswith("socket:[") and link[8:-1] in inodes:
                    out.append(int(pid))
                    break
        except OSError:
            continue
    return out


def cmdline(pid: int) -> str:
    try:
        return open(f"/proc/{pid}/cmdline").read().replace("\0", " ")
    except OSError:
        return ""


def cwd(pid: int) -> str:
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return ""


def is_ours(pid: int, root: str) -> bool:
    c, d = cmdline(pid), cwd(pid)
    if d == root or d.startswith(root + os.sep):
        return True
    if "uvicorn" in c and "main:app" in c:      # another copy of the Nemiii backend
        return True
    pj = os.path.join(d, "package.json")        # another copy of the Nemiii frontend
    try:
        return '"name": "nemiii"' in open(pj).read()
    except OSError:
        return False


def stop_ours(root: str) -> None:
    root = os.path.realpath(root)
    victims = set()
    for port in PORTS:
        for pid in pids_on(port):
            if is_ours(pid, root):
                victims.add(pid)
    for pid in victims:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    time.sleep(1.5)
    for pid in victims:
        if os.path.exists(f"/proc/{pid}"):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    if victims:
        print("stopped", len(victims), "old Nemiii process(es)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "busy":
        sys.exit(0 if listening_inodes(int(sys.argv[2])) else 1)
    elif cmd == "pids":
        print(" ".join(str(p) for p in pids_on(int(sys.argv[2]))))
    elif cmd == "stop-ours":
        stop_ours(sys.argv[2])
    else:
        print(__doc__)
