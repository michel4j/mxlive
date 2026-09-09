## Agent skills

### Issue tracker

GitHub issues tracked via `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout (`CONTEXT.md` and `docs/adr/` at root). See `docs/agents/domain.md`.

## Environment Setup and Execution

* **Dependency Installation:** Run `uv sync` to set up or sync the environment.
* **Preferred Invocation:** Always run commands prefixing them with `uv run` (e.g., `uv run pytest`, `uv run python main.py`).
* **Environment Path Inspection:** Use `uv python find` if an absolute path to the virtual environment python interpreter is required.

## Commands
- Run the test suite: `uv run manage.py test `
- Run a specific test file: `uv run manage.py test mxlive.dashboard`