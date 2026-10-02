from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "todos.db"
BUSY_TIMEOUT_MS = 5000
TITLE_MAX_LENGTH = 200

app = FastAPI(title="Half-Baked Todo")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class TodoCreate(BaseModel):
    # Whitespace is stripped before the length check, so padding cannot be
    # used to bypass the limit. Blank titles are rejected in create_todo (400).
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(max_length=TITLE_MAX_LENGTH)


class TodoUpdate(BaseModel):
    completed: bool


class TodoRead(BaseModel):
    id: int
    title: str
    completed: bool


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    # Wait for a competing writer instead of failing immediately with
    # "database is locked".
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return connection


def row_to_todo(row: sqlite3.Row) -> TodoRead:
    return TodoRead(id=row["id"], title=row["title"], completed=bool(row["completed"]))


def initialize_database() -> None:
    with get_connection() as connection:
        # WAL lets readers and a writer proceed concurrently; the mode is
        # stored in the database file, so setting it once is enough.
        connection.execute("PRAGMA journal_mode = WAL")
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


@app.get("/api/todos", response_model=list[TodoRead])
def list_todos() -> list[TodoRead]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, title, completed FROM todos ORDER BY id DESC"
        ).fetchall()
    return [row_to_todo(row) for row in rows]


@app.post("/api/todos", status_code=201, response_model=TodoRead)
def create_todo(todo: TodoCreate) -> TodoRead:
    title = todo.title
    if not title:
        raise HTTPException(status_code=400, detail="Todo title cannot be empty")

    with get_connection() as connection:
        cursor = connection.execute("INSERT INTO todos (title) VALUES (?)", (title,))
        todo_id = cursor.lastrowid
    return TodoRead(id=todo_id, title=title, completed=False)


@app.patch("/api/todos/{todo_id}", response_model=TodoRead)
def update_todo(todo_id: int, todo: TodoUpdate) -> TodoRead:
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
    return row_to_todo(row)


@app.delete("/api/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int) -> None:
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Todo not found")