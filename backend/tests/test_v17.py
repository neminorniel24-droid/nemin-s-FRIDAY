"""v17: progress, the creations viewer endpoints, and the natural voice endpoint."""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
import main
import studio
import tts
from actions import studio_actions as sa

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def ssd(monkeypatch, tmp_path):
    (tmp_path / "ssd").mkdir()
    monkeypatch.setattr(config, "MODELS_ROOT", str(tmp_path / "ssd"))
    monkeypatch.setattr(sa, "toast", lambda *a, **k: None)
    studio.JOBS.clear()
    sa.RECENT.clear()
    studio.PROG.update(busy=False, kind="", what="", pct=0, stage="", started=0.0, error="", latest=None)
    yield


def make(folder, name, data=b"x"):
    d = studio.root() / "outputs" / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(data)


def test_progress_only_moves_forward_and_never_hits_100_early():
    studio.prog_start("image", "a cat")
    studio.prog_update(50, "drawing")
    studio.prog_update(20)
    assert studio.PROG["pct"] == 50
    studio.prog_update(150)
    assert studio.PROG["pct"] == 99
    p = studio.root() / "outputs" / "images" / "a.png"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"png")
    studio.prog_finish(p)
    snap = client.get("/studio/progress").json()
    assert snap["busy"] is False and snap["pct"] == 100 and snap["latest"] == {"folder": "images", "name": "a.png"}


def test_failed_job_reports_error_not_100():
    studio.prog_start("music", "lofi")
    studio.prog_update(40, "composing")
    studio.prog_finish(None, "boom")
    snap = client.get("/studio/progress").json()
    assert snap["pct"] == 40 and snap["error"] == "boom" and snap["stage"] == "failed"


def test_background_job_sets_and_clears_progress(monkeypatch):
    def slow(prompt, size, out):
        studio.prog_update(60, "drawing")
        out.write_bytes(b"png")
        return out, prompt
    monkeypatch.setattr(sa, "_comfy_make", slow)
    e = studio.BY_ID["image-sdxl-turbo"]
    d = studio._dest(e)
    d.mkdir(parents=True)
    studio._marker(e).write_text("x")
    monkeypatch.setattr(studio, "comfy_url", lambda: "http://x")
    import actions
    assert actions.run("generate_image", {"prompt": "fox"}).ok
    for _ in range(100):
        if not studio.PROG["busy"]:
            break
        time.sleep(0.05)
    snap = client.get("/studio/progress").json()
    assert snap["busy"] is False and snap["pct"] == 100 and snap["latest"]["folder"] == "images"


def test_files_listing_and_download():
    make("images", "one.png", b"PNGDATA")
    make("music", "two.wav", b"WAVDATA")
    make("images", "notes.exe", b"nope")      # wrong extension is never listed
    items = client.get("/studio/files").json()["items"]
    assert {i["name"] for i in items} == {"one.png", "two.wav"}
    assert [i["name"] for i in client.get("/studio/files?folder=images").json()["items"]] == ["one.png"]
    r = client.get("/studio/file/images/one.png")
    assert r.status_code == 200 and r.content == b"PNGDATA"


@pytest.mark.parametrize("folder,name", [
    ("images", "../../backend/.env"), ("images", "..%2F..%2Fx.png"), ("images", "a/b.png"),
    ("outputs", "one.png"), ("images", ".hidden.png"), ("images", "missing.png"), ("images", "notes.exe"),
    ("images", "..\\x.png"),
])
def test_file_endpoint_refuses_anything_odd(folder, name):
    make("images", "one.png")
    make("images", "notes.exe")
    assert client.get(f"/studio/file/{folder}/{name}").status_code in (404, 405)


def test_open_endpoint_validates(monkeypatch):
    make("images", "one.png")
    opened = []
    monkeypatch.setattr(sa, "open_path", lambda p: (opened.append(p), sa.Result(True, "Opening."))[1])
    assert client.post("/studio/open", json={"folder": "images", "name": "../x.png"}).status_code == 404
    assert client.post("/studio/open", json={"folder": "images", "name": "one.png"}).json()["ok"] is True
    assert opened and opened[0].name == "one.png"


def test_show_creations_action():
    import actions
    assert not actions.run("show_creations", {}).ok
    make("images", "one.png")
    r = actions.run("show_creations", {})
    assert r.ok and r.ui == {"gallery": True}


def test_tts_endpoint_503_when_off(monkeypatch):
    monkeypatch.setattr(tts, "available", lambda: False)
    assert client.post("/tts", json={"text": "hello"}).status_code == 503
    assert client.get("/health").json()["tts_natural"] is False


def test_tts_endpoint_returns_wav_and_falls_back_on_error(monkeypatch):
    monkeypatch.setattr(tts, "available", lambda: True)
    monkeypatch.setattr(tts, "synth", lambda text, persona_key=None: b"RIFFwav")
    r = client.post("/tts", json={"text": "hello"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content == b"RIFFwav"

    def boom(text, persona_key=None):
        raise RuntimeError("helper died")
    monkeypatch.setattr(tts, "synth", boom)
    assert client.post("/tts", json={"text": "hello"}).status_code == 503


def test_tts_turns_itself_off_for_a_minute_after_failure(monkeypatch):
    e = studio.BY_ID["tts-kokoro"]
    studio._dest(e).mkdir(parents=True)
    studio._marker(e).write_text("x")
    monkeypatch.setattr(studio, "tool_python", lambda: Path("/nonexistent/python"))
    monkeypatch.setattr(tts, "_down_until", 0.0)
    assert tts.available() is True
    (studio.root() / "logs").mkdir(exist_ok=True)
    with pytest.raises(Exception):
        tts.synth("hello")
    assert tts.available() is False


def test_prompt_tells_her_to_speak_cleanly():
    import persona
    text = persona.build_system_prompt("- x: y")
    assert "for example" in text and "e.g." in text and "URLs" in text


def test_voice_helper_end_to_end_with_stub_libraries(monkeypatch, tmp_path):
    """Runs the real studio_worker.py serve loop with tiny fake kokoro_onnx / soundfile modules."""
    import sys
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "kokoro_onnx.py").write_text(
        "class Kokoro:\n    def __init__(self, a, b): pass\n"
        "    def create(self, text, voice, speed, lang):\n"
        "        if voice == 'bad_voice': raise ValueError('no such voice')\n"
        "        return ([0.0] * 4, 24000)\n")
    (stubs / "soundfile.py").write_text("def write(path, data, rate):\n    open(path, 'wb').write(b'RIFF' + bytes(len(data)))\n")
    monkeypatch.setenv("PYTHONPATH", str(stubs))
    e = studio.BY_ID["tts-kokoro"]
    studio._dest(e).mkdir(parents=True)
    studio._marker(e).write_text("x")
    (studio.root() / "logs").mkdir(exist_ok=True)
    monkeypatch.setattr(studio, "tool_python", lambda: Path(sys.executable))
    monkeypatch.setattr(tts, "_down_until", 0.0)
    try:
        wav = tts.synth("Hello there.", "jarvis")
        assert wav.startswith(b"RIFF")
        monkeypatch.setitem(tts.VOICES, "friday", ("bad_voice", 1.0))   # unknown voice still speaks
        assert tts.synth("Second sentence.", "friday").startswith(b"RIFF")
    finally:
        tts._stop()
