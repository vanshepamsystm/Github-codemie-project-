# Half-Baked Todo

A deliberately small todo prototype: plain HTML, CSS, and JavaScript on the frontend, FastAPI for the API, and SQLite 3 for storage.

## Run it

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://127.0.0.1:8000. The SQLite database (`todos.db`) is created automatically the first time the app starts.

The frontend is intentionally barebones, but adding, completing, and removing todos is wired up end to end.