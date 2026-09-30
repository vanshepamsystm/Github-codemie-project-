from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "todos.db"

app = FastAPI(title="Half-Baked Todo")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class TodoCreate(BaseModel):
    title: str


class TodoUpdate(BaseModel):
    completed: bool


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            )"""
        )


initialize_database()


@app.get("/")
def home() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/todos")
def list_todos() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, title, completed FROM todos ORDER BY id DESC"
        ).fetchall()
    return [
        {"id": row["id"], "title": row["title"], "completed": bool(row["completed"])}
        for row in rows
    ]


@app.post("/api/todos", status_code=201)
def create_todo(todo: TodoCreate) -> dict:
    title = todo.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Todo title cannot be empty")

    with get_connection() as connection:
        cursor = connection.execute("INSERT INTO todos (title) VALUES (?)", (title,))
        todo_id = cursor.lastrowid
    return {"id": todo_id, "title": title, "completed": False}


@app.patch("/api/todos/{todo_id}")
def update_todo(todo_id: int, todo: TodoUpdate) -> dict:
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE todos SET completed = ? WHERE id = ?",
            (int(todo.completed), todo_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Todo not found")
        row = connection.execute(
            "SELECT id, title, completed FROM todos WHERE id = ?", (todo_id,)
        ).fetchone()
    return {"id": row["id"], "title": row["title"], "completed": bool(row["completed"])}


@app.delete("/api/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int) -> None:
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Todo not found")