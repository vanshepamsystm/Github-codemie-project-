import pytest
from fastapi.testclient import TestClient

import main


def create_todo(client: TestClient, title: str) -> dict:
    response = client.post("/api/todos", json={"title": title})
    assert response.status_code == 201
    return response.json()


def test_create_and_list_todos(client: TestClient):
    created = create_todo(client, "Buy milk")
    assert created["id"]
    assert created["title"] == "Buy milk"
    assert created["completed"] is False

    list_resp = client.get("/api/todos")
    assert list_resp.status_code == 200
    assert list_resp.json() == [created]


def test_list_todos_is_empty_initially(client: TestClient):
    resp = client.get("/api/todos")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_todos_returns_newest_first(client: TestClient):
    first = create_todo(client, "first")
    second = create_todo(client, "second")

    ids = [todo["id"] for todo in client.get("/api/todos").json()]
    assert ids == [second["id"], first["id"]]


def test_create_todo_trims_title(client: TestClient):
    created = create_todo(client, "  Walk the dog  ")
    assert created["title"] == "Walk the dog"
    assert client.get("/api/todos").json()[0]["title"] == "Walk the dog"


@pytest.mark.parametrize("title", ["", "   ", "\t\n"])
def test_create_todo_rejects_blank_title(client: TestClient, title: str):
    resp = client.post("/api/todos", json={"title": title})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Todo title cannot be empty"
    assert client.get("/api/todos").json() == []


@pytest.mark.parametrize(
    "payload",
    [{}, {"title": None}, {"title": 123}, {"name": "wrong field"}],
)
def test_create_todo_rejects_invalid_payload(client: TestClient, payload: dict):
    resp = client.post("/api/todos", json=payload)
    assert resp.status_code == 422


def test_update_todo_completed(client: TestClient):
    created = create_todo(client, "Do laundry")

    resp = client.patch(f"/api/todos/{created['id']}", json={"completed": True})
    assert resp.status_code == 200
    assert resp.json() == {**created, "completed": True}
    assert client.get("/api/todos").json()[0]["completed"] is True


def test_update_todo_can_mark_incomplete_again(client: TestClient):
    created = create_todo(client, "Toggle me")
    client.patch(f"/api/todos/{created['id']}", json={"completed": True})

    resp = client.patch(f"/api/todos/{created['id']}", json={"completed": False})
    assert resp.status_code == 200
    assert resp.json()["completed"] is False


def test_update_todo_rejects_invalid_payload(client: TestClient):
    created = create_todo(client, "Bad patch")
    resp = client.patch(f"/api/todos/{created['id']}", json={})
    assert resp.status_code == 422


def test_update_missing_todo_returns_404(client: TestClient):
    resp = client.patch("/api/todos/999999", json={"completed": True})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Todo not found"


def test_delete_todo(client: TestClient):
    created = create_todo(client, "Take out trash")

    del_resp = client.delete(f"/api/todos/{created['id']}")
    assert del_resp.status_code == 204
    assert del_resp.content == b""
    assert client.get("/api/todos").json() == []


def test_delete_only_removes_target_todo(client: TestClient):
    keep = create_todo(client, "keep")
    remove = create_todo(client, "remove")

    assert client.delete(f"/api/todos/{remove['id']}").status_code == 204
    assert client.get("/api/todos").json() == [keep]


def test_delete_missing_todo_returns_404(client: TestClient):
    resp = client.delete("/api/todos/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Todo not found"


def test_delete_twice_returns_404_second_time(client: TestClient):
    created = create_todo(client, "once")
    assert client.delete(f"/api/todos/{created['id']}").status_code == 204
    assert client.delete(f"/api/todos/{created['id']}").status_code == 404


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_non_integer_todo_id_is_rejected(client: TestClient, method: str):
    kwargs = {"json": {"completed": True}} if method == "patch" else {}
    resp = getattr(client, method)("/api/todos/not-a-number", **kwargs)
    assert resp.status_code == 422


def test_todo_responses_match_response_model_shape(client: TestClient):
    expected_keys = {"id", "title", "completed"}
    created = create_todo(client, "shape")
    assert set(created) == expected_keys

    assert set(client.get("/api/todos").json()[0]) == expected_keys
    patched = client.patch(f"/api/todos/{created['id']}", json={"completed": True})
    assert set(patched.json()) == expected_keys
    assert isinstance(created["id"], int)
    assert isinstance(patched.json()["completed"], bool)


def test_openapi_documents_todo_response_model(client: TestClient):
    schema = client.get("/openapi.json").json()
    todo_read = schema["components"]["schemas"]["TodoRead"]
    assert set(todo_read["properties"]) == {"id", "title", "completed"}
    assert set(todo_read["required"]) == {"id", "title", "completed"}


def test_create_todo_accepts_title_at_max_length(client: TestClient):
    title = "a" * main.TITLE_MAX_LENGTH
    assert create_todo(client, title)["title"] == title


def test_create_todo_rejects_title_over_max_length(client: TestClient):
    resp = client.post("/api/todos", json={"title": "a" * (main.TITLE_MAX_LENGTH + 1)})
    assert resp.status_code == 422
    assert client.get("/api/todos").json() == []


def test_create_todo_strips_before_checking_max_length(client: TestClient):
    padded = "  " + "a" * main.TITLE_MAX_LENGTH + "  "
    assert create_todo(client, padded)["title"] == "a" * main.TITLE_MAX_LENGTH


def test_connection_sets_busy_timeout():
    with main.get_connection() as connection:
        timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout == main.BUSY_TIMEOUT_MS


def test_database_uses_wal_journal_mode():
    with main.get_connection() as connection:
        mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
