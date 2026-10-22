import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    """Every test gets its own empty memory file."""
    import memory
    monkeypatch.setattr(memory, "_FILE", tmp_path / "memory.json")
    yield
