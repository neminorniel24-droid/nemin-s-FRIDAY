"""
The natural offline voice. Kokoro stays loaded in a small helper process (studio_worker.py serve) so each
sentence takes a moment instead of seconds. Anything that goes wrong turns it off for a minute and the
browser voice takes over, so she never goes silent.
"""
import atexit
import json
import select
import subprocess
import threading
import time
import uuid
from pathlib import Path

import config
import personas
import studio

# Kokoro voice and speed for each mode. An unknown voice falls back to af_heart inside the worker.
VOICES = {
    "nemiii": ("af_heart", 1.0),
    "jarvis": ("bm_george", 0.97),
    "friday": ("af_nicole", 1.05),
    "edith": ("af_sarah", 1.0),
}

_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_down_until = 0.0


def available() -> bool:
    """Cheap check used by /health: the voice is installed and the studio tools exist."""
    if time.time() < _down_until or studio.root() is None or studio.tool_python() is None:
        return False
    return studio.installed(studio.BY_ID["tts-kokoro"])


def _stop():
    global _proc
    p, _proc = _proc, None
    if p and p.poll() is None:
        p.kill()


atexit.register(_stop)


def _readline(p: subprocess.Popen, timeout: float) -> dict:
    ready, _, _ = select.select([p.stdout], [], [], timeout)
    if not ready:
        raise TimeoutError("the voice helper did not answer")
    line = p.stdout.readline()
    if not line:
        raise RuntimeError("the voice helper stopped")
    return json.loads(line)


def _start() -> subprocess.Popen:
    global _proc
    if _proc and _proc.poll() is None:
        return _proc
    py = studio.tool_python()
    script = Path(__file__).resolve().parent / "studio_worker.py"
    model_dir = str(studio.root() / studio.BY_ID["tts-kokoro"]["dest"])
    logf = open(studio.root() / "logs" / "tts.log", "a")
    _proc = subprocess.Popen([str(py), str(script), "serve", json.dumps({"model_dir": model_dir})],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=logf, text=True, bufsize=1)
    first = _readline(_proc, 90)
    if not first.get("ready"):
        raise RuntimeError("the voice helper did not start")
    return _proc


def synth(text: str, persona_key: str | None = None) -> bytes:
    """WAV bytes for one short piece of text. Raises if the natural voice is not working."""
    global _down_until
    text = text.strip()[:700]
    if not text:
        raise ValueError("nothing to say")
    voice, speed = VOICES.get(persona_key or personas.current().key, VOICES["nemiii"])
    if config.TTS_VOICE != "af_heart" and (persona_key or personas.current().key) == "nemiii":
        voice = config.TTS_VOICE
    tmp_dir = studio.root() / "cache" / "tts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out = tmp_dir / f"{uuid.uuid4().hex}.wav"
    with _lock:
        try:
            p = _start()
            p.stdin.write(json.dumps({"text": text, "voice": voice, "speed": speed, "out": str(out)}) + "\n")
            p.stdin.flush()
            res = _readline(p, 40)
            if not res.get("ok"):
                raise RuntimeError(res.get("error", "voice error"))
            return out.read_bytes()
        except Exception:
            _stop()
            _down_until = time.time() + 60
            raise
        finally:
            out.unlink(missing_ok=True)
