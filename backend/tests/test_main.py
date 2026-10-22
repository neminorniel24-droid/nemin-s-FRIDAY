import json

import pytest
from fastapi.testclient import TestClient

import actions
import llm
import main
import memory
from actions import Result, pc

client = TestClient(main.app)


def script_llm(monkeypatch, *replies):
    """Make the 'model' say the given JSON replies, one per call."""
    calls = []
    it = iter(replies)

    def fake(messages, json_mode=True):
        calls.append(messages)
        return json.dumps(next(it)), "test"
    monkeypatch.setattr(llm, "chat", fake)
    return calls


def test_just_talking(monkeypatch):
    script_llm(monkeypatch, {"reply": "I'm here.", "actions": []})
    r = client.post("/chat", json={"message": "hello"}).json()
    assert r["reply"] == "I'm here." and r["actions"] == []
    assert [m["role"] for m in memory.get_history()] == ["user", "assistant"]


def test_pc_action_runs(monkeypatch):
    monkeypatch.setattr(pc, "run_ps", lambda s, t=25: (True, "OK"))
    script_llm(monkeypatch, {"reply": "Opening Chrome.", "actions": [{"name": "open_app", "args": {"name": "chrome"}}]})
    r = client.post("/chat", json={"message": "open chrome"}).json()
    assert r["reply"] == "Opening Chrome." and r["actions"][0]["ok"]


def test_failed_action_makes_her_honest(monkeypatch):
    monkeypatch.setattr(pc, "run_ps", lambda s, t=25: (True, "NOTFOUND"))
    script_llm(monkeypatch, {"reply": "Opening it now!", "actions": [{"name": "open_app", "args": {"name": "ghost"}}]})
    r = client.post("/chat", json={"message": "open ghost"}).json()
    assert "couldn't" in r["reply"].lower() and "Opening it now" not in r["reply"]


def test_info_action_data_goes_back_to_model(monkeypatch):
    monkeypatch.setattr(actions.REGISTRY["tell_news"], "fn", lambda a: Result(True, "Headlines:\nMoon base approved"))
    calls = script_llm(
        monkeypatch,
        {"reply": "Let me check.", "actions": [{"name": "tell_news", "args": {}}]},
        {"reply": "A moon base was approved.", "actions": []},
    )
    r = client.post("/chat", json={"message": "what's the news"}).json()
    assert r["reply"] == "A moon base was approved."
    assert "Moon base approved" in calls[1][-1]["content"]  # real data reached the model


def test_chain_of_actions(monkeypatch):
    monkeypatch.setattr(pc, "run_ps", lambda s, t=25: (True, "OK"))
    script_llm(monkeypatch, {"reply": "On it.", "actions": [
        {"name": "set_volume", "args": {"level": 30}}, {"name": "media_control", "args": {"command": "play_pause"}}]})
    r = client.post("/chat", json={"message": "quieter and play"}).json()
    assert [a["name"] for a in r["actions"]] == ["set_volume", "media_control"]


def test_model_down_gives_spoken_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("local model not running; GROQ_API_KEY is not set")
    monkeypatch.setattr(llm, "chat", boom)
    r = client.post("/chat", json={"message": "hi"})
    assert r.status_code == 200 and "can't reach" in r.json()["reply"] and "GROQ_API_KEY" in r.json()["error"]


def test_remembered_fact_reaches_prompt(monkeypatch):
    memory.add_fact("favourite colour is teal")
    calls = script_llm(monkeypatch, {"reply": "ok", "actions": []})
    client.post("/chat", json={"message": "hi"})
    assert "favourite colour is teal" in calls[0][0]["content"]


def test_gesture_and_unknown(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", lambda s, t=25: (seen.append(s) or (True, "")))
    assert client.post("/gesture_action", json={"name": "swipe_right"}).json()["ok"]
    assert "^{TAB}" in seen[0]
    assert not client.post("/gesture_action", json={"name": "wave"}).json()["ok"]


def test_vision_error_is_spoken(monkeypatch):
    monkeypatch.setattr(llm, "describe_image", lambda *a: (_ for _ in ()).throw(RuntimeError("no vision")))
    r = client.post("/vision", json={"image": "data:image/jpeg;base64,AAAA", "question": "what is this"}).json()
    assert "can't look" in r["reply"]


def test_reset_memory():
    memory.add_message("user", "x"); memory.add_fact("keep")
    client.post("/reset_memory", json={})
    assert memory.get_history() == [] and memory.get_facts() == ["keep"]
    client.post("/reset_memory", json={"all": True})
    assert memory.get_facts() == []


def test_health_shape():
    h = client.get("/health").json()
    assert h["ok"] and "local" in h and "open_app" in h["actions"]
