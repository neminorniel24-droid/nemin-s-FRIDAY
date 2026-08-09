import importlib


def test_currency_invalid_input():
    info_actions = importlib.import_module("backend.info_actions")

    result = info_actions.convert_currency("hello")

    assert "amount" in result.lower()
    assert "currency" in result.lower()


def test_currency_invalid_currency_format():
    info_actions = importlib.import_module("backend.info_actions")

    result = info_actions.convert_currency("100 dollars")

    assert "amount" in result.lower()


def test_wikipedia_empty_query():
    info_actions = importlib.import_module("backend.info_actions")

    result = info_actions.look_up("")

    assert result == "What would you like me to look up?"


def test_github_missing_username(monkeypatch):
    info_actions = importlib.import_module("backend.info_actions")

    monkeypatch.setattr(info_actions, "GITHUB_USERNAME", "")

    result = info_actions.check_github("")

    assert "github username" in result.lower()


def test_project_status_unknown_project():
    info_actions = importlib.import_module("backend.info_actions")

    result = info_actions.project_status("definitely-not-a-configured-project")

    assert "isn't configured" in result
