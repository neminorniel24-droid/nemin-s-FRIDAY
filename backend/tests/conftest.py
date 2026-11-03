import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Every test gets its own empty memory, settings, reminders and activity log."""
    import activity
    import memory
    import reminders
    import settings
    monkeypatch.setattr(memory, "_FILE", tmp_path / "memory.json")
    monkeypatch.setattr(settings, "_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(reminders, "_FILE", tmp_path / "reminders.json")
    monkeypatch.setattr(activity, "_FILE", tmp_path / "activity.log")
    try:
        import main
        main.PENDING.update(actions=[], expires=0.0)
    except Exception:
        pass
    yield
