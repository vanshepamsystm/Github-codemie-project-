"""KAN-33 (automated API tests + CI pipeline) tests.

Validates the deliverables of the ticket rather than re-testing the Todo API
(that is done by ``test_api_todos.py`` / ``test_api_kan32.py``):

* R1 API test suite exists, covers CRUD + negative cases, never touches the real DB
* R2 ``.github/workflows/ci.yml`` runs lint + tests and targets ``master``
* R3 CI installs everything the tests need from ``requirements.txt``
* R4 README documents how to run the tests locally (and the documented commands work)
* R5 The exact commands CI/README use succeed (BUG-1: they currently do not)

Traceability IDs (TC-KAN33-xx) map to docs/qa/KAN-33/KAN-33-manual-test-cases.md.
Only new third-party import: PyYAML, which arrives through ``uvicorn[standard]`` (asserted in TC-KAN33-31).
"""
from pathlib import Path
import ast
import hashlib
import os
import re
import shlex
import subprocess
import sys
import tomllib

import pytest
import yaml
from fastapi.testclient import TestClient

import main

PROJECT_ROOT = Path(main.BASE_DIR)
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"
README_PATH = PROJECT_ROOT / "README.md"
RUFF_CONFIG_PATH = PROJECT_ROOT / "ruff.toml"
TODOS_TEST_FILE = PROJECT_ROOT / "tests" / "test_api_todos.py"
TODO_KEYS = {"id", "title", "completed"}


# --- Helpers ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ruff_config() -> dict:
    return tomllib.loads(RUFF_CONFIG_PATH.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML follows YAML 1.1, so the bare key `on` is parsed as boolean True.
    return workflow.get("on", workflow.get(True))


def _steps(job: dict) -> list[dict]:
    return job["steps"]


def _index_of_run(job: dict, pattern: str) -> int:
    """Index of the first step whose `run` script has a line matching ``pattern``."""
    for index, step in enumerate(_steps(job)):
        for line in step.get("run", "").splitlines():
            if re.search(pattern, line.strip()):
                return index
    raise AssertionError(f"no step runs a command matching {pattern!r}")


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def _pytest_args_from(command: str) -> list[str]:
    tokens = shlex.split(command)
    assert tokens[0] == "pytest", command
    return tokens[1:]


def _workflow_pytest_command(workflow: dict) -> str:
    index = _index_of_run(workflow["jobs"]["test"], r"^pytest\b")
    run = _steps(workflow["jobs"]["test"])[index]["run"]
    return next(line.strip() for line in run.splitlines() if line.strip().startswith("pytest"))


def _readme_test_section() -> str:
    text = README_PATH.read_text(encoding="utf-8")
    match = re.search(r"^## Run the automated tests\s*$(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert match, "README has no 'Run the automated tests' section"
    return match.group(1)


def _readme_commands() -> list[str]:
    commands: list[str] = []
    for block in re.findall(r"```(?:\w+)?\n(.*?)```", _readme_test_section(), re.S):
        commands += [line.strip() for line in block.splitlines() if line.strip()]
    return commands


def _collect(args: list[str], *, isolated: bool) -> subprocess.CompletedProcess:
    """`pytest --collect-only` in a subprocess.

    ``isolated=True`` (``python -I``) leaves the working directory off ``sys.path``, which is how the bare
    ``pytest`` console script behaves in CI. ``isolated=False`` (``python -m pytest``) adds the cwd.
    """
    command = [sys.executable] + (["-I"] if isolated else []) + [
        "-m", "pytest", *args, "--collect-only", "-p", "no:cacheprovider",
    ]
    env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "TODO_DB_PATH")}
    return subprocess.run(command, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=120)


def _ruff(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120,
    )


def _requirement_names() -> set[str]:
    names = set()
    for line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.match(r"[A-Za-z0-9_.\-]+", line).group(0)
        names.add(name.lower().replace("_", "-"))
    return names


# --- R1: API test suite ------------------------------------------------------------


def test_openapi_documents_all_crud_operations(client: TestClient):  # TC-KAN33-01
    paths = client.get("/openapi.json").json()["paths"]
    assert {"get", "post"} <= set(paths["/api/todos"])
    assert {"patch", "delete"} <= set(paths["/api/todos/{todo_id}"])
    assert "201" in paths["/api/todos"]["post"]["responses"]
    assert "204" in paths["/api/todos/{todo_id}"]["delete"]["responses"]


def test_todo_payloads_have_exact_keys_and_types(client: TestClient, create_todo):  # TC-KAN33-02
    created = create_todo("shape")
    listed = client.get("/api/todos").json()[0]
    patched = client.patch(f"/api/todos/{created['id']}", json={"completed": True}).json()
    for payload in (created, listed, patched):
        assert set(payload) == TODO_KEYS
        assert isinstance(payload["id"], int)
        assert isinstance(payload["title"], str)
        assert isinstance(payload["completed"], bool)


def test_existing_api_suite_covers_crud_and_negative_cases():  # TC-KAN33-03
    source = TODOS_TEST_FILE.read_text(encoding="utf-8")
    for method in ("post", "get", "patch", "delete"):
        assert f"client.{method}(" in source, f"no test calls client.{method}"
    for status in ("201", "204", "400", "404", "422"):
        assert re.search(rf"status_code == {status}\b", source), f"no assertion on HTTP {status}"


def test_suite_never_modifies_the_real_database():  # TC-KAN33-04
    real_db = PROJECT_ROOT / "todos.db"
    if not real_db.exists():
        pytest.skip("real todos.db not present")
    before = hashlib.sha256(real_db.read_bytes()).hexdigest()
    env = {key: value for key, value in os.environ.items() if key != "TODO_DB_PATH"}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(TODOS_TEST_FILE), "-q", "-p", "no:cacheprovider"],
        cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout[-2000:]
    assert hashlib.sha256(real_db.read_bytes()).hexdigest() == before


# --- R2: CI workflow ---------------------------------------------------------------


def test_workflow_file_exists_and_is_valid_yaml(workflow: dict):  # TC-KAN33-10
    assert WORKFLOW_PATH.is_file()
    assert isinstance(workflow, dict)
    assert workflow["name"] == "CI"


def test_workflow_triggers_on_pr_and_push_to_master(workflow: dict):  # TC-KAN33-11
    triggers = _triggers(workflow)
    assert "master" in triggers["pull_request"]["branches"]
    assert "master" in triggers["push"]["branches"]


def test_workflow_defines_lint_and_test_jobs(workflow: dict):  # TC-KAN33-12
    assert {"lint", "test"} <= set(workflow["jobs"])
    for name in ("lint", "test"):
        assert workflow["jobs"][name]["runs-on"] == "ubuntu-latest"


@pytest.mark.parametrize("job_name", ["lint", "test"])
def test_jobs_checkout_and_setup_python_with_pinned_major(workflow: dict, job_name: str):  # TC-KAN33-13
    uses = [step["uses"] for step in _steps(workflow["jobs"][job_name]) if "uses" in step]
    assert any(re.fullmatch(r"actions/checkout@v\d+", item) for item in uses)
    assert any(re.fullmatch(r"actions/setup-python@v\d+", item) for item in uses)
    checkout = next(i for i, item in enumerate(uses) if item.startswith("actions/checkout"))
    setup = next(i for i, item in enumerate(uses) if item.startswith("actions/setup-python"))
    assert checkout < setup


def test_lint_job_installs_requirements_then_runs_ruff(workflow: dict):  # TC-KAN33-14
    job = workflow["jobs"]["lint"]
    install = _index_of_run(job, r"^pip install -r requirements\.txt$")
    lint = _index_of_run(job, r"^ruff check \.$")
    assert install < lint


def test_test_job_installs_requirements_then_runs_pytest_without_e2e(workflow: dict):  # TC-KAN33-15
    job = workflow["jobs"]["test"]
    install = _index_of_run(job, r"^pip install -r requirements\.txt$")
    run = _index_of_run(job, r"^pytest\b")
    assert install < run
    args = _pytest_args_from(_workflow_pytest_command(workflow))
    assert "tests" in args
    assert "--ignore=tests/e2e" in args


def test_test_matrix_covers_minimum_and_current_python(workflow: dict):  # TC-KAN33-16
    versions = workflow["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert {"3.11", "3.12"} <= set(versions)
    setup = next(s for s in _steps(workflow["jobs"]["test"]) if s.get("uses", "").startswith("actions/setup-python"))
    assert setup["with"]["python-version"] == "${{ matrix.python-version }}"
    assert workflow["jobs"]["test"]["strategy"].get("fail-fast") is False


def test_lint_python_version_is_not_below_ruff_target(workflow: dict, ruff_config: dict):  # TC-KAN33-17
    setup = next(s for s in _steps(workflow["jobs"]["lint"]) if s.get("uses", "").startswith("actions/setup-python"))
    digits = ruff_config["target-version"].removeprefix("py")  # "py311" -> "311"
    target = (int(digits[0]), int(digits[1:]))
    assert _version_tuple(str(setup["with"]["python-version"])) >= target


@pytest.mark.parametrize("job_name", ["lint", "test"])
def test_pip_cache_has_a_dependency_file_to_hash(workflow: dict, job_name: str):  # TC-KAN33-18
    """`cache: pip` makes setup-python fail when it finds no requirements file."""
    setup = next(s for s in _steps(workflow["jobs"][job_name]) if s.get("uses", "").startswith("actions/setup-python"))
    assert setup["with"].get("cache") == "pip"
    assert REQUIREMENTS_PATH.is_file()


def test_ci_does_not_run_browser_tests(workflow: dict):  # TC-KAN33-19
    # Inspect real steps only; the workflow legitimately mentions Playwright in a comment.
    for job in workflow["jobs"].values():
        for step in _steps(job):
            assert "playwright" not in (step.get("run", "") + step.get("uses", "")).lower()
    assert (PROJECT_ROOT / "tests" / "e2e").is_dir()


# --- R5: the commands CI and README use actually work --------------------------------


def test_workflow_pytest_command_collects_via_python_dash_m(workflow: dict):  # TC-KAN33-20
    """Sanity: with the cwd on sys.path the CI arguments collect the API tests and skip e2e."""
    result = _collect(_pytest_args_from(_workflow_pytest_command(workflow)), isolated=False)
    assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-1500:]
    node_ids = [line for line in result.stdout.splitlines() if "::" in line]
    assert len(node_ids) >= 70
    assert not [line for line in node_ids if "tests/e2e" in line.replace("\\", "/")]


@pytest.mark.parametrize("source", ["workflow", "readme"])
def test_documented_pytest_command_works_like_the_console_script(workflow: dict, source: str):  # TC-KAN33-21
    if source == "workflow":
        command = _workflow_pytest_command(workflow)
    else:
        command = next(c for c in _readme_commands() if c.startswith("pytest"))
    result = _collect(_pytest_args_from(command), isolated=True)
    assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-1500:]
    assert "No module named 'main'" not in result.stdout + result.stderr


# --- R3: dependencies installed in CI ------------------------------------------------


def test_requirements_declare_runtime_test_and_lint_tools():  # TC-KAN33-30
    names = _requirement_names()
    assert {"fastapi", "uvicorn", "pytest", "httpx", "ruff"} <= names


def test_every_third_party_import_is_covered_by_requirements():  # TC-KAN33-31
    declared = _requirement_names()
    requirements_text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    local = {"main"} | {path.stem for path in (PROJECT_ROOT / "tests").glob("*.py")}
    # imports that are installed as a dependency of a declared package
    transitive = {"pydantic": "fastapi", "yaml": "uvicorn[standard]"}

    sources = [PROJECT_ROOT / "main.py", *sorted((PROJECT_ROOT / "tests").glob("*.py"))]
    imported: set[str] = set()
    for path in sources:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])

    third_party = imported - set(sys.stdlib_module_names) - local
    assert {"fastapi", "pytest"} <= third_party  # the scan itself found something
    missing = sorted(
        name for name in third_party
        if name.replace("_", "-") not in declared and name not in transitive
    )
    assert missing == []
    for module in third_party & set(transitive):
        provider = transitive[module]
        assert provider.split("[")[0] in declared
        if "[" in provider:
            assert provider in requirements_text


def test_requirements_do_not_pull_in_browser_tooling():  # TC-KAN33-32
    names = _requirement_names()
    assert not {"playwright", "pytest-playwright"} & names


# --- Ruff configuration --------------------------------------------------------------


def test_ruff_config_values(ruff_config: dict):  # TC-KAN33-40
    assert ruff_config["line-length"] == 120
    assert ruff_config["target-version"] == "py311"
    assert {"E", "F"} <= set(ruff_config["lint"]["select"])
    assert {"docs", "task"} <= set(ruff_config["extend-exclude"])


def test_ruff_target_matches_oldest_ci_python(workflow: dict, ruff_config: dict):  # TC-KAN33-41
    oldest = min(workflow["jobs"]["test"]["strategy"]["matrix"]["python-version"], key=_version_tuple)
    assert ruff_config["target-version"] == "py" + oldest.replace(".", "")


def test_ruff_check_passes_on_repository():  # TC-KAN33-42
    result = _ruff("check", ".", "--no-cache")
    assert result.returncode == 0, result.stdout + result.stderr


def test_ruff_flags_unused_import(tmp_path: Path):  # TC-KAN33-43
    probe = tmp_path / "probe.py"
    probe.write_text("import os\n", encoding="utf-8")
    result = _ruff("check", "--config", str(RUFF_CONFIG_PATH), "--no-cache", "--output-format", "concise", str(probe))
    assert result.returncode == 1
    assert "F401" in result.stdout


@pytest.mark.parametrize(
    ("length", "expected_exit"), [(120, 0), (121, 1)], ids=["at-limit-120", "over-limit-121"]
)
def test_ruff_line_length_boundary(tmp_path: Path, length: int, expected_exit: int):  # TC-KAN33-44
    probe = tmp_path / "probe.py"
    probe.write_text('x = "' + "a" * (length - 6) + '"\n', encoding="utf-8")
    assert len(probe.read_text(encoding="utf-8").rstrip("\n")) == length
    result = _ruff("check", "--config", str(RUFF_CONFIG_PATH), "--no-cache", "--output-format", "concise", str(probe))
    assert result.returncode == expected_exit, result.stdout
    if expected_exit:
        assert "E501" in result.stdout


def test_ruff_scope_includes_code_and_excludes_docs_and_task():  # TC-KAN33-45
    result = _ruff("check", "--show-files", ".")
    assert result.returncode == 0, result.stderr
    files = [Path(line.strip()).resolve().relative_to(PROJECT_ROOT).as_posix() for line in result.stdout.splitlines()
             if line.strip()]
    assert {"main.py", "tests/conftest.py", "tests/test_api_todos.py"} <= set(files)
    assert not [f for f in files if f.startswith(("docs/", "task/", ".venv/"))]


# --- R4: README ---------------------------------------------------------------------


def test_readme_has_local_test_instructions():  # TC-KAN33-50
    commands = _readme_commands()
    assert "pip install -r requirements.txt" in commands
    assert "pytest tests --ignore=tests/e2e" in commands
    assert "ruff check ." in commands


def test_readme_commands_match_what_ci_runs(workflow: dict):  # TC-KAN33-51
    ci_pytest_args = _pytest_args_from(_workflow_pytest_command(workflow))
    readme_pytest = next(c for c in _readme_commands() if c.startswith("pytest"))
    readme_args = _pytest_args_from(readme_pytest)
    ci_ignores = [arg for arg in ci_pytest_args if arg.startswith("--ignore")]
    readme_ignores = [arg for arg in readme_args if arg.startswith("--ignore")]
    assert ci_ignores == readme_ignores
    assert "tests" in readme_args


def test_readme_explains_e2e_exclusion_and_points_to_existing_workflow():  # TC-KAN33-52
    section = _readme_test_section()
    assert "tests/e2e" in section
    assert "requirements-e2e.txt" in section
    assert "playwright install" in section
    assert ".github/workflows/ci.yml" in section
    assert (PROJECT_ROOT / "requirements-e2e.txt").is_file()
    assert WORKFLOW_PATH.is_file()
