# North Star

**Forge becomes a planning refinery** that can repeatedly generate → measure → patch → gate until it can *prove* it didn’t miss major work.

To make that real, everything converges on two measurable artifacts:

1. **Run Store**: what happened (providers/params/decisions), how long it took, what it cost, why it looped, and what it produced.
2. **Coverage Ledger**: what requirements/dimensions are covered, what’s missing, and evidence pointers for each claim.

If you build these first, “leadership”, Monte Carlo, and any RL become straightforward optimization instead of guesswork.

---

# Design principles (vNext)

1. **Config-driven agents**: each node/agent has a crisp contract (inputs/outputs, rubric, schema, stop conditions).
2. **Cheap-first / expensive-last**: cheaper models draft + audit + patch; stronger models gate only when close.
3. **Measure, don’t vibe**: each loop emits structured deltas so termination can be deterministic.
4. **Cold start must be safe**: exploration is bounded (caps, neutral priors) to avoid runaway cost.
5. **Tooling-ready, not tool-dependent**: planning/decomposition must work without tools; tools improve verification later.
6. **Interop by default**: trace/span data should be exportable to LangSmith/Langfuse later without redesign.

---

# Versioning + migrations (cross-cutting)

You’re about to introduce 3 evolving surfaces: config schema, artifact schemas, and the Run Store schema. Make versioning explicit up front.

**Schema versioning (config + artifacts + Run Store):**

- `config.schema_version` (default `1`)
- each artifact includes `artifact_schema_version`
- Run Store includes `db_schema_version` and supports forward migrations
- Back-compat policy:
  - missing fields default safely
  - new required fields have defaults
  - deprecations are warned for N releases before removal

This prevents “why did old runs break” drift and keeps replay/inspection viable.

---

# Roadmap phases (sequenced, no big-bang refactor)

## Phase 0 — Lock baseline + remove startup friction

Goal: “stable, fast CLI, reproducible runs” with predictable local + API behavior.

### Deliverables

- **True lazy provider initialization + `prewarm`**
  - Current repo behavior still attempts eager init during config reload (`anvil/orchestrator.py:reload_config()` calls `initialize_provider(name)` for each provider).
  - Change to “register configs only” and initialize on first use unless `prewarm: true`.
- **Device auto-selection defaults** for HF providers (`device: auto`) with clean fallback order (cuda → mps → cpu).
- **Deterministic end-of-run summaries** across run + stream:
  - timing, node counts, attempts/loops, provider breakdown, token/cost (when available).
- **Budget caps / stop conditions (config defaults)**
  - `max_attempts`, `timeout_s` (per role), `max_total_runtime_s` (optional), `max_cost_usd` (API), `max_tokens` (local).
- **BudgetManager (shared, enforceable)**
  - A single shared mechanism (carried in state) that tracks `elapsed_s`, `total_tokens`, `estimated_cost_usd`, `attempts_by_role`, and provides `check_or_abort(reason)`.
  - Every node and micro-agent calls it (no scattered one-off cap checks).
- **Smoke eval suite (fast, deterministic)**
  - Ship 5–10 “golden briefs” and an `anvil bench --smoke` mode that runs quickly and deterministically.
  - Run this in CI to catch regressions from dependency/config/schema changes early.

### Acceptance criteria

- `python -m anvil list` is fast and doesn’t trigger heavy imports unless prewarm is enabled.
- Offline smoke tests stay green and deterministic.
- Smoke eval suite runs in CI and flags behavioral regressions quickly.

---

## Phase 1 — Run Store (foundation for everything)

Goal: every run produces durable, queryable data so leadership + bench runs aren’t blind.

### Deliverables

- **Run Store backend** (SQLite recommended; JSONL acceptable initially):
  - `run_id`, timestamp, CLI args/env, strategy, exploration mode, prompt profile/version
  - provider/model/kwargs per role
  - per-node spans: duration, success/fail, retries, output length, token usage + estimated cost (if known)
  - artifact pointers (plan/ledger/deltas) + hashes
- **Minimum Trace/Span schema (interop/export)**
  - `trace_id`, `span_id`, `parent_span_id` (nullable), `name`, `start_ts`, `end_ts`, `status` (`ok|error|aborted`)
  - `attributes` map: `provider`, `model`, `role`, `prompt_profile`, `prompt_version`, `tokens`, `est_cost_usd`, `retries`, `attempt_index`
  - when `status != ok`: `error_type`, `error_message`
  - This is intentionally compatible with later export to Langfuse/LangSmith.
- **Storage policy** (important):
  - Default: store *pointers + hashes* (and small summaries) to avoid ballooning storage / leaking prompts.
  - Optional flags: `--store-content` or `FORGE_STORE_CONTENT=1` to persist full prompts/outputs when desired.
- **Artifact store (content-addressed)**
  - Default layout: `{run_id}/artifacts/`
  - Large blobs stored as `sha256/<hash>.json|.md` (content-addressed; de-duplicated)
  - DB stores: `artifact_type`, `hash`, `size_bytes`, `path`, `redaction_applied: bool`
- **Redaction hook (when `--store-content`)**
  - Redact secrets/keys and optionally PII before persisting content.
  - Default: always redact API keys/secrets/tokens by pattern + known env var names; PII redaction is optional via `--redact-pii` or `FORGE_REDACT_PII=1`.
  - Keeps replay/inspection great without turning the DB into a blob warehouse.
- **CLI commands**:
  - `anvil runs list`
  - `anvil runs show <run_id>`
  - `anvil runs export <run_id> --format jsonl`
  - `anvil runs replay <run_id>` (best-effort; full replay requires stored content or deterministic fixtures)

### Acceptance criteria

- You can answer: “what looped, what did we spend, what was chosen, and why?”
- You can compute: pass rate, iterations-to-pass, cost-to-pass, p95 latency per role/provider.

---

## Phase 2A — Agent Registry (agent = config) + prompt profiles

Goal: add/modify agents without changing orchestration code.

### Deliverables

- `config/agents/` (or `config/agents.yaml`) with inheritance:
  - base roles: `execute`, `critique`, `refine`, `review`, `reflect`
  - profiles: `default`, `planning`, `coding`, etc.
  - provider-specific overlays (optional): local models may need stricter formatting constraints.
- Each agent spec includes:
  - `id`, `role`, `purpose`
  - `system_prompt` (+ append/overrides), prompt version
  - `model_policy`: cheap/mid/expensive + allow/deny lists
  - `tools_allowed` (future)
  - `output_format`: `json | markdown_strict | text`
  - `validation`: `strict | lenient`
  - `repair_strategy`: `none | json_repair_agent:<id> | markdown_resection`
  - `max_output_chars` / `max_output_tokens` (guardrail per agent)
  - `input_schema` / `output_schema` (Pydantic)
  - `stop_condition` / rubric (what “PASS” means)
- **Agent runner**:
  - takes `state + agent_config`
  - calls the chosen provider
  - enforces `BudgetManager.check_or_abort(...)` for deterministic caps
  - validates output (and records validation errors)
  - applies repair policy *inside the agent runner* (not deferred to later phases)
  - writes spans + artifacts to Run Store

### Key pattern (avoid node explosion)

Don’t create 50 LangGraph nodes.
Keep a small set of core nodes and run “micro-agents” (configured passes) inside them.

### Acceptance criteria

- You can add a new “audit.*” agent by editing YAML only.
- Output is validated (or explicitly marked invalid) and stored with schema version.

---

## Phase 2B — Planning mode MVP (decomposition + Plan QA gate)

Goal: deliver the primary user value (engineering planning/decomposition) early, without waiting for Monte Carlo/RL.

### Deliverables

- Add a `decompose` step before `execute` (can be a node or a micro-agent pass).
- Define a **planning artifact schema** (start with strict Markdown sections or JSON):
  - scope + non-goals
  - ordered steps + dependencies
  - acceptance criteria
  - validation plan (tests/commands)
  - risks/unknowns + mitigation
  - estimates/owners (optional)
  - **Stable IDs are required** for all steps/slices/stories/ACs (e.g., `SLICE-001`, `STORY-003`, `AC-003b`) to support evidence pointers, diffs, and ledger convergence.
- Add a **Plan QA gate** (new `plan_review` or a strict `review` profile):
  - hard fail if validation/acceptance criteria/dependencies are missing
  - produce *structured deltas* (what to add/change), not prose
  - **Diff-first gating**: gate/review agents receive `patch_summary + coverage_ledger_delta + unresolved_unknowns` first, and only pull full artifacts if needed.
- Add “cheap-first / expensive-last” routing:
  - local/cheap for draft + critique + refine
  - stronger model only for gating (when configured / available)

### Notes on local models (practical constraint)

Local models often emit reasoning tags or malformed JSON.
Plan for:
- schema repair micro-pass (“fix JSON to match schema”) when needed
- fallback to strict Markdown sections if JSON compliance is unreliable

### Acceptance criteria

- A planning prompt produces a valid plan artifact + a pass/fail gate decision.
- If it fails, the next refine iteration is guided by structured deltas.

---

## Phase 3 — Coverage Ledger gating (make “nothing left unidentified” mechanical)

Goal: “nothing left unidentified” becomes measurable and enforceable.

### Deliverables

1. **Dimension taxonomy** (`config/coverage_dimensions.yaml`)
   - For planning: UX flows, error states, data lifecycle, API contracts, authz, observability, migrations, failure modes, testing, perf/cost, rollout, etc.
2. **Evidence extractor agent**
   - Input: plan artifacts + deltas
   - Output: `coverage_ledger.json` entries:
     - covered? (bool)
     - evidence pointers (section IDs/paths)
     - confidence
     - missing items list
3. **Refine becomes surgical**
   - given missing dimensions, generate minimal additions (not rewrites)
4. **Gate criteria**
  - PASS requires all required dimensions covered or explicitly deferred with impact notes
  - **Diff-first gating**: pass only `coverage_ledger_delta` and unresolved items to gate agents unless full artifacts are explicitly needed
5. **Assumptions / Unknowns Register**
  - gating requires “resolved or explicitly deferred”

### Acceptance criteria

- Every run produces `coverage_ledger.json` + `assumptions.json`.
- Loops terminate because the ledger converges (or a budget cap is hit deterministically).

---

## Phase 4 — Leadership 2.0 (bandit-style guardrails + cold start)

Goal: leadership becomes consistent, cheap, and improves over time.

### Deliverables

- **Leadership config block**:
  - min samples, epsilon schedule, EWMA latency alpha, scoring weights
- **Provider scoring upgrades**:
  - neutral priors + minimum samples
  - EWMA latency (less flapping)
  - down-weight low-sample scores
- **Exploration mode gating**
  - `exploration.mode = none | random | bandit | mc | rl` (never stack accidentally)
- **Constraint-aware selection**
  - filter by local availability, context length, budget caps before scoring
- **Circuit breaker hooks**
  - down-rank after consecutive failures / latency spikes

### Acceptance criteria

- Early runs explore without wasting money/time.
- Later runs converge on stable provider sets per role.

---

## Phase 5 — Bench harness + Monte Carlo trials

Goal: find best model/prompt/param combos with data.

### Deliverables

- `anvil bench` command:
  - curated suite of briefs/tasks
  - sweeps providers/models/params/profiles
  - outputs CSV + summary report
- `--mc-trials K`:
  - short trial phase chooses best config for full run
- Trial tagging/exclusion:
  - trials must not poison long-horizon provider scoring
- Objective function:
  - maximize pass rate + ledger completeness
  - minimize cost, iterations, latency

### Acceptance criteria

- Reproducibly identify “best cheap drafting stack + best gate model”.
- Overnight campaigns yield ranked configurations.

---

## Phase 6 — Reliability & predictability (timeouts, retries, schema guardrails)

Goal: no hangs, no runaway loops, artifacts always valid or fail fast.

### Deliverables

- Per-role `timeout_s`, bounded retries + jitter
- “fallback once” to next best provider when a role fails
- Output guardrails:
  - strict schema validation
  - JSON repair micro-pass
  - length caps + safe truncation
- Streaming (`--stream`) works consistently across providers (local + API)

### Acceptance criteria

- No infinite loops.
- Cost/time bounded by config.
- Structured artifacts parseable or fail fast with clear errors.

---

## Phase 7 — RL / meta-learning (optional; only after the above is solid)

Goal: only pursue RL if it improves the objective without increasing cost-to-pass.

### Deliverables

- RL env and persisted policy (offline bootstrapping from Run Store)
- Policy biases leadership while retaining small epsilon exploration

### Acceptance criteria

- Demonstrated improvement on bench suite with stable cost/latency.
- Can be disabled cleanly (`exploration.mode`).

---

## Phase 8 — Platform upgrades & optional API

Goal: throughput + integration without making CLI secondary.

### Deliverables (optional)

- vLLM/TGI providers for batching/throughput (when local-only isn’t enough)
- Quantization toggles/docs
- Minimal FastAPI server only if needed; CLI remains canonical

---

# Shortest path to value (recommended)

If you only do 3 chunks next, do:

1. **Phase 1 Run Store**
2. **Phase 2A Agent Registry + prompt profiles**
3. **Phase 2B Planning mode MVP (decompose + Plan QA)**

Then add Coverage Ledger gating (Phase 3) once planning artifacts are stable.

---

# Definition of done for “Forge vNext”

A single CLI run produces a durable record (DB row + artifacts) containing:

- `final_plan.json` (or strict Markdown plan + index)
- `coverage_ledger.json`
- `assumptions.json`
- `critique_deltas.json`
- `run_summary.json` (providers, params, cost, timings, iterations, pass/fail)

…and is inspectable and exportable via:

- `anvil runs show <run_id>`
- `anvil runs export <run_id> --format jsonl`
