import pytest
from fastapi.testclient import TestClient


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
