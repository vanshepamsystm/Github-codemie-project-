from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
import logging
from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "todos.db"
SQLITE_BUSY_TIMEOUT_SECONDS = 5.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s level=%(levelname)s logger=%(name)s %(message)s",
)
logger = logging.getLogger("todo")


class TodoCreate(BaseModel):
    title: str


class TodoUpdate(BaseModel):
    completed: bool


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a connection that commits on success, rolls back on error, and always closes."""
    connection = sqlite3.connect(DATABASE_PATH, timeout=SQLITE_BUSY_TIMEOUT_SECONDS)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    with get_connection() as connection:
        # WAL lets readers proceed while a write is in progress.
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            )"""
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    logger.info("event=startup database=%s", DATABASE_PATH.name)
    yield


app = FastAPI(title="Half-Baked Todo", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1")
    except sqlite3.Error:
        logger.exception("event=readiness_failed")
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ready"})


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
    logger.info("event=todo_created id=%s", todo_id)
    return {"id": todo_id, "title": title, "completed": False}


@app.patch("/api/todos/{todo_id}")
def update_todo(todo_id: int, todo: TodoUpdate) -> dict:
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE todos SET completed = ? WHERE id = ?",
            (int(todo.completed), todo_id),
        )
        if cursor.rowcount == 0:
            logger.warning("event=todo_not_found action=update id=%s", todo_id)
            raise HTTPException(status_code=404, detail="Todo not found")
        row = connection.execute(
            "SELECT id, title, completed FROM todos WHERE id = ?", (todo_id,)
        ).fetchone()
    logger.info("event=todo_updated id=%s completed=%s", todo_id, todo.completed)
    return {"id": row["id"], "title": row["title"], "completed": bool(row["completed"])}


@app.delete("/api/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int) -> None:
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        if cursor.rowcount == 0:
            logger.warning("event=todo_not_found action=delete id=%s", todo_id)
            raise HTTPException(status_code=404, detail="Todo not found")
    logger.info("event=todo_deleted id=%s", todo_id)
