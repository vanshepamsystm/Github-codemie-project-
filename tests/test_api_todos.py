from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

import main

NOT_FOUND_ID = 999999


# --- Isolation -------------------------------------------------------------


def test_tests_use_temporary_database(db_path: Path):
    assert main.DATABASE_PATH == db_path
    assert db_path != main.BASE_DIR / "todos.db"
    assert db_path.exists()


def test_database_is_fresh_for_each_test(client: TestClient):
    assert client.get("/api/todos").json() == []


def test_get_connection_closes_connection(db_path: Path):
    with main.get_connection() as connection:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


# --- Create ----------------------------------------------------------------


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


def test_create_todo_trims_title(client: TestClient):
    resp = client.post("/api/todos", json={"title": "  Walk dog  "})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Walk dog"


def test_create_todo_rejects_overlong_title(client: TestClient):
    resp = client.post("/api/todos", json={"title": "x" * (main.MAX_TITLE_LENGTH + 1)})
    assert resp.status_code == 422


def test_create_todo_accepts_max_length_title(client: TestClient):
    resp = client.post("/api/todos", json={"title": "x" * main.MAX_TITLE_LENGTH})
    assert resp.status_code == 201


@pytest.mark.parametrize("title", ["", "   ", "\t\n"])
def test_create_todo_rejects_blank_title(client: TestClient, title: str):
    resp = client.post("/api/todos", json={"title": title})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Todo title cannot be empty"
    assert client.get("/api/todos").json() == []


@pytest.mark.parametrize(
    "payload",
    [{}, {"title": None}, {"title": ["a"]}, {"name": "wrong field"}],
    ids=["missing-body-field", "null-title", "list-title", "unknown-field-only"],
)
def test_create_todo_rejects_invalid_payload(client: TestClient, payload: dict):
    resp = client.post("/api/todos", json=payload)
    assert resp.status_code == 422


def test_create_todo_rejects_missing_body(client: TestClient):
    assert client.post("/api/todos").status_code == 422


# --- List ------------------------------------------------------------------


def test_list_todos_empty(client: TestClient):
    resp = client.get("/api/todos")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_todos_returns_newest_first(client: TestClient, create_todo):
    first = create_todo("first")
    second = create_todo("second")

    todos = client.get("/api/todos").json()

    assert [todo["id"] for todo in todos] == [second["id"], first["id"]]


# --- Update ----------------------------------------------------------------


def test_update_todo_completed(client: TestClient, create_todo):
    created = create_todo("Do laundry")

    resp = client.patch(f"/api/todos/{created['id']}", json={"completed": True})
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["id"] == created["id"]
    assert updated["title"] == "Do laundry"
    assert updated["completed"] is True


def test_update_todo_can_be_reverted_and_persists(client: TestClient, create_todo):
    created = create_todo()
    url = f"/api/todos/{created['id']}"

    client.patch(url, json={"completed": True})
    resp = client.patch(url, json={"completed": False})

    assert resp.json()["completed"] is False
    assert client.get("/api/todos").json()[0]["completed"] is False


def test_update_missing_todo_returns_404(client: TestClient):
    resp = client.patch(f"/api/todos/{NOT_FOUND_ID}", json={"completed": True})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Todo not found"


@pytest.mark.parametrize(
    "payload",
    [{}, {"completed": "not-a-bool"}, {"completed": None}, {"title": "x"}],
    ids=["empty", "non-bool", "null", "wrong-field"],
)
def test_update_todo_rejects_invalid_payload(
    client: TestClient, create_todo, payload: dict
):
    created = create_todo()
    resp = client.patch(f"/api/todos/{created['id']}", json=payload)
    assert resp.status_code == 422


def test_update_todo_rejects_non_integer_id(client: TestClient):
    resp = client.patch("/api/todos/abc", json={"completed": True})
    assert resp.status_code == 422


# --- Delete ----------------------------------------------------------------


def test_delete_todo(client: TestClient, create_todo):
    created = create_todo("Take out trash")

    del_resp = client.delete(f"/api/todos/{created['id']}")
    assert del_resp.status_code == 204
    assert del_resp.content == b""

    assert client.get("/api/todos").json() == []
    resp = client.patch(f"/api/todos/{created['id']}", json={"completed": True})
    assert resp.status_code == 404


def test_delete_only_removes_target_todo(client: TestClient, create_todo):
    keep = create_todo("keep")
    remove = create_todo("remove")

    client.delete(f"/api/todos/{remove['id']}")

    assert [todo["id"] for todo in client.get("/api/todos").json()] == [keep["id"]]


def test_delete_missing_todo_returns_404(client: TestClient):
    resp = client.delete(f"/api/todos/{NOT_FOUND_ID}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Todo not found"


def test_delete_todo_twice_returns_404_second_time(client: TestClient, create_todo):
    created = create_todo()
    url = f"/api/todos/{created['id']}"

    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 404


def test_delete_todo_rejects_non_integer_id(client: TestClient):
    assert client.delete("/api/todos/abc").status_code == 422


# --- Frontend entry point --------------------------------------------------


def test_home_serves_index_html(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
