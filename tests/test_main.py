import importlib


def test_health_endpoint():
    main = importlib.import_module("backend.main")

    result = main.health()

    assert result["ok"] is True
    assert "llm_configured" in result
    assert "conversation_history_length" in result


def test_reset_memory():
    main = importlib.import_module("backend.main")

    main.conversation_history.clear()
    main.conversation_history.append(
        {"role": "user", "content": "hello"}
    )

    result = main.reset_memory()

    assert result == {"ok": True}
    assert main.conversation_history == []


def test_chat_without_groq_key():
    main = importlib.import_module("backend.main")

    original_client = main.client

    try:
        main.client = None

        request = main.ChatRequest(message="hello")
        result = main.chat(request)

        assert result.reply
        assert "GROQ_API_KEY" in result.reply
    finally:
        main.client = original_client


def test_gesture_action_dispatches(monkeypatch):
    main = importlib.import_module("backend.main")

    def fake_execute(action_type, arg):
        assert action_type == "test_action"
        assert arg == "hello"
        return main.pc_control.ActionResult(True, "test succeeded")

    monkeypatch.setattr(main.pc_control, "execute", fake_execute)

    request = main.GestureActionRequest(
        type="test_action",
        arg="hello",
    )

    result = main.gesture_action(request)

    assert result["ok"] is True
    assert result["message"] == "test succeeded"


def test_gesture_action_rejects_unknown_action(monkeypatch):
    main = importlib.import_module("backend.main")

    def fake_execute(action_type, arg):
        return main.pc_control.ActionResult(
            False,
            f"unknown action '{action_type}'",
        )

    monkeypatch.setattr(main.pc_control, "execute", fake_execute)

    request = main.GestureActionRequest(
        type="not-a-real-action",
        arg="",
    )

    result = main.gesture_action(request)

    assert result["ok"] is False
    assert "unknown action" in result["message"]


def test_chat_request_requires_message():
    main = importlib.import_module("backend.main")

    try:
        main.ChatRequest()
        assert False, "ChatRequest should require message"
    except Exception:
        pass
