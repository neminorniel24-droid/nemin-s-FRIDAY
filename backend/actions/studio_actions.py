"""
The studio actions: install models to your SSD, make pictures, music and speech, transcribe audio.

Making things is slow, so each creation runs in the background (one at a time, because 6 GB of video
memory is not enough for two). When it finishes you get a Windows notification and it is in the
activity log. Everything is saved under MODELS_ROOT/outputs on your SSD.
"""
import json
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

import requests

import activity
import studio
from . import Result, action
from .winshell import ps_quote, run_ps, toast

RECENT: list[dict] = []          # newest last: {kind, path, text}
_BUSY = threading.Lock()
_current = {"what": ""}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".mp4", ".mkv", ".webm", ".mov"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "creation"


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _finish(kind: str, ok: bool, msg: str, path: Path | None = None, text: str = ""):
    if ok and path:
        RECENT.append({"kind": kind, "path": str(path), "text": text})
        del RECENT[:-20]
    studio.prog_finish(path if ok else None, "" if ok else msg)
    activity.record("studio", f"finished_{kind}", {}, ok, msg)
    try:
        toast("Nemiii", msg[:120])
    except Exception:
        pass


def _creep(started: float, seen_real: bool, cap: float = 90.0):
    """When a tool cannot report real progress, move the bar slowly so you can see it is alive."""
    if not seen_real:
        studio.prog_update(min(cap, 4 + (time.time() - started) * 1.2))


def _background(kind: str, what: str, job) -> Result:
    """Run job() -> (path, text) in a thread. Only one creation at a time."""
    if not _BUSY.acquire(blocking=False):
        return Result(False, f"I'm still busy with {_current['what']}. Ask me again when it is done.")
    _current["what"] = what
    studio.prog_start(kind, what)

    def runner():
        try:
            path, text = job()
            _finish(kind, True, f"Your {kind} is ready: {Path(path).name}", Path(path), text)
        except Exception as e:  # noqa: BLE001
            _finish(kind, False, f"The {kind} failed: {str(e)[:150]}")
        finally:
            _current["what"] = ""
            _BUSY.release()

    threading.Thread(target=runner, daemon=True).start()
    return Result(True, f"On it. I'm making {what}. You can watch the progress on screen, and I'll tell you when it's ready.")


def _need(model_id: str) -> str | None:
    problem = studio.root_problem()
    if problem:
        return problem
    e = studio.BY_ID[model_id]
    if not studio.installed(e):
        return f"{e['name']} isn't installed yet. Say: install {e['name']}."
    return None


# ------------------------------------------------------------------ models
@action("studio_status", "info", "Studio status: SSD free space, which models are installed, what is being made. args: {}")
def studio_status(a: dict) -> Result:
    text = studio.summary()
    if _current["what"]:
        text += f" Making now: {_current['what']}."
    if RECENT:
        text += f" Latest creation: {Path(RECENT[-1]['path']).name}."
    return Result(True, text)


def _model_name(a: dict) -> str:
    return studio.BY_ID.get(str(a.get("id", "")), {}).get("name", str(a.get("id", "that model")))


@action("install_model", "pc",
        'Download a free model from the catalog onto the SSD. args: {"id": "image-sdxl-turbo"}. '
        "ids: chat-llama3.2-3b, chat-qwen2.5-7b, vision-moondream, vision-gemma3-4b, stt-whisper-small, tts-kokoro, image-sdxl-turbo, music-musicgen-small",
        risky=True, describe=lambda a: f"download {_model_name(a)}")
def install_model(a: dict) -> Result:
    ok, msg = studio.start_install(str(a.get("id", "")))
    return Result(ok, msg)


@action("remove_model", "pc", 'Delete a model I installed, to free SSD space. args: {"id": "image-sdxl-turbo"}',
        risky=True, describe=lambda a: f"delete {_model_name(a)}")
def remove_model(a: dict) -> Result:
    ok, msg = studio.remove(str(a.get("id", "")))
    return Result(ok, msg)


# ------------------------------------------------------------------ pictures (ComfyUI)
def _workflow(prompt: str, seed: int, size: int) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_turbo_1.0_fp16.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, watermark, text", "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": size, "height": size, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": seed, "steps": 4, "cfg": 1.0,
              "sampler_name": "euler_ancestral", "scheduler": "simple", "positive": ["2", 0], "negative": ["3", 0],
              "latent_image": ["4", 0], "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "nemiii"}},
    }


def _comfy_watch(base: str, client_id: str, stop: threading.Event, seen: dict):
    """Listen to ComfyUI's own progress messages. Best effort: if anything is off, the creeping bar still works."""
    try:
        from websockets.sync.client import connect
        ws = connect(base.replace("http", "ws", 1) + "/ws?clientId=" + client_id, open_timeout=3)
    except Exception:
        return
    try:
        while not stop.is_set():
            try:
                msg = ws.recv(timeout=1)
            except TimeoutError:
                continue
            if not isinstance(msg, str):
                continue
            d = json.loads(msg)
            t, data = d.get("type"), d.get("data", {})
            if t == "execution_start":
                studio.prog_update(8, "loading the model")
            elif t == "progress" and data.get("max"):
                seen["real"] = True
                v, m = data["value"], data["max"]
                studio.prog_update(15 + 80 * v / m, f"drawing, step {v} of {m}")
            elif t == "executing" and data.get("node") is None and data.get("prompt_id"):
                studio.prog_update(97, "saving")
    except Exception:
        pass
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _comfy_make(prompt: str, size: int, out: Path) -> tuple[Path, str]:
    base = studio.comfy_url()
    if not base:
        raise RuntimeError("ComfyUI isn't running. Start it with: bash scripts/studio-start.sh")
    seed = int(uuid.uuid4().int % (2 ** 32))
    client_id = uuid.uuid4().hex
    stop, seen = threading.Event(), {"real": False}
    threading.Thread(target=_comfy_watch, args=(base, client_id, stop, seen), daemon=True).start()
    started = time.time()
    try:
        studio.prog_update(5, "sending to the picture engine")
        r = requests.post(base + "/prompt", json={"prompt": _workflow(prompt, seed, size), "client_id": client_id}, timeout=20)
        if not r.ok:
            raise RuntimeError(f"ComfyUI refused the job: {r.text[:150]}")
        pid = r.json()["prompt_id"]
        deadline = time.time() + 600       # the first run loads a 7 GB model, so allow a while
        while time.time() < deadline:
            h = requests.get(f"{base}/history/{pid}", timeout=10).json().get(pid)
            if h and h.get("outputs"):
                studio.prog_update(98, "saving")
                img = next(i for node in h["outputs"].values() for i in node.get("images", []))
                data = requests.get(f"{base}/view", params={"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                                                            "type": img.get("type", "output")}, timeout=30)
                data.raise_for_status()
                out.write_bytes(data.content)
                return out, prompt
            if h and h.get("status", {}).get("status_str") == "error":
                raise RuntimeError("ComfyUI reported an error while drawing.")
            _creep(started, seen["real"])
            time.sleep(1.0)
        raise RuntimeError("Drawing took too long.")
    finally:
        stop.set()


@action("generate_image", "pc", 'Draw a picture from a description with the offline image model. args: {"prompt": "a neon city at night"}')
def generate_image(a: dict) -> Result:
    prompt = str(a.get("prompt", "")).strip()[:400]
    if not prompt:
        return Result(False, "What should I draw?")
    why = _need("image-sdxl-turbo")
    if why:
        return Result(False, why)
    if not studio.comfy_url():
        return Result(False, "ComfyUI isn't running. Start it with: bash scripts/studio-start.sh")
    out = studio.out_dir("images") / f"{_stamp()}-{_slug(prompt)}.png"
    return _background("image", f"a picture of {prompt[:60]}", lambda: _comfy_make(prompt, 512, out))


# ------------------------------------------------------------------ worker based: music, speech, transcribe
def _read_progress(f: Path) -> tuple[float, str] | None:
    try:
        frac, stage = f.read_text().split("|", 1)
        return float(frac), stage.strip()
    except Exception:
        return None


def _worker(mode: str, args: dict, timeout: int) -> dict:
    py = studio.tool_python()
    if py is None:
        raise RuntimeError("The studio tools aren't installed. Run: bash scripts/studio-setup.sh --tools")
    script = Path(__file__).resolve().parent.parent / "studio_worker.py"
    prog = Path(args["out"] + ".progress")
    log = Path(args["out"] + ".log")
    args = dict(args, progress=str(prog))
    started, seen = time.time(), False
    with open(log, "w") as errf:
        p = subprocess.Popen([str(py), str(script), mode, json.dumps(args)], stdout=subprocess.PIPE, stderr=errf, text=True)
        try:
            while p.poll() is None:
                if time.time() - started > timeout:
                    p.kill()
                    raise RuntimeError("That took too long, so I stopped it.")
                got = _read_progress(prog)
                if got:
                    seen = True
                    studio.prog_update(5 + 90 * got[0], got[1])
                else:
                    _creep(started, seen)
                time.sleep(0.5)
            stdout = p.stdout.read() if p.stdout else ""
        finally:
            if p.poll() is None:
                p.kill()
    tail = ""
    try:
        lines = [ln for ln in log.read_text().splitlines() if ln.strip()]
        tail = lines[-1][:200] if lines else ""
    except OSError:
        pass
    for f in (prog, log):
        f.unlink(missing_ok=True)
    rows = [ln for ln in stdout.strip().splitlines() if ln.startswith("{")]
    if not rows:
        raise RuntimeError(tail or "the worker printed nothing")
    d = json.loads(rows[-1])
    if not d.get("ok"):
        raise RuntimeError(d.get("error", "unknown error"))
    return d


@action("make_music", "pc", 'Compose a short instrumental clip (5-30 seconds). args: {"prompt": "calm lo-fi piano", "seconds": 12}')
def make_music(a: dict) -> Result:
    prompt = str(a.get("prompt", "")).strip()[:300]
    if not prompt:
        return Result(False, "What kind of music?")
    why = _need("music-musicgen-small")
    if why:
        return Result(False, why)
    try:
        seconds = max(5, min(30, int(a.get("seconds", 10))))
    except (TypeError, ValueError):
        seconds = 10
    out = studio.out_dir("music") / f"{_stamp()}-{_slug(prompt)}.wav"
    model_dir = str(studio.root() / studio.BY_ID["music-musicgen-small"]["dest"])

    def job():
        d = _worker("music", {"prompt": prompt, "seconds": seconds, "model_dir": model_dir, "out": str(out)}, 900)
        return Path(d["path"]), prompt
    return _background("music", f"{seconds} seconds of {prompt[:50]}", job)


@action("make_speech", "pc", 'Turn text into a spoken audio file with a natural offline voice. args: {"text": "Hello there"}')
def make_speech(a: dict) -> Result:
    text = str(a.get("text", "")).strip()[:1500]
    if not text:
        return Result(False, "What should I say?")
    why = _need("tts-kokoro")
    if why:
        return Result(False, why)
    import config
    out = studio.out_dir("speech") / f"{_stamp()}-{_slug(text)}.wav"
    model_dir = str(studio.root() / studio.BY_ID["tts-kokoro"]["dest"])

    def job():
        d = _worker("speech", {"text": text, "voice": config.TTS_VOICE, "model_dir": model_dir, "out": str(out)}, 300)
        return Path(d["path"]), text
    return _background("speech", "a voice recording", job)


@action("transcribe_audio", "pc",
        'Turn a recording or video into text (offline Whisper). Looks in Documents, Downloads, Desktop and the studio. args: {"query": "lecture"}')
def transcribe_audio(a: dict) -> Result:
    from . import files
    query = str(a.get("query", "")).strip()
    if not query:
        return Result(False, "Which recording?")
    why = _need("stt-whisper-small")
    if why:
        return Result(False, why)
    hits = [p for p in files.search(query, limit=20) if p.suffix.lower() in AUDIO_EXT]
    r = studio.root()
    if r:
        hits += [p for p in (r / "outputs").rglob("*") if p.suffix.lower() in AUDIO_EXT and query.lower() in p.name.lower()]
    if not hits:
        return Result(False, f"I couldn't find an audio or video file matching {query}.")
    src = hits[0]
    out = studio.out_dir("transcripts") / f"{_stamp()}-{_slug(src.stem)}.txt"
    model_dir = str(r / studio.BY_ID["stt-whisper-small"]["dest"])

    def job():
        d = _worker("transcribe", {"file": str(src), "model_dir": model_dir, "out": str(out)}, 3600)
        return Path(d["path"]), d.get("text", "")
    return _background("transcript", f"a transcript of {src.name}", job)


# ------------------------------------------------------------------ look at results
def open_path(path: Path) -> Result:
    """Open a file in Windows with its normal program."""
    try:
        win = subprocess.run(["wslpath", "-w", str(path)], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        win = ""
    if not win:
        return Result(False, "I couldn't work out where that file is on Windows.")
    ok, out = run_ps(f"Start-Process -LiteralPath {ps_quote(win)}")
    return Result(True, f"Opening {path.name}.") if ok else Result(False, out)


@action("open_creation", "pc", 'Open the latest thing I made (picture, music, speech, transcript). args: {"kind": "image|music|speech|transcript"}')
def open_creation(a: dict) -> Result:
    kind = str(a.get("kind", "")).strip().lower() or None
    items = [i for i in RECENT if not kind or i["kind"] == kind]
    path = Path(items[-1]["path"]) if items else None
    if path is None:      # nothing this session: use the newest file on disk
        folder = studio.FOLDERS.get(kind or "")
        newest = studio.list_outputs(folder, 1)
        path = studio.output_path(newest[0]["folder"], newest[0]["name"]) if newest else None
    if path is None or not path.exists():
        return Result(False, "I haven't made anything yet.")
    return open_path(path)


@action("show_creations", "pc", "Show the gallery of everything I made on screen. args: {}")
def show_creations(a: dict) -> Result:
    if not studio.list_outputs(None, 1):
        return Result(False, "I haven't made anything yet.")
    return Result(True, "Here is what I made.", ui={"gallery": True})


@action("read_transcript", "info", "Read the text of the latest transcript I made. args: {}")
def read_transcript(a: dict) -> Result:
    items = [i for i in RECENT if i["kind"] == "transcript"]
    if not items:
        return Result(False, "I haven't transcribed anything this session.")
    t = items[-1]["text"]
    return Result(True, "Transcript:\n" + (t[:6000] + (" (cut short)" if len(t) > 6000 else "")))
