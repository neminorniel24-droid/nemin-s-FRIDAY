import importlib


def test_set_volume_rejects_invalid_direction():
    pc = importlib.import_module("backend.pc_control")

    result = pc.set_volume("sideways")

    assert result.ok is False
    assert "up, down, or mute" in result.message


def test_search_web_rejects_empty_query():
    pc = importlib.import_module("backend.pc_control")

    result = pc.search_web("")

    assert result.ok is False
    assert "search query" in result.message.lower()


def test_open_and_type_rejects_missing_separator():
    pc = importlib.import_module("backend.pc_control")

    result = pc.open_and_type("notepad hello")

    assert result.ok is False
    assert "app_name::text" in result.message


def test_open_folder_rejects_unknown_folder():
    pc = importlib.import_module("backend.pc_control")

    result = pc.open_folder("definitely-not-a-folder")

    assert result.ok is False
    assert "folder whitelist" in result.message


def test_play_youtube_rejects_empty_query():
    pc = importlib.import_module("backend.pc_control")

    result = pc.play_youtube("")

    assert result.ok is False
    assert "song/video" in result.message


def test_media_control_rejects_unknown_action():
    pc = importlib.import_module("backend.pc_control")

    result = pc.media_control("definitely-not-valid")

    assert result.ok is False


def test_close_app_unknown_process_does_not_execute_without_mocking():
    pc = importlib.import_module("backend.pc_control")

    # An unknown name should fall through to the process lookup.
    # Replace PowerShell execution so CI never touches a real Windows host.
    original = pc._run_powershell

    try:
        pc._run_powershell = lambda command, timeout=pc.TIMEOUT_SECONDS: pc.ActionResult(
            False, "no matching process found"
        )

        result = pc.close_app("definitely-not-a-real-app")

        assert result.ok is False
        assert "no running process" in result.message.lower()
    finally:
        pc._run_powershell = original
