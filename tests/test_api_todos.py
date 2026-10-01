import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Run each test with an isolated SQLite DB file.

    The app uses a module-level DATABASE_PATH; patch it for tests and
    initialize schema against the temp DB.
    """
    db_path = tmp_path / "test_todos.db"
    monkeypatch.setattr(main, "DATABASE_PATH", db_path)
    main.initialize_database()
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)


def test_create_and_list_todos(client: TestClient):
    create_resp = client.post("/api/todos", json={"title": "Buy milk"})
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["id"]
    assert created["title"] == "Buy milk"
    assert created["completed"] is False

    list_resp = client.get("/api/todos")
    assert list_resp.status_code == 200
    todos = list_resp.json()
    assert isinstance(todos, list)
    assert len(todos) == 1
    assert todos[0]["id"] == created["id"]


def test_create_todo_rejects_empty_title(client: TestClient):
    resp = client.post("/api/todos", json={"title": "   "})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Todo title cannot be empty"


def test_update_todo_completed(client: TestClient):
    created = client.post("/api/todos", json={"title": "Do laundry"}).json()

    resp = client.patch(f"/api/todos/{created['id']}", json={"completed": True})
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["id"] == created["id"]
    assert updated["completed"] is True


def test_update_missing_todo_returns_404(client: TestClient):
    resp = client.patch("/api/todos/999999", json={"completed": True})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Todo not found"


def test_delete_todo(client: TestClient):
    created = client.post("/api/todos", json={"title": "Take out trash"}).json()

    del_resp = client.delete(f"/api/todos/{created['id']}")
    assert del_resp.status_code == 204

    # Confirm it's gone
    resp = client.patch(f"/api/todos/{created['id']}", json={"completed": True})
    assert resp.status_code == 404


def test_delete_missing_todo_returns_404(client: TestClient):
    resp = client.delete("/api/todos/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Todo not found"


def test_health_returns_ok(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_returns_ready_when_database_reachable(client: TestClient):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


def test_ready_returns_503_when_database_unreachable(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # A directory cannot be opened as a SQLite database file.
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path)
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json() == {"status": "unavailable"}


def test_startup_initializes_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "fresh.db")
    with TestClient(main.app) as started_client:
        assert started_client.get("/api/todos").json() == []


def test_connection_is_closed_after_use():
    with main.get_connection() as connection:
        connection.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
