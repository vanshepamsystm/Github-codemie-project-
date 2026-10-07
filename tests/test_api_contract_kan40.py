"""KAN-40: minimal API contract tests for the Todo CRUD endpoints.

Each test asserts the public contract only: status code, JSON shape,
field names and field types.
"""
import pytest
from fastapi.testclient import TestClient

import main

MISSING_ID = 999999
TODO_FIELDS = {"id": int, "title": str, "completed": bool}


def assert_todo_shape(body: dict) -> None:
    assert set(body) == set(TODO_FIELDS)
    for field, expected_type in TODO_FIELDS.items():
        assert type(body[field]) is expected_type, field


def assert_validation_error(response, field: str) -> None:
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert isinstance(errors, list) and errors
    assert errors[0]["loc"][-1] == field


def test_create_returns_201_with_todo_shape(client: TestClient):
    response = client.post("/api/todos", json={"title": "Buy milk"})

    assert response.status_code == 201
    body = response.json()
    assert_todo_shape(body)
    assert body["title"] == "Buy milk"
    assert body["completed"] is False


def test_list_returns_200_with_array_of_todos(client: TestClient, create_todo):
    create_todo("first")
    create_todo("second")

    response = client.get("/api/todos")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list) and len(body) == 2
    for todo in body:
        assert_todo_shape(todo)


def test_list_is_empty_array_when_no_todos(client: TestClient):
    response = client.get("/api/todos")

    assert response.status_code == 200
    assert response.json() == []


def test_created_todo_is_retrievable_from_list(client: TestClient, create_todo):
    created = create_todo("Find me")

    assert client.get("/api/todos").json() == [created]


@pytest.mark.parametrize("completed", [True, False])
def test_update_returns_200_with_updated_todo(client: TestClient, create_todo, completed: bool):
    created = create_todo("Do laundry")

    response = client.patch(f"/api/todos/{created['id']}", json={"completed": completed})

    assert response.status_code == 200
    body = response.json()
    assert_todo_shape(body)
    assert body == {**created, "completed": completed}


def test_delete_returns_204_with_empty_body(client: TestClient, create_todo):
    created = create_todo()

    response = client.delete(f"/api/todos/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/api/todos").json() == []


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_missing_id_returns_404_with_detail(client: TestClient, method: str):
    kwargs = {"json": {"completed": True}} if method == "patch" else {}

    response = getattr(client, method)(f"/api/todos/{MISSING_ID}", **kwargs)

    assert response.status_code == 404
    assert response.json() == {"detail": "Todo not found"}


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_non_integer_id_returns_422(client: TestClient, method: str):
    kwargs = {"json": {"completed": True}} if method == "patch" else {}

    response = getattr(client, method)("/api/todos/abc", **kwargs)

    assert_validation_error(response, "todo_id")


def test_create_with_title_too_long_returns_422(client: TestClient):
    response = client.post("/api/todos", json={"title": "x" * (main.MAX_TITLE_LENGTH + 1)})

    assert_validation_error(response, "title")


@pytest.mark.parametrize("payload", [{}, {"title": None}, {"title": 123}])
def test_create_with_invalid_payload_returns_422(client: TestClient, payload: dict):
    response = client.post("/api/todos", json=payload)

    assert_validation_error(response, "title")


def test_create_with_blank_title_returns_400_with_detail(client: TestClient):
    response = client.post("/api/todos", json={"title": "   "})

    assert response.status_code == 400
    assert response.json() == {"detail": "Todo title cannot be empty"}


@pytest.mark.parametrize("payload", [{}, {"completed": "maybe"}, {"completed": None}])
def test_update_with_invalid_payload_returns_422(client: TestClient, create_todo, payload: dict):
    created = create_todo()

    response = client.patch(f"/api/todos/{created['id']}", json=payload)

    assert_validation_error(response, "completed")
