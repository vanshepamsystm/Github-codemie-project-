from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the app at a throwaway SQLite file so tests never touch todos.db.

    main.py reads the module-level DATABASE_PATH on every connection, so
    patching it is enough; the schema is then created in the temp file.
    """
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "test_todos.db")
    main.initialize_database()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)
