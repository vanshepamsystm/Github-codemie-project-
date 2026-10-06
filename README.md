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

## Manual smoke test checklist (KAN-2)

1. Start the app and open http://127.0.0.1:8000/ .
2. On page load, confirm the browser devtools console shows no errors.
3. Add a new todo and confirm it appears in the list.
4. Toggle the todo to completed and confirm the UI updates.
5. Remove the todo and confirm it disappears from the list.

---

### Placeholder note (KAN-7)

This is a non-functional placeholder commit for the PR branch associated with Jira **KAN-7** (automated tests + CI). No behavior changes are intended.  
