"""Shared pytest fixtures for the Todo API tests.

Every test runs against its own temporary SQLite file, so the real
``todos.db`` is never read or modified.
"""
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the app at a fresh temporary database with the schema created."""
    path = tmp_path / "test_todos.db"
    monkeypatch.setattr(main, "DATABASE_PATH", path)
    main.initialize_database()
    return path


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)


@pytest.fixture()
def create_todo(client: TestClient) -> Callable[[str], dict]:
    """Factory that creates a todo through the API and returns its JSON."""

    def _create(title: str = "Sample todo") -> dict:
        response = client.post("/api/todos", json={"title": title})
        assert response.status_code == 201
        return response.json()

    return _create
