import pytest
from unittest.mock import MagicMock
import core.db as db


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("core.db.DB_PATH", db_path)
    db.init_db()
    return db_path


@pytest.fixture
def mock_display():
    # used by test_state.py
    return MagicMock()
