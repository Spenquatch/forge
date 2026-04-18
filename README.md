# 🔥 Forge v1.2 - Modular AI Agent System

A modular, agentic AI framework designed with hot-swappable models, LangGraph orchestration, and reinforcement learning-based feedback loops.

## 📚 Documentation

- [Installation Guide](docs/installation.md)
- [Getting Started](docs/getting_started.md)
- [Architecture Overview](docs/architecture_overview.md)
- [Leadership Architecture](docs/leadership_architecture.md)
- [Configuration System](docs/configuration_system.md)
- [Provider System](docs/provider_system.md)
- [Provider Support Status](docs/provider_support.md)
- [Role-Based Configuration](docs/role_based_configuration.md)
- [Testing Guide](docs/testing_guide.md)
- [Checkpointing & Persistence](docs/checkpointing.md)
- [Migration Plan (Archived)](archived/LANGGRAPH_MIGRATION_PLAN.md)

## 🚀 Project Setup Instructions

This project uses UV for virtual environment management and Poetry for dependency management to ensure a consistent and fast development experience. We've completely switched to a Poetry-based workflow, eliminating the need for requirements.txt.

### Prerequisites

- Python 3.11+ installed
- Git

### Installation

#### 1. Install UV

[UV](https://github.com/astral-sh/uv) is a fast, reliable Python package installer and resolver built in Rust.

```bash
# Install UV using the installer script
curl -sSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

For Windows:

```powershell
# Install UV via the Windows installer script
(Invoke-WebRequest -Uri https://astral.sh/uv/install.ps1 -UseBasicParsing).Content | powershell -Command -

# Verify installation
uv --version
```

#### 2. Install Poetry

[Poetry](https://python-poetry.org/) is a tool for dependency management and packaging.

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Verify installation
poetry --version
```

For Windows:

```powershell
# Install Poetry
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Verify installation
poetry --version
```

#### 3. Clone the Repository

```bash
git clone <your-repo-url>
cd <repo-dir>
```

#### 4. Set Up the Development Environment with UV

```bash
# Create a virtual environment in the .venv directory
uv venv

# Activate the virtual environment
# For Linux/macOS:
source .venv/bin/activate

# For Windows (PowerShell):
.venv\Scripts\Activate.ps1

# For Windows (CMD):
.venv\Scripts\activate.bat
```

#### 5. Install Dependencies

```bash
# Configure Poetry to use the existing .venv
poetry config virtualenvs.in-project true
poetry config virtualenvs.path ".venv"

# Install dependencies using Poetry
poetry install
```

#### 6. Set Up Environment Variables

Create a `.env` file in the project root for API keys:

```bash
# Create .env file
cat > .env << 'EOF'
OPENAI_API_KEY=your_openai_key_here
EOF

# Load environment variables
# For Linux/macOS:
source .env

# For Windows (PowerShell):
Get-Content .env | ForEach-Object { $var = $_.Split('='); if($var[0] -and !$var[0].StartsWith('#')) { [Environment]::SetEnvironmentVariable($var[0], $var[1], 'Process') } }
```

## System Architecture

Forge uses a two-tier agent architecture:

```
flowchart TD
    Orchestrator([Orchestrator Agent])
    Execute([Execute Agent])
    Critique([Critique Agent])
    Refine([Refine Agent])
    Review([Review Agent])
    Done([Done])
    Monitor([Monitor Agent])
    MetaLearning([Meta Learning Agent])

    Orchestrator -->|Selects prompt & model| Execute
    Execute     --> Critique
    Critique    --> Refine
    Refine      --> Review
    Review      -->|Pass| Done
    Review      -->|Fail| Monitor
    Monitor     -->|Adjust Strategy| Orchestrator
    Monitor     -->|Log & Reward| MetaLearning
    MetaLearning -->|Update Policy| Orchestrator
```

1. **Leadership Team**

   - **Orchestrator Agent**: Analyzes tasks and selects optimal models and prompts
   - **Monitor Agent**: Evaluates failures and adjusts strategy
   - **Meta Learning Agent**: Learns from experience via reinforcement learning with skrl

2. **Worker Team**
   - **Execute Agent**: Primary task execution
   - **Critique Agent**: Error detection and feedback
   - **Refine Agent**: Improvements based on critique
   - **Review Agent**: Quality assurance and pass/fail decisions

For more details on this architecture, see [Leadership Architecture](docs/leadership_architecture.md).

## Using LangGraph Orchestration

Forge includes a LangGraph-based orchestrator that adds leadership nodes, conditional routing, streaming, and checkpointing. LangGraph is now the only backend.

- Run via module entrypoint:

  ```bash
  poetry run python -m anvil run "Write a haiku about Python"
  ```

- Stream node-level progress during execution (enhanced CLI):

  ```bash
  poetry run python -m anvil run "Write a haiku about Python" --stream
  ```

- For full LangGraph/LangChain callback tracing (very noisy), add `--stream-verbose`.

- The previous simple graph has been removed. All runs use LangGraph.

### Env flags

- `FORGE_LG_CHECKPOINT` (default `memory`): `memory` or `sqlite`.
- `FORGE_LG_DB_PATH` (default `forge_checkpoints.db`): SQLite DB path when using `sqlite`.
- `FORGE_LG_MAX_ATTEMPTS` (default `3`): retry ceiling for review failures.

See [Checkpointing & Persistence](docs/checkpointing.md) for details.


## Mini-Harness Surface

Forge now includes a separate task/strategy surface modeled after the mini-harness experiments. This sits alongside the existing leadership/LangGraph flow rather than replacing it.

Use it when you want explicit task specs, strategy specs, workspace write-policy enforcement, and structured proposer/falsifier/patcher or analysis-review loops.

Example:

```bash
poetry run python -m anvil.cli harness-run   --task examples/harness/tasks/recommend_automation_improvements.yaml   --strategy examples/harness/strategies/analysis_review_bounded_codex_claude.yaml   --workspace /path/to/repo   --out-root .forge-harness-runs
```

For the alternate trust-oriented mode, swap in `examples/harness/strategies/analysis_review_trust_codex_claude.yaml`.

For analysis-review tasks, `review_requirements.evidence_cap_policy` defaults to `trim_to_cap`, which canonicalizes path-like refs and trims oversize evidence lists before semantic validation. Set it to `strict` when you want fail-fast bounded-review enforcement instead.

The harness writes a run directory containing:
- `summary.json`
- `REPORT.md`
- `FINAL_ANSWER.json` / `FINAL_ANSWER.md` when a final structured answer is available
- per-stage prompt/schema/output artifacts
- validator logs and workspace policy checkpoints

### What you get with LangGraph

- Leadership nodes (orchestrator, monitor, meta‑learning) that set strategy, adjust on failure, and record learning signals.
- Conditional routing with retries and a finalize step that sets `result` and `completion_status`.
- Streaming of node events for live observability.
- Checkpointing (in‑memory default; optional SQLite persistence).

## 🧪 Testing Your Installation

```bash
poetry run pytest -q

# Targeted tests for the LangGraph backend (all offline)
poetry run pytest -q tests/test_lg_offline_smoke.py
poetry run pytest -q tests/test_langgraph_parity.py
poetry run pytest -q tests/test_graph_factory_compat.py
```

For detailed testing instructions, see the [Testing Guide](docs/testing_guide.md).

## 🤖 AI Provider Support

Forge supports multiple AI providers with role-based configuration:

- **OpenAI**: GPT models with full feature support (text, chat, embeddings)
- **Anthropic**: Claude models with text and chat support
- **Local Models**: Transformers and LlamaCpp support

Each provider can be configured with different parameters for different roles (execute, critique, refine, etc.). See [Role-Based Configuration](docs/role_based_configuration.md) for details.

## 📋 Contributing

1. Create a new branch for your feature/fix
2. Implement your changes
3. Run code quality tools (black, isort, ruff, mypy)
4. Run incremental tests to verify functionality
5. Submit a pull request

## 📝 License

MIT License (see `LICENSE`).
