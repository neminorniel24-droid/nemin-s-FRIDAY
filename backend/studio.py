"""
The studio: a small, honest catalog of free models that fit a 6 GB graphics card, and the code that
installs, removes and tracks them on ONE folder (your external SSD).

Rules that keep it safe:
  - Only catalog ids can be installed. The model never supplies a URL or a command.
  - Nothing happens until MODELS_ROOT is set to an existing, writable folder.
  - A download is refused if it would leave less than MIN_FREE_GB free on that drive.
  - Everything is written under MODELS_ROOT and nothing outside it is ever deleted.
"""
import shutil
import threading
import time
from pathlib import Path

import requests

import config
import llm

GB = 1024 ** 3

# kind: chat, vision, stt (speech to text), tts (text to speech), image, music, video, 3d, agent
# how:  ollama (pulled by Ollama), url (single files), hf (Hugging Face), manual (we only give steps)
CATALOG: list[dict] = [
    # ---- brains (Ollama) -------------------------------------------------
    dict(id="chat-llama3.2-3b", kind="chat", name="Llama 3.2 3B (fast, default)", gb=2.0, how="ollama", tag="llama3.2:3b", tier="recommended",
         note="Fast on a 4050. Good for commands and chat."),
    dict(id="chat-qwen2.5-7b", kind="chat", name="Qwen 2.5 7B (smarter)", gb=4.7, how="ollama", tag="qwen2.5:7b", tier="recommended",
         note="Smarter, still fits 6 GB of video memory. Set LOCAL_MODEL=qwen2.5:7b."),
    dict(id="vision-moondream", kind="vision", name="Moondream (tiny vision)", gb=1.7, how="ollama", tag="moondream", tier="recommended",
         note="Answers 'what do you see' offline."),
    dict(id="vision-gemma3-4b", kind="vision", name="Gemma 3 4B (chat + vision)", gb=3.3, how="ollama", tag="gemma3:4b", tier="optional",
         note="Better pictures and chat in one model. Set LOCAL_VISION_MODEL=gemma3:4b."),
    # ---- ears and voice --------------------------------------------------
    dict(id="stt-whisper-small", kind="stt", name="Whisper small (speech to text)", gb=0.5, how="hf", repo="Systran/faster-whisper-small",
         dest="stt/whisper-small", tier="recommended", note="Transcribes recordings and audio files. Runs on CPU."),
    dict(id="tts-kokoro", kind="tts", name="Kokoro 82M (natural offline voice)", gb=0.34, how="url", dest="tts/kokoro",
         files=[("kokoro-v1.0.onnx", "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx"),
                ("voices-v1.0.bin", "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin")],
         tier="recommended", note="Turns text into a spoken file. Apache 2.0."),
    # ---- pictures --------------------------------------------------------
    dict(id="image-sdxl-turbo", kind="image", name="SDXL Turbo (images in seconds)", gb=6.9, how="hf", repo="stabilityai/sdxl-turbo",
         dest="models/checkpoints", pattern="sd_xl_turbo_1.0_fp16.safetensors", tier="recommended",
         note="Needs ComfyUI. Fits 6 GB with low-VRAM mode. Free for personal and research use; check its licence for business."),
    # ---- music -----------------------------------------------------------
    dict(id="music-musicgen-small", kind="music", name="MusicGen small (short music clips)", gb=2.4, how="hf", repo="facebook/musicgen-small",
         dest="music/musicgen-small", tier="recommended", note="Makes instrumental clips from a text prompt. Non-commercial licence."),
    # ---- advanced: we do not automate these yet --------------------------
    dict(id="video-wan-1.3b", kind="video", name="Wan 2.1 1.3B (short video)", gb=9.0, how="manual", tier="experimental",
         note="Short, slow, low-resolution clips on 6 GB. Run it inside ComfyUI with a template workflow. Not automated."),
    dict(id="video-ltx", kind="video", name="LTX-Video (short video)", gb=10.0, how="manual", tier="experimental",
         note="Needs lowvram mode and patience on 6 GB. Run it inside ComfyUI. Not automated."),
    dict(id="3d-triposr", kind="3d", name="TripoSR (picture to 3D model)", gb=1.5, how="manual", tier="experimental",
         note="Turns one picture into a 3D mesh. Needs its own setup. Not automated."),
    dict(id="agent-openclaw", kind="agent", name="OpenClaw (autonomous agent)", gb=0.5, how="manual", tier="isolated",
         note="Has full computer access. Install it in an isolated place only. See docs/OPENCLAW.md."),
]
BY_ID = {e["id"]: e for e in CATALOG}

JOBS: dict[str, dict] = {}   # id -> {state: running|done|error, message, pct}
_LOCK = threading.Lock()


# ------------------------------------------------------------------ the SSD folder
def root() -> Path | None:
    """The studio folder, or None when it is not set up / not reachable (SSD unplugged)."""
    if not config.MODELS_ROOT:
        return None
    p = Path(config.MODELS_ROOT)
    return p if p.is_dir() else None


def root_problem() -> str | None:
    if not config.MODELS_ROOT:
        return "The studio isn't set up. Run: bash scripts/studio-setup.sh /mnt/d/NemiiiStudio (your SSD folder)."
    p = Path(config.MODELS_ROOT)
    if not p.is_dir():
        return f"I can't see the studio folder {config.MODELS_ROOT}. Is the external SSD plugged in?"
    try:
        probe = p / ".nemiii-write-test"
        probe.write_text("x")
        probe.unlink()
    except OSError:
        return f"I can't write to {config.MODELS_ROOT}."
    return None


def out_dir(kind: str) -> Path:
    r = root()
    if r is None:
        raise RuntimeError(root_problem() or "studio is off")
    d = r / "outputs" / kind
    d.mkdir(parents=True, exist_ok=True)
    return d


def free_gb() -> float | None:
    r = root()
    return round(shutil.disk_usage(r).free / GB, 1) if r else None


def folder_gb(p: Path) -> float:
    total = 0
    if p.exists():
        for f in p.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                pass
    return round(total / GB, 2)


# ------------------------------------------------------------------ what is installed
def _dest(e: dict) -> Path | None:
    r = root()
    if r is None or "dest" not in e:
        return None
    return r / e["dest"]


def _marker(e: dict) -> Path | None:
    d = _dest(e)
    return d / f".nemiii-{e['id']}.done" if d else None


def installed(e: dict) -> bool:
    if e["how"] == "ollama":
        return llm._has_model(llm.local_status()["models"], e["tag"])
    if e["how"] == "manual":
        return False
    m = _marker(e)
    return bool(m and m.exists())


def rows() -> list[dict]:
    out = []
    for e in CATALOG:
        job = JOBS.get(e["id"])
        out.append(dict(id=e["id"], kind=e["kind"], name=e["name"], gb=e["gb"], tier=e["tier"], how=e["how"],
                        installed=installed(e), job=job, note=e["note"]))
    return out


def summary() -> str:
    """Spoken status: free space and what is installed."""
    problem = root_problem()
    have = [e["name"] for e in CATALOG if e["how"] != "manual" and installed(e)]
    parts = []
    if problem:
        parts.append(problem)
    else:
        parts.append(f"The studio is on your SSD with {free_gb()} gigabytes free.")
    parts.append("Installed: " + (", ".join(have) if have else "nothing yet") + ".")
    running = [f"{BY_ID[i]['name']}: {j['message']}" for i, j in JOBS.items() if j["state"] == "running"]
    if running:
        parts.append("Downloading: " + "; ".join(running) + ".")
    return " ".join(parts)


# ------------------------------------------------------------------ install / remove
def can_install(e: dict) -> str | None:
    """None when it is fine to start, otherwise the reason it is not."""
    if e["how"] == "manual":
        return f"{e['name']} is a manual install. {e['note']}"
    if e["how"] != "ollama":   # Ollama keeps its own folder; everything else lives on the SSD
        problem = root_problem()
        if problem:
            return problem
        free = free_gb()
        if free is not None and free - e["gb"] < config.MIN_FREE_GB:
            return f"Not enough room: {e['name']} needs about {e['gb']} gigabytes and the SSD has {free} free."
    return None


def _set(eid: str, **kw):
    with _LOCK:
        JOBS.setdefault(eid, {"state": "running", "message": "starting", "pct": 0}).update(kw)


def _download_url(eid: str, url: str, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    with requests.get(url, stream=True, timeout=30, allow_redirects=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        got = 0
        with open(part, "wb") as f:
            for chunk in r.iter_content(1024 * 256):
                f.write(chunk)
                got += len(chunk)
                if total:
                    _set(eid, message=f"{target.name} {round(100 * got / total)} percent", pct=round(100 * got / total))
    part.replace(target)


def _ollama_pull(eid: str, tag: str):
    url = llm.local_status()["url"]
    if not url:
        raise RuntimeError("Ollama isn't running. Start it first (see docs/STUDIO.md).")
    with requests.post(url + "/api/pull", json={"name": tag, "stream": True}, stream=True, timeout=(10, 600)) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            import json
            d = json.loads(line)
            if d.get("error"):
                raise RuntimeError(d["error"])
            if d.get("total"):
                pct = round(100 * d.get("completed", 0) / d["total"])
                _set(eid, message=f"{d.get('status', 'pulling')} {pct} percent", pct=pct)
    llm.local_status(force=True)


def _hf_download(eid: str, e: dict):
    from huggingface_hub import snapshot_download
    dest = _dest(e)
    dest.mkdir(parents=True, exist_ok=True)
    kw = {"allow_patterns": [e["pattern"]]} if e.get("pattern") else {}
    snapshot_download(repo_id=e["repo"], local_dir=str(dest), **kw)


def _install_worker(e: dict):
    eid = e["id"]
    try:
        _set(eid, state="running", message="starting", pct=0)
        if e["how"] == "ollama":
            _ollama_pull(eid, e["tag"])
        elif e["how"] == "url":
            for name, url in e["files"]:
                _download_url(eid, url, _dest(e) / name)
        elif e["how"] == "hf":
            _set(eid, message="downloading from Hugging Face")
            _hf_download(eid, e)
        if e["how"] != "ollama":
            _marker(e).write_text(time.strftime("%Y-%m-%d %H:%M"))
        _set(eid, state="done", message="installed", pct=100)
    except Exception as ex:  # noqa: BLE001
        _set(eid, state="error", message=str(ex)[:200])


def start_install(eid: str) -> tuple[bool, str]:
    e = BY_ID.get(eid)
    if not e:
        return False, "That model isn't in my catalog."
    if installed(e):
        return True, f"{e['name']} is already installed."
    job = JOBS.get(eid)
    if job and job["state"] == "running":
        return True, f"{e['name']} is already downloading ({job['message']})."
    why = can_install(e)
    if why:
        return False, why
    _set(eid, state="running", message="starting", pct=0)
    threading.Thread(target=_install_worker, args=(e,), daemon=True).start()
    return True, f"Started downloading {e['name']}, about {e['gb']} gigabytes. Ask me for the studio status to see progress."


def remove(eid: str) -> tuple[bool, str]:
    e = BY_ID.get(eid)
    if not e or e["how"] == "manual":
        return False, "I can only remove models I installed from my catalog."
    if e["how"] == "ollama":
        url = llm.local_status()["url"]
        if not url:
            return False, "Ollama isn't running."
        r = requests.delete(url + "/api/delete", json={"name": e["tag"]}, timeout=20)
        llm.local_status(force=True)
        return (r.ok, f"Removed {e['name']}." if r.ok else f"Ollama couldn't remove it: {r.text[:100]}")
    r = root()
    d = _dest(e)
    if r is None or d is None:
        return False, root_problem() or "studio is off"
    if e["how"] == "url":
        for name, _ in e["files"]:
            (d / name).unlink(missing_ok=True)
    elif e.get("pattern"):
        for f in d.glob(e["pattern"]):
            f.unlink(missing_ok=True)
    else:  # whole folder, but only if it is really inside the studio root
        if r.resolve() in d.resolve().parents:
            shutil.rmtree(d, ignore_errors=True)
    _marker(e).unlink(missing_ok=True)
    JOBS.pop(eid, None)
    return True, f"Removed {e['name']}."


# ------------------------------------------------------------------ locating things
def tool_python() -> Path | None:
    """Python of the studio's own virtual environment (kept on the SSD so torch never fills your laptop)."""
    r = root()
    if r is None:
        return None
    p = r / "venv" / "bin" / "python"
    return p if p.exists() else None


def comfy_urls() -> list[str]:
    urls = [config.COMFY_URL.rstrip("/")] if config.COMFY_URL else []
    for u in llm._candidate_urls():
        urls.append(u.rsplit(":", 1)[0] + ":8188")
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def comfy_url() -> str | None:
    for u in comfy_urls():
        try:
            if requests.get(u + "/system_stats", timeout=1.5).ok:
                return u
        except Exception:
            continue
    return None


# ------------------------------------------------------------------ progress of the thing being made
PROG: dict = {"busy": False, "kind": "", "what": "", "pct": 0, "stage": "", "started": 0.0, "error": "", "latest": None}
FOLDERS = {"image": "images", "music": "music", "speech": "speech", "transcript": "transcripts"}
OUTPUT_EXT = {"images": {".png", ".jpg", ".jpeg"}, "music": {".wav"}, "speech": {".wav"}, "transcripts": {".txt"}}


def prog_start(kind: str, what: str):
    PROG.update(busy=True, kind=kind, what=what, pct=2, stage="starting", started=time.time(), error="", latest=None)


def prog_update(pct: float | None = None, stage: str | None = None):
    if pct is not None:   # never go backwards, never reach 100 until it is really done
        PROG["pct"] = max(PROG["pct"], min(99, round(pct)))
    if stage:
        PROG["stage"] = stage


def prog_finish(path: Path | None = None, error: str = ""):
    PROG.update(busy=False, pct=100 if path else PROG["pct"], stage="done" if path else "failed", error=error)
    if path:
        PROG["latest"] = {"folder": path.parent.name, "name": path.name}


def prog_snapshot() -> dict:
    d = dict(PROG)
    d["elapsed"] = round(time.time() - PROG["started"]) if PROG["started"] else 0
    d["started_at"] = PROG["started"]
    return d


def list_outputs(folder: str | None = None, limit: int = 30) -> list[dict]:
    """Newest creations on the SSD. folder is one of images, music, speech, transcripts (or None for all)."""
    r = root()
    if r is None:
        return []
    items = []
    for f, exts in OUTPUT_EXT.items():
        if folder and f != folder:
            continue
        d = r / "outputs" / f
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if p.is_file() and p.suffix.lower() in exts:
                st = p.stat()
                items.append({"folder": f, "name": p.name, "mtime": st.st_mtime, "size": st.st_size})
    items.sort(key=lambda i: i["mtime"], reverse=True)
    return items[:limit]


def output_path(folder: str, name: str) -> Path | None:
    """The real file for a creation, or None. Only plain file names inside the four output folders."""
    r = root()
    if r is None or folder not in OUTPUT_EXT or not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    if Path(name).suffix.lower() not in OUTPUT_EXT[folder]:
        return None
    p = (r / "outputs" / folder / name)
    try:
        if p.is_file() and p.resolve().parent == (r / "outputs" / folder).resolve():
            return p
    except OSError:
        pass
    return None
