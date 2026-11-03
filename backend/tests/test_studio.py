"""v16 studio: SSD folder, catalog, installs, and the creation actions (no real models are used)."""
import time
from pathlib import Path

import pytest

import actions
import config
import studio
from actions import studio_actions as sa


@pytest.fixture(autouse=True)
def studio_state(monkeypatch, tmp_path):
    studio.JOBS.clear()
    sa.RECENT.clear()
    monkeypatch.setattr(config, "MODELS_ROOT", str(tmp_path / "ssd"))
    (tmp_path / "ssd").mkdir()
    monkeypatch.setattr(sa, "toast", lambda *a, **k: None)
    yield


def wait_idle():
    for _ in range(100):
        if not sa._BUSY.locked() and not any(j["state"] == "running" for j in studio.JOBS.values()):
            return
        time.sleep(0.05)
    raise AssertionError("background job never finished")


def fake_install(eid):
    e = studio.BY_ID[eid]
    d = studio._dest(e)
    d.mkdir(parents=True, exist_ok=True)
    studio._marker(e).write_text("x")


def test_catalog_is_sane():
    ids = [e["id"] for e in studio.CATALOG]
    assert len(ids) == len(set(ids))
    for e in studio.CATALOG:
        assert e["how"] in {"ollama", "url", "hf", "manual"}
        assert e["gb"] > 0 and e["tier"]
        if e["how"] == "url":
            assert all(u.startswith("https://") for _, u in e["files"])
        if e["how"] in {"url", "hf"}:
            assert e["dest"] and ".." not in e["dest"] and not e["dest"].startswith("/")


def test_root_problems(monkeypatch, tmp_path):
    assert studio.root_problem() is None
    monkeypatch.setattr(config, "MODELS_ROOT", "")
    assert "isn't set up" in studio.root_problem()
    monkeypatch.setattr(config, "MODELS_ROOT", str(tmp_path / "unplugged"))
    assert "plugged in" in studio.root_problem()


def test_unknown_and_manual_models_are_refused():
    assert studio.start_install("rm -rf")[0] is False
    ok, msg = studio.start_install("video-wan-1.3b")
    assert not ok and "manual" in msg
    assert studio.remove("agent-openclaw")[0] is False


def test_install_and_remove_are_risky_and_described():
    assert actions.is_risky("install_model", {"id": "tts-kokoro"})
    assert actions.is_risky("remove_model", {"id": "tts-kokoro"})
    assert "Kokoro" in actions.describe("install_model", {"id": "tts-kokoro"})
    assert not actions.is_risky("generate_image", {"prompt": "x"})


def test_install_refused_when_ssd_is_nearly_full(monkeypatch):
    monkeypatch.setattr(studio, "free_gb", lambda: 5.0)
    ok, msg = studio.start_install("image-sdxl-turbo")  # needs 6.9 GB
    assert not ok and "Not enough room" in msg


def test_install_refused_without_ssd(monkeypatch):
    monkeypatch.setattr(config, "MODELS_ROOT", "")
    ok, msg = studio.start_install("tts-kokoro")
    assert not ok and "isn't set up" in msg


def test_url_install_then_remove(monkeypatch):
    def fake_dl(eid, url, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"model")
    monkeypatch.setattr(studio, "_download_url", fake_dl)
    ok, msg = studio.start_install("tts-kokoro")
    assert ok
    wait_idle()
    assert studio.JOBS["tts-kokoro"]["state"] == "done"
    e = studio.BY_ID["tts-kokoro"]
    assert studio.installed(e)
    assert (studio._dest(e) / "kokoro-v1.0.onnx").exists()
    assert "already installed" in studio.start_install("tts-kokoro")[1]
    ok, _ = studio.remove("tts-kokoro")
    assert ok and not studio.installed(e) and not (studio._dest(e) / "kokoro-v1.0.onnx").exists()


def test_failed_download_is_reported(monkeypatch):
    def boom(*a):
        raise RuntimeError("network down")
    monkeypatch.setattr(studio, "_download_url", boom)
    studio.start_install("tts-kokoro")
    wait_idle()
    assert studio.JOBS["tts-kokoro"]["state"] == "error"
    assert not studio.installed(studio.BY_ID["tts-kokoro"])


def test_remove_never_leaves_the_studio_folder(monkeypatch, tmp_path):
    outside = tmp_path / "precious"
    outside.mkdir()
    (outside / "keep.txt").write_text("x")
    evil = dict(studio.BY_ID["stt-whisper-small"], dest="../precious")
    monkeypatch.setitem(studio.BY_ID, "stt-whisper-small", evil)
    studio.remove("stt-whisper-small")
    assert (outside / "keep.txt").exists()


def test_status_text(monkeypatch):
    monkeypatch.setattr(studio.llm, "local_status", lambda force=False: {"url": None, "models": []})
    fake_install("tts-kokoro")
    text = actions.run("studio_status", {}).message
    assert "free" in text and "Kokoro" in text


def test_generate_image_needs_model_and_comfy(monkeypatch):
    r = actions.run("generate_image", {"prompt": "a cat"})
    assert not r.ok and "isn't installed" in r.message
    fake_install("image-sdxl-turbo")
    monkeypatch.setattr(studio, "comfy_url", lambda: None)
    r = actions.run("generate_image", {"prompt": "a cat"})
    assert not r.ok and "ComfyUI" in r.message
    assert not actions.run("generate_image", {"prompt": "  "}).ok


def test_generate_image_runs_in_background(monkeypatch):
    fake_install("image-sdxl-turbo")
    monkeypatch.setattr(studio, "comfy_url", lambda: "http://x")

    def fake_make(prompt, size, out):
        out.write_bytes(b"png")
        return out, prompt
    monkeypatch.setattr(sa, "_comfy_make", fake_make)
    r = actions.run("generate_image", {"prompt": "neon city"})
    assert r.ok and "progress" in r.message
    wait_idle()
    assert sa.RECENT and sa.RECENT[-1]["kind"] == "image"
    p = Path(sa.RECENT[-1]["path"])
    assert p.exists() and p.parent == studio.root() / "outputs" / "images"


def test_second_creation_is_refused_while_busy(monkeypatch):
    fake_install("music-musicgen-small")
    gate = []

    def slow(mode, args, timeout):
        while not gate:
            time.sleep(0.02)
        Path(args["out"]).write_bytes(b"wav")
        return {"ok": True, "path": args["out"]}
    monkeypatch.setattr(sa, "_worker", slow)
    assert actions.run("make_music", {"prompt": "lofi", "seconds": 8}).ok
    r = actions.run("make_music", {"prompt": "again"})
    assert not r.ok and "busy" in r.message
    gate.append(1)
    wait_idle()
    assert sa.RECENT[-1]["kind"] == "music"


def test_music_seconds_are_clamped(monkeypatch):
    fake_install("music-musicgen-small")
    seen = {}

    def fake(mode, args, timeout):
        seen.update(args)
        Path(args["out"]).write_bytes(b"w")
        return {"ok": True, "path": args["out"]}
    monkeypatch.setattr(sa, "_worker", fake)
    actions.run("make_music", {"prompt": "x", "seconds": 9999})
    wait_idle()
    assert seen["seconds"] == 30


def test_transcribe_only_picks_audio_and_video(monkeypatch, tmp_path):
    fake_install("stt-whisper-small")
    from actions import files
    doc = tmp_path / "lecture.pdf"
    doc.write_text("x")
    monkeypatch.setattr(files, "search", lambda q, limit=8, max_depth=4: [doc])
    r = actions.run("transcribe_audio", {"query": "lecture"})
    assert not r.ok and "couldn't find" in r.message
    rec = tmp_path / "lecture.mp3"
    rec.write_bytes(b"x")
    monkeypatch.setattr(files, "search", lambda q, limit=8, max_depth=4: [doc, rec])

    def fake(mode, args, timeout):
        assert args["file"] == str(rec)
        Path(args["out"]).write_text("hello world")
        return {"ok": True, "path": args["out"], "text": "hello world"}
    monkeypatch.setattr(sa, "_worker", fake)
    assert actions.run("transcribe_audio", {"query": "lecture"}).ok
    wait_idle()
    assert "hello world" in actions.run("read_transcript", {}).message


def test_worker_failure_is_reported(monkeypatch):
    fake_install("tts-kokoro")

    def bad(mode, args, timeout):
        raise RuntimeError("onnx exploded")
    monkeypatch.setattr(sa, "_worker", bad)
    assert actions.run("make_speech", {"text": "hi"}).ok  # started
    wait_idle()
    assert not sa.RECENT
    import activity
    assert any("failed" in str(x) for x in activity.recent(5))


def test_workflow_carries_prompt_and_size():
    wf = sa._workflow("a red fox", 123, 512)
    assert wf["2"]["inputs"]["text"] == "a red fox"
    assert wf["4"]["inputs"]["width"] == 512 and wf["5"]["inputs"]["seed"] == 123
