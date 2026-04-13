# Repository Guidelines

## Project Structure & Module Organization

- `anvil/`: primary Python package (CLI entrypoint is `python -m anvil`), orchestration graph, providers, persistence, and leadership logic.
- `config/models.yaml`: provider/model configuration and role-based overrides (execute/critique/refine/review/reflect).
- `tests/`: pytest suite (`tests/providers/` holds provider-specific tests).
- `docs/`: architecture and usage docs referenced from `README.md`.
- `examples/`: small runnable scripts (run from repo root).
- `scripts/`: developer utilities/ad-hoc helpers (not part of the packaged CLI or pytest suite).
- `archived/`: legacy plans/experiments; avoid changing unless you’re intentionally working on archived material.

## Build, Test, and Development Commands

- Install deps: `poetry install` (optionally `poetry install -E all` for optional backends).
- Run CLI:
  - `poetry run python -m anvil list`
  - `poetry run python -m anvil run "Write a haiku" --stream`
  - `poetry run python -m anvil test openai` (requires API keys)
- Run tests:
  - `poetry run pytest -q`
  - Offline LangGraph smoke tests: `poetry run pytest -q tests/test_lg_offline_smoke.py`

## Coding Style & Naming Conventions

- Python: format with Black (line length 88) and sort imports with isort; lint with Ruff; type-check with mypy (configured in `pyproject.toml`).
- Naming: `snake_case.py`, `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.
- Typical checks: `poetry run ruff check . && poetry run black . && poetry run isort . && poetry run mypy anvil`.

## Testing Guidelines

- Framework: `pytest` + `pytest-asyncio`. Tests are named `test_*.py` and live under `tests/`.
- Prefer adding/keeping offline tests for core orchestration; use `python -m anvil test <provider>` for online provider verification when keys are available.

## Commit & Pull Request Guidelines

- Commit messages follow a lightweight conventional style (seen in history): `feat: ...`, `fix: ...`, `chore: ...`.
- PRs should include: a short problem statement, the approach, commands run (e.g. `poetry run pytest -q`), and screenshots/log snippets for CLI output changes; link any related issue/task ids when applicable.

## Security & Configuration Tips

- Store credentials in `.env` (e.g. `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) and avoid committing secrets.
- When changing `config/models.yaml`, also update any affected docs/examples to keep the CLI behavior and documentation consistent.

