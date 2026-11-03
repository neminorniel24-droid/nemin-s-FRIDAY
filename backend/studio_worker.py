"""
Runs OUTSIDE the main backend, inside the studio's own virtual environment on your SSD, so heavy libraries
(torch, transformers, onnxruntime) never touch your laptop's small drive or slow the backend.

Usage:  python studio_worker.py <music|speech|transcribe> '<json args>'
        python studio_worker.py serve '<json args>'     (stays running and speaks sentences for the live voice)
One-shot modes print one JSON line:  {"ok": true, "path": "...", "text": "..."}  or  {"ok": false, "error": "..."}
If args has "progress", the file gets "0.42|stage text" as the work moves along.
"""
import json
import sys
from pathlib import Path


def _prog(a: dict, frac: float, stage: str):
    f = a.get("progress")
    if f:
        try:
            Path(f).write_text(f"{frac:.3f}|{stage}")
        except OSError:
            pass


def music(a: dict) -> dict:
    import numpy as np
    import torch
    from scipy.io import wavfile
    from transformers import AutoProcessor, MusicgenForConditionalGeneration, StoppingCriteria, StoppingCriteriaList

    _prog(a, 0.02, "loading the music model")
    src = a["model_dir"]
    proc = AutoProcessor.from_pretrained(src)
    model = MusicgenForConditionalGeneration.from_pretrained(src)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(dev)
    inputs = proc(text=[a["prompt"]], padding=True, return_tensors="pt").to(dev)
    tokens = int(max(5, min(30, a.get("seconds", 10))) * 50)  # MusicGen makes 50 tokens per second

    class Tick(StoppingCriteria):  # called once per step: this is how we know how far along we are
        n = 0

        def __call__(self, input_ids, scores, **kw):
            self.n += 1
            if self.n % 8 == 0:
                _prog(a, 0.1 + 0.88 * min(1.0, self.n / tokens), f"composing, {min(100, round(100 * self.n / tokens))} percent")
            return torch.zeros(input_ids.shape[0], dtype=torch.bool, device=input_ids.device)

    _prog(a, 0.1, "composing")
    with torch.no_grad():
        audio = model.generate(**inputs, do_sample=True, guidance_scale=3, max_new_tokens=tokens,
                               stopping_criteria=StoppingCriteriaList([Tick()]))
    rate = model.config.audio_encoder.sampling_rate
    wavfile.write(a["out"], rate, audio[0, 0].cpu().numpy().astype(np.float32))
    return {"ok": True, "path": a["out"]}


def _kokoro(model_dir: str):
    from kokoro_onnx import Kokoro
    d = Path(model_dir)
    return Kokoro(str(d / "kokoro-v1.0.onnx"), str(d / "voices-v1.0.bin"))


def _say(k, text: str, voice: str, speed: float):
    try:
        return k.create(text, voice=voice, speed=speed, lang="en-us")
    except Exception:  # an unknown voice name must never break her: use the default one
        return k.create(text, voice="af_heart", speed=speed, lang="en-us")


def speech(a: dict) -> dict:
    import soundfile as sf
    _prog(a, 0.1, "loading the voice")
    k = _kokoro(a["model_dir"])
    _prog(a, 0.4, "speaking")
    samples, rate = _say(k, a["text"], a.get("voice", "af_heart"), float(a.get("speed", 1.0)))
    sf.write(a["out"], samples, rate)
    return {"ok": True, "path": a["out"]}


def transcribe(a: dict) -> dict:
    from faster_whisper import WhisperModel

    _prog(a, 0.05, "loading the listening model")
    model = WhisperModel(a["model_dir"], device="cpu", compute_type="int8")
    segments, info = model.transcribe(a["file"], vad_filter=True)
    parts = []
    for s in segments:
        parts.append(s.text.strip())
        if info.duration:
            _prog(a, 0.1 + 0.88 * min(1.0, s.end / info.duration), f"listening, {min(100, round(100 * s.end / info.duration))} percent")
    text = " ".join(parts)
    Path(a["out"]).write_text(text, encoding="utf-8")
    return {"ok": True, "path": a["out"], "text": text, "language": info.language}


def serve(a: dict):
    """Live voice: load Kokoro once, then answer one JSON line per sentence."""
    import soundfile as sf
    k = _kokoro(a["model_dir"])
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        try:
            req = json.loads(line)
            samples, rate = _say(k, req["text"], req.get("voice", "af_heart"), float(req.get("speed", 1.0)))
            sf.write(req["out"], samples, rate)
            print(json.dumps({"ok": True}), flush=True)
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}), flush=True)


MODES = {"music": music, "speech": speech, "transcribe": transcribe}

if __name__ == "__main__":
    try:
        mode, args = sys.argv[1], json.loads(sys.argv[2])
        if mode == "serve":
            serve(args)
        else:
            print(json.dumps(MODES[mode](args)))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}))
