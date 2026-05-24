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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **forge** (9115 symbols, 18104 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/forge/context` | Codebase overview, check index freshness |
| `gitnexus://repo/forge/clusters` | All functional areas |
| `gitnexus://repo/forge/processes` | All execution flows |
| `gitnexus://repo/forge/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
