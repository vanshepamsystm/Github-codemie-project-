from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    """Create a TestClient backed by a temporary SQLite DB.

    The application uses a module-level DATABASE_PATH, so we patch it and re-run
    initialize_database() for each test.
    """

    import main

    # Ensure each test gets its own isolated DB file
    db_path = tmp_path / "test_todos.db"
    monkeypatch.setattr(main, "DATABASE_PATH", db_path)

    # Re-initialize schema against patched DB
    main.initialize_database()

    # Reload not strictly required, but helps avoid stale module state if future
    # changes add more globals depending on DATABASE_PATH.
    importlib.reload(main)
    monkeypatch.setattr(main, "DATABASE_PATH", db_path)
    main.initialize_database()

    return TestClient(main.app)


def test_get_todos_returns_list(client: TestClient) -> None:
    resp = client.get("/api/todos")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_post_creates_todo_and_returns_fields(client: TestClient) -> None:
    resp = client.post("/api/todos", json={"title": "Buy milk"})
    assert resp.status_code == 201
    body = resp.json()
    assert set(body.keys()) == {"id", "title", "completed"}
    assert isinstance(body["id"], int)
    assert body["title"] == "Buy milk"
    assert body["completed"] is False


def test_patch_updates_completed(client: TestClient) -> None:
    created = client.post("/api/todos", json={"title": "Do thing"}).json()

    resp = client.patch(f"/api/todos/{created['id']}", json={"completed": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["completed"] is True


def test_delete_deletes_todo(client: TestClient) -> None:
    created = client.post("/api/todos", json={"title": "Temp"}).json()

    resp = client.delete(f"/api/todos/{created['id']}")
    assert resp.status_code == 204

    # Ensure it's gone
    resp2 = client.patch(f"/api/todos/{created['id']}", json={"completed": True})
    assert resp2.status_code == 404


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_non_existent_id_returns_404(client: TestClient, method: str) -> None:
    todo_id = 999999
    if method == "patch":
        resp = client.patch(f"/api/todos/{todo_id}", json={"completed": True})
    else:
        resp = client.delete(f"/api/todos/{todo_id}")

    assert resp.status_code == 404
