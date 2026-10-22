import actions
from actions import pc


def fake_ps(store, ok=True, out="OK"):
    def run(script, timeout=25):
        store.append(script)
        return ok, out
    return run


def test_registry_has_core_actions():
    for name in ["open_app", "close_app", "play_youtube", "tell_news", "weather", "remember", "type_text", "set_volume"]:
        assert name in actions.REGISTRY
    assert actions.kind_of("tell_news") == "info"
    assert actions.kind_of("open_app") == "pc"


def test_unknown_action_is_refused():
    assert not actions.run("format_disk", {"drive": "c"}).ok


def test_open_known_app(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", fake_ps(seen))
    assert actions.run("open_app", {"name": "Chrome"}).ok
    assert "Start-Process chrome" in seen[0]


def test_open_steam_game(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", fake_ps(seen))
    assert actions.run("open_app", {"name": "PUBG"}).ok
    assert "steam://rungameid/578080" in seen[0]


def test_open_any_installed_app_uses_start_menu_search(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", fake_ps(seen, out="OK:Some Game"))
    r = actions.run("open_app", {"name": "Some Game"})
    assert r.ok and "Get-StartApps" in seen[0]


def test_app_not_found_is_reported(monkeypatch):
    monkeypatch.setattr(pc, "run_ps", fake_ps([], out="NOTFOUND"))
    r = actions.run("open_app", {"name": "Nonexistent"})
    assert not r.ok and "couldn't find" in r.message


def test_app_name_cannot_inject_commands(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", fake_ps(seen, out="NOTFOUND"))
    actions.run("open_app", {"name": "x'; Remove-Item C:\\ -Recurse; '"})
    name_line = seen[0].split("\n")[0]          # the line that holds the app name
    assert ";" not in name_line and "\\" not in name_line


def test_close_refuses_system_processes(monkeypatch):
    monkeypatch.setattr(pc, "run_ps", fake_ps([]))
    assert not actions.run("close_app", {"name": "explorer"}).ok
    assert not actions.run("close_app", {"name": "svchost"}).ok


def test_open_url_rejects_unsafe_schemes(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", fake_ps(seen))
    assert not actions.run("open_url", {"url": "javascript:alert(1)"}).ok
    assert not actions.run("open_url", {"url": "file:///C:/Windows/System32"}).ok
    assert actions.run("open_url", {"url": "example.com"}).ok
    assert "https://example.com" in seen[-1]


def test_volume_level_sends_right_number_of_steps(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", fake_ps(seen))
    assert actions.run("set_volume", {"level": 40}).ok
    assert "1..20" in seen[0] and "[char]175" in seen[0]
    assert not actions.run("set_volume", {"change": "sideways"}).ok


def test_type_text_escapes_quotes(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", fake_ps(seen))
    assert actions.run("type_text", {"text": "it's fine"}).ok
    assert "'it''s fine'" in seen[0]


def test_whatsapp_builds_link(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", fake_ps(seen))
    r = actions.run("whatsapp_message", {"text": "hello there", "number": "+91 98765 43210"})
    assert r.ok and "wa.me/919876543210?text=hello+there" in seen[0]


def test_open_project_unknown(monkeypatch):
    monkeypatch.setattr(pc.config, "project_paths", lambda: {})
    assert not actions.run("open_project", {"name": "nothing"}).ok


def test_calculate_is_safe():
    assert actions.run("calculate", {"expression": "12.5 * (3 + 4)"}).message.endswith("87.5")
    assert not actions.run("calculate", {"expression": "__import__('os').system('ls')"}).ok
    assert not actions.run("calculate", {"expression": "9**9999"}).ok


def test_remember_and_forget():
    import memory
    assert actions.run("remember", {"fact": "exam is on Friday"}).ok
    assert "exam is on Friday" in memory.get_facts()
    assert "1 saved item" in actions.run("forget", {"keyword": "exam"}).message
    assert memory.get_facts() == []
