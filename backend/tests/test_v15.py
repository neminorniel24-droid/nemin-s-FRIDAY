"""Tests for the v15 features: modes, confirmations, reminders, files, security, home, plugins, log."""
import json
import socket
import threading
import time
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import actions
import activity
import briefing
import clock
import llm
import main
import personas
import reminders
import settings
from actions import Result, files, home, pc, security, system, winshell

client = TestClient(main.app)
IST = timezone(timedelta(hours=5, minutes=30))


def script_llm(monkeypatch, *replies):
    calls = []
    it = iter(replies)

    def fake(messages, json_mode=True):
        calls.append(messages)
        return json.dumps(next(it)), "test"
    monkeypatch.setattr(llm, "chat", fake)
    return calls


def no_llm(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the language model should not be used for this")
    monkeypatch.setattr(llm, "chat", boom)


# ------------------------------------------------------------------ modes
def test_switch_persona_without_llm(monkeypatch):
    no_llm(monkeypatch)
    r = client.post("/chat", json={"message": "switch to Jarvis"}).json()
    assert r["persona"]["key"] == "jarvis" and r["ui"]["persona"]["key"] == "jarvis"
    assert settings.get("persona") == "jarvis"
    assert client.post("/chat", json={"message": "friday mode"}).json()["persona"]["key"] == "friday"
    assert client.post("/chat", json={"message": "go back to nemiii"}).json()["persona"]["key"] == "nemiii"


def test_calling_her_by_name_switches_mode(monkeypatch):
    script_llm(monkeypatch, {"reply": "Right away.", "actions": []})
    r = client.post("/chat", json={"message": "what time is it", "persona": "edith"}).json()
    assert r["persona"]["key"] == "edith"


def test_each_persona_changes_the_prompt(monkeypatch):
    seen = {}
    for key in ("nemiii", "jarvis", "friday", "edith"):
        personas.set_current(key)
        calls = script_llm(monkeypatch, {"reply": "ok", "actions": []})
        client.post("/chat", json={"message": "hello there"})
        seen[key] = calls[0][0]["content"]
    assert "digital butler" in seen["jarvis"] and "tactical" in seen["friday"] and "literal" in seen["edith"]
    assert len({v.split("HOW YOU ACT")[0] for v in seen.values()}) == 4


def test_theme_without_llm(monkeypatch):
    no_llm(monkeypatch)
    assert client.post("/chat", json={"message": "red alert"}).json()["ui"]["theme"] == "red"
    assert client.post("/chat", json={"message": "change the theme to gold"}).json()["ui"]["theme"] == "gold"
    assert client.post("/chat", json={"message": "switch to ice theme"}).json()["ui"]["theme"] == "ice"
    assert settings.get("theme") == "ice"


# ---------------------------------------------------------- confirmations
def test_risky_action_asks_first_then_yes_runs_it(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", lambda s, t=25: (seen.append(s) or (True, "CLOSED")))
    script_llm(monkeypatch, {"reply": "Closing it.", "actions": [{"name": "close_app", "args": {"name": "chrome"}}]})
    r = client.post("/chat", json={"message": "close chrome"}).json()
    assert r["confirm"] and "close chrome" in r["reply"].lower() and not seen   # nothing ran yet
    no_llm(monkeypatch)
    r2 = client.post("/chat", json={"message": "yes"}).json()
    assert seen and r2["actions"][0]["ok"] and not r2["confirm"]


def test_no_cancels_a_risky_action(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", lambda s, t=25: (seen.append(s) or (True, "OK")))
    script_llm(monkeypatch, {"reply": "Locking.", "actions": [{"name": "lock_pc", "args": {}}]})
    assert client.post("/chat", json={"message": "lock my pc"}).json()["confirm"]
    no_llm(monkeypatch)
    assert client.post("/chat", json={"message": "no"}).json()["reply"] == "Cancelled."
    assert not seen


def test_confirmation_expires(monkeypatch):
    monkeypatch.setattr(pc, "run_ps", lambda s, t=25: (True, "OK"))
    script_llm(monkeypatch, {"reply": "x", "actions": [{"name": "lock_pc", "args": {}}]}, {"reply": "Sure.", "actions": []})
    client.post("/chat", json={"message": "lock"})
    main.PENDING["expires"] = time.time() - 1
    r = client.post("/chat", json={"message": "yes"}).json()  # goes to the model, runs nothing
    assert r["reply"] == "Sure." and not r["actions"]


def test_safe_actions_before_a_risky_one_still_run(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "run_ps", lambda s, t=25: (seen.append(s) or (True, "OK")))
    script_llm(monkeypatch, {"reply": "ok", "actions": [
        {"name": "set_volume", "args": {"change": "mute"}}, {"name": "lock_pc", "args": {}}]})
    r = client.post("/chat", json={"message": "mute and lock"}).json()
    assert r["confirm"] and [a["name"] for a in r["actions"]] == ["set_volume"] and len(seen) == 1


def test_cancelling_a_shutdown_needs_no_confirmation():
    assert actions.is_risky("power_action", {"command": "shutdown"})
    assert actions.is_risky("power_action", {"command": "restart"})
    assert not actions.is_risky("power_action", {"command": "cancel"})
    assert not actions.is_risky("open_app", {"name": "chrome"})


def test_power_commands(monkeypatch):
    seen = []
    monkeypatch.setattr(system, "run_ps", lambda s, t=25: (seen.append(s) or (True, "")))
    assert actions.run("power_action", {"command": "shutdown"}).ok and "/s /t 30" in seen[-1]
    assert actions.run("power_action", {"command": "cancel"}).ok and "/a" in seen[-1]
    assert not actions.run("power_action", {"command": "format"}).ok


# -------------------------------------------------------------- reminders
NOW = datetime(2026, 10, 29, 21, 0, tzinfo=IST)


def test_parse_when():
    assert reminders.parse_when({"minutes": 20}, NOW) == NOW + timedelta(minutes=20)
    assert reminders.parse_when({"seconds": 90}, NOW) == NOW + timedelta(seconds=90)
    assert reminders.parse_when({"at": "22:30"}, NOW).hour == 22
    assert reminders.parse_when({"at": "7:00"}, NOW).day == 30          # already past today, so tomorrow
    assert reminders.parse_when({"at": "6:30 pm"}, NOW).day == 30
    assert reminders.parse_when({"at": "tomorrow 9:15 am"}, NOW) == datetime(2026, 10, 30, 9, 15, tzinfo=IST)
    assert reminders.parse_when({"at": "2026-11-02 09:00"}, NOW).month == 11
    assert reminders.parse_when({"at": "whenever"}, NOW) is None
    assert reminders.parse_when({"at": "25:00"}, NOW) is None
    assert reminders.parse_when({}, NOW) is None


def test_reminder_lifecycle_and_due_endpoint(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: datetime.now(IST))
    r = actions.run("set_reminder", {"text": "call mom", "seconds": 1})
    assert r.ok and "call mom" in r.message
    assert client.get("/reminders").json()["items"][0]["text"] == "call mom"
    assert client.get("/reminders/due").json()["due"] == []        # not yet
    time.sleep(1.2)
    due = client.get("/reminders/due").json()["due"]
    assert [d["text"] for d in due] == ["call mom"]
    assert client.get("/reminders/due").json()["due"] == []        # said only once
    assert client.get("/reminders").json()["items"] == []


def test_timer_and_cancel(monkeypatch):
    assert actions.run("set_timer", {"minutes": 10, "label": "tea"}).ok
    assert "tea is done" in actions.run("list_reminders", {}).message
    assert "Cancelled 1" in actions.run("cancel_reminder", {"keyword": "tea"}).message
    assert actions.run("list_reminders", {}).message == "You have no reminders."


def test_daily_reminder_rearms():
    due = clock.now() - timedelta(seconds=5)
    reminders.add("water", due, "daily")
    assert len(reminders.take_due()) == 1
    up = reminders.upcoming()
    assert len(up) == 1 and datetime.fromisoformat(up[0]["due"]) > clock.now()


def test_background_sweep_notifies_only_when_page_did_not(monkeypatch):
    reminders.add("late one", clock.now() - timedelta(seconds=60))
    reminders.add("fresh one", clock.now() - timedelta(seconds=2))
    got = []
    assert reminders.sweep(lambda t, m: got.append(m)) == 1       # only the one overdue past the grace time
    assert got == ["late one"]


def test_reminder_failure_is_honest():
    assert not actions.run("set_reminder", {"text": "x", "at": "banana"}).ok


# ---------------------------------------------------------------- briefing
def test_briefing_works_with_everything_missing(monkeypatch):
    import geo, news
    monkeypatch.setattr(geo, "get_weather", lambda *a: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(news, "headlines", lambda *a: (_ for _ in ()).throw(RuntimeError("offline")))
    morning = datetime(2026, 10, 29, 8, 0, tzinfo=IST)
    monkeypatch.setattr(clock, "now", lambda: morning)
    reminders.add("standup", morning + timedelta(minutes=1))
    text = actions.run("daily_briefing", {}).message
    assert "Good morning" in text and "standup" in text and "weather" not in text.lower()


def test_briefing_greeting_follows_the_time_of_day(monkeypatch):
    import geo, news
    monkeypatch.setattr(geo, "get_weather", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(news, "headlines", lambda *a: [])
    monkeypatch.setattr(clock, "now", lambda: datetime(2026, 10, 29, 19, 0, tzinfo=IST))
    assert "Good evening" in actions.run("daily_briefing", {}).message
    personas.set_current("edith")
    assert actions.run("daily_briefing", {}).message.startswith("Briefing.")


def test_good_morning_uses_briefing_without_llm(monkeypatch):
    no_llm(monkeypatch)
    monkeypatch.setattr(briefing, "collect", lambda: {
        "date": "Thursday, 29 October", "time": "7:00 AM", "place": "Chennai", "weather": "clear, 28 degrees",
        "unread": 2, "mail": ["Offer letter"], "headlines": ["Moon base approved"], "github": None,
        "reminders": [], "skipped": []})
    r = client.post("/chat", json={"message": "good morning"}).json()
    assert "Chennai" in r["reply"] and "2 unread" in r["reply"] and "Moon base approved" in r["reply"]


# ------------------------------------------------------------- activity log
def test_every_action_is_logged_and_secrets_hidden(monkeypatch):
    monkeypatch.setattr(pc, "run_ps", lambda s, t=25: (True, "OK"))
    actions.run("open_app", {"name": "chrome"}, "chat")
    actions.run("open_app", {"name": "x", "api_token": "sekret"}, "chat")
    items = activity.recent()
    assert items[0]["action"] == "open_app" and items[0]["args"]["api_token"] == "***"
    assert client.get("/activity").json()["items"][1]["ok"] is True
    assert "open_app" in actions.run("activity_summary", {}).message


# ------------------------------------------------------------------- files
@pytest.fixture
def docs(tmp_path, monkeypatch):
    root = tmp_path / "Documents"
    (root / "school").mkdir(parents=True)
    (root / "notes.txt").write_text("buy milk and call the bank", encoding="utf-8")
    (root / "school" / "Quantum Report Final.txt").write_text("qubits are fun", encoding="utf-8")
    (root / ".env").write_text("KEY=1", encoding="utf-8")
    (root / "my_token.txt").write_text("secret", encoding="utf-8")
    (root / "setup.exe").write_bytes(b"MZ")
    with zipfile.ZipFile(root / "essay.docx", "w") as z:
        z.writestr("word/document.xml",
                   '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                   "<w:p><w:r><w:t>Hello from Word</w:t></w:r></w:p></w:body></w:document>")
    monkeypatch.setattr(files.config, "FILES_ROOTS", [str(root)])
    return root


def test_find_and_read_files(docs):
    assert "Quantum Report Final.txt" in actions.run("find_file", {"query": "quantum report"}).message
    assert "buy milk" in actions.run("read_file", {"query": "notes"}).message
    assert "Hello from Word" in actions.run("read_file", {"query": "essay"}).message


def test_secrets_and_outside_paths_are_refused(docs, tmp_path):
    assert "no files" in actions.run("find_file", {"query": "token"}).message.lower()
    assert "no files" in actions.run("find_file", {"query": "env"}).message.lower()
    outside = tmp_path / "outside.txt"
    outside.write_text("nope")
    assert not actions.run("read_file", {"path": str(outside)}).ok
    assert not actions.run("read_file", {"path": str(docs / "my_token.txt")}).ok
    assert not actions.run("read_file", {"path": str(docs / ".." / "outside.txt")}).ok


def test_programs_are_never_opened(docs, monkeypatch):
    monkeypatch.setattr(files, "run_ps", lambda s, t=25: (True, ""))
    r = actions.run("open_file", {"query": "setup"})
    assert not r.ok and "programs" in r.message


def test_open_file_uses_start_process(docs, monkeypatch):
    seen = []
    monkeypatch.setattr(files, "run_ps", lambda s, t=25: (seen.append(s) or (True, "")))
    monkeypatch.setattr(files.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "C:\\Users\\n\\Documents\\notes.txt"})())
    assert actions.run("open_file", {"query": "notes"}).ok and "Start-Process -LiteralPath" in seen[0]


def test_clipboard(monkeypatch):
    monkeypatch.setattr(files, "run_ps", lambda s, t=25: (True, "copied text here"))
    assert "copied text here" in actions.run("read_clipboard", {}).message
    seen = []
    monkeypatch.setattr(files, "run_ps", lambda s, t=25: (seen.append(s) or (True, "")))
    assert actions.run("copy_to_clipboard", {"text": "it's fine"}).ok and "it''s fine" in seen[0]


# ------------------------------------------------------------------ system
def test_system_status(monkeypatch):
    payload = {"cpu": 12, "mem_total_gb": 16.0, "mem_free_gb": 6.0, "disk_free_gb": 200, "disk_total_gb": 500,
               "battery": 80, "charging": True, "uptime_h": 3.5}
    monkeypatch.setattr(system, "run_ps", lambda s, t=25: (True, json.dumps(payload)))
    m = actions.run("system_status", {}).message
    assert "CPU at 12" in m and "62 percent" in m and "charging" in m


# ---------------------------------------------------------------- security
def test_scan_refuses_the_internet(monkeypatch):
    monkeypatch.setattr(security.socket, "gethostbyname", lambda h: "8.8.8.8")
    r = actions.run("scan_ports", {"target": "8.8.8.8"})
    assert not r.ok and "never the internet" in r.message


def test_scan_finds_a_local_open_port(monkeypatch):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    monkeypatch.setattr(security, "PORTS", {port: "test service", 1: "nothing"})
    try:
        r = actions.run("scan_ports", {"target": "localhost"})
    finally:
        srv.close()
    assert r.ok and f"{port} test service" in r.message


def test_private_lan_address_is_allowed(monkeypatch):
    monkeypatch.setattr(security.socket, "gethostbyname", lambda h: h)
    assert security.resolve_private_target("192.168.1.20")[0] == "192.168.1.20"
    assert security.resolve_private_target("10.0.0.5")[0] == "10.0.0.5"
    assert security.resolve_private_target("1.1.1.1")[0] is None


def test_url_heuristics():
    _, w = security.url_findings("http://paypal-login.verify-account.xyz/signin")
    joined = " ".join(w)
    assert "not encrypted" in joined and "paypal" in joined and ".xyz" in joined
    assert security.url_findings("https://www.github.com/x")[1] == []
    assert any("@" in x for x in security.url_findings("https://google.com@evil.example/")[1])
    assert any("raw IP" in x for x in security.url_findings("http://203.0.113.9/login")[1])
    assert any("shortener" in x for x in security.url_findings("https://bit.ly/abc")[1])


def test_check_url_does_not_fetch_private_targets(monkeypatch):
    monkeypatch.setattr(security.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("192.168.0.1", 0))])
    boom = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not fetch a private address"))
    monkeypatch.setattr(security.requests, "head", boom)
    assert "private address" in actions.run("check_url", {"url": "http://router.local"}).message


def test_check_url_follows_redirect_to_other_site(monkeypatch):
    monkeypatch.setattr(security.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    monkeypatch.setattr(security, "_cert_note", lambda h: None)

    def head(url, **k):
        if "start.example" in url:
            return type("R", (), {"status_code": 302, "headers": {"Location": "https://evil.test/x"}})()
        return type("R", (), {"status_code": 200, "headers": {}})()
    monkeypatch.setattr(security.requests, "head", head)
    m = actions.run("check_url", {"url": "https://start.example/a"}).message
    assert "redirects to a different site, evil.test" in m


ARP = """Interface: 192.168.1.4 --- 0x7
  Internet Address      Physical Address      Type
  192.168.1.1           aa-bb-cc-dd-ee-01     dynamic
  192.168.1.22          aa-bb-cc-dd-ee-22     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
  224.0.0.22            01-00-5e-00-00-16     static
"""


def test_lan_devices(monkeypatch):
    assert [d[0] for d in security.parse_arp(ARP)] == ["192.168.1.1", "192.168.1.22"]
    monkeypatch.setattr(security, "run_ps", lambda s, t=25: (True, ARP))
    assert "2 devices" in actions.run("lan_devices", {}).message


def test_cve_news(monkeypatch):
    feed = {"vulnerabilities": [
        {"cveID": "CVE-2026-1", "vendorProject": "Microsoft", "product": "Windows", "vulnerabilityName": "Old bug", "dateAdded": "2026-01-01"},
        {"cveID": "CVE-2026-9", "vendorProject": "Cisco", "product": "IOS", "vulnerabilityName": "New bug", "dateAdded": "2026-10-20"}]}
    monkeypatch.setattr(security.requests, "get", lambda *a, **k: type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: feed})())
    security._CVE_CACHE.update(at=0.0, items=[])
    m = actions.run("cve_news", {}).message
    assert m.index("CVE-2026-9") < m.index("CVE-2026-1")
    assert "CVE-2026-1" not in actions.run("cve_news", {"vendor": "cisco"}).message


def test_honeypot_status(monkeypatch):
    import config
    monkeypatch.setattr(config, "HONEYPOT_CONTAINER", "juice")

    def fake_run(cmd, **k):
        if cmd[1] == "ps":
            return type("R", (), {"stdout": "honeypot-juiceshop-1|Up 3 hours\nother|Exited (0)", "stderr": ""})()
        return type("R", (), {"stdout": 'GET /rest/products 200\nPOST /rest/user/login 401\nstarted', "stderr": ""})()
    monkeypatch.setattr(security.subprocess, "run", fake_run)
    m = actions.run("honeypot_status", {}).message
    assert "Up 3 hours" in m and "2 web requests" in m and "POST /rest/user/login" in m


# ---------------------------------------------------------------- smart home
def test_home_assistant(monkeypatch):
    import config
    monkeypatch.setattr(config, "HOME_ASSISTANT_URL", "http://ha.local:8123")
    monkeypatch.setattr(config, "HOME_ASSISTANT_TOKEN", "t")
    states = [{"entity_id": "light.bedroom", "state": "off", "attributes": {"friendly_name": "Bedroom Light"}},
              {"entity_id": "lock.front", "state": "locked", "attributes": {"friendly_name": "Front Door"}}]
    posted = []
    monkeypatch.setattr(home.requests, "get", lambda *a, **k: type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: states})())
    monkeypatch.setattr(home.requests, "post", lambda url, **k: (posted.append((url, k["json"])) or type("R", (), {"ok": True, "status_code": 200})()))
    assert "Bedroom Light is off" in actions.run("home_devices", {}).message and "Front Door" not in actions.run("home_devices", {}).message
    assert actions.run("home_control", {"name": "bedroom light", "command": "on"}).ok
    assert posted[0] == ("http://ha.local:8123/api/services/light/turn_on", {"entity_id": "light.bedroom"})
    assert not actions.run("home_control", {"name": "front door", "command": "off"}).ok   # locks are never controlled


def test_home_assistant_not_configured():
    assert "isn't set up" in actions.run("home_control", {"name": "x", "command": "on"}).message


# ----------------------------------------------------------------- plugins
def test_plugin_loaded_and_logged():
    assert "dice" in actions.PLUGINS and "roll_dice" in actions.REGISTRY
    r = actions.run("roll_dice", {"sides": 6, "count": 3})
    assert r.ok and "total" in r.message and activity.recent()[0]["action"] == "roll_dice"


def test_bad_plugin_does_not_stop_the_rest(tmp_path, monkeypatch):
    plug = actions.Path(actions.__file__).resolve().parent.parent / "plugins" / "zz_broken.py"
    plug.write_text("raise RuntimeError('broken on purpose')")
    try:
        loaded = actions.load_plugins()
    finally:
        plug.unlink()
    assert "dice" in loaded and "zz_broken" not in loaded


# ------------------------------------------------------------------ misc
def test_timezone_comes_from_the_browser():
    client.get("/health", params={"tz": "Asia/Kolkata"})
    assert settings.get("tz") == "Asia/Kolkata" and clock.now().utcoffset() == timedelta(hours=5, minutes=30)
    client.get("/health", params={"tz": "Not/AZone"})
    assert settings.get("tz") == "Asia/Kolkata"


def test_health_lists_new_things():
    h = client.get("/health").json()
    assert h["version"] == "17" and h["persona"]["key"] == "nemiii" and len(h["personas"]) == 4
    for name in ["set_reminder", "daily_briefing", "scan_ports", "check_url", "read_file", "power_action", "home_control"]:
        assert name in h["actions"]
    assert "jarvis" in h["wake_names"] and "friday" in h["wake_names"] and "edith" in h["wake_names"]


def test_mode_and_settings_endpoints():
    assert client.post("/mode", json={"key": "edith"}).json()["key"] == "edith"
    assert client.get("/mode").json()["key"] == "edith"
    assert client.post("/settings", json={"theme": "red alert"}).json()["theme"] == "red"
    assert "error" in client.post("/mode", json={"key": "skynet"}).json()


def test_facts_endpoints():
    import memory
    memory.add_fact("likes tea")
    assert client.get("/facts").json()["facts"] == ["likes tea"]
    assert client.post("/facts/forget", json={"keyword": "tea"}).json()["removed"] == 1
