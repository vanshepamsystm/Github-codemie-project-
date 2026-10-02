const form = document.querySelector("#todo-form");
const input = document.querySelector("#todo-input");
const list = document.querySelector("#todo-list");
const status = document.querySelector("#status");

function errorMessage(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item) => item.msg).join("; ");
  }
  return "Something went wrong";
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(errorMessage(error.detail));
  }

  return response.status === 204 ? null : response.json();
}

function renderTodos(todos) {
  list.replaceChildren();

  for (const todo of todos) {
    const row = document.createElement("li");
    row.className = `todo-row${todo.completed ? " is-complete" : ""}`;

    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.checked = todo.completed;
    toggle.setAttribute("aria-label", `Mark ${todo.title} complete`);
    toggle.addEventListener("change", async () => {
      try {
        await request(`/api/todos/${todo.id}`, {
          method: "PATCH",
          body: JSON.stringify({ completed: toggle.checked }),
        });
        await loadTodos();
      } catch (error) {
        showError(error.message);
      }
    });

    const title = document.createElement("span");
    title.textContent = todo.title;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove";
    remove.addEventListener("click", async () => {
      try {
        await request(`/api/todos/${todo.id}`, { method: "DELETE" });
        await loadTodos();
      } catch (error) {
        showError(error.message);
      }
    });

    row.append(toggle, title, remove);
    list.append(row);
  }
}

function showError(message = "") {
  status.textContent = message;
}

async function loadTodos() {
  try {
    renderTodos(await request("/api/todos"));
    showError();
  } catch (error) {
    showError(error.message);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = input.value.trim();
  if (!title) return;

  try {
    await request("/api/todos", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
    input.value = "";
    await loadTodos();
  } catch (error) {
    showError(error.message);
  }
});

loadTodos();