# Engineering Charter — Forge

## What this is
This charter defines Forge’s default engineering decision posture for the durable Python CLI and library system in this repository. It sets the default rigor level, allowed shortcuts, and non-negotiables for hardening work so changes stay maintainable, explicit, and reversible without turning every decision into a bespoke debate.

### Assumptions
- This charter applies to the repo’s Python CLI, importable library, orchestration, configuration, and validation/test workflows.
- No domain-specific overrides are currently defined because none were provided in the structured inputs.
- For scalability & performance, the structured level `2` is treated as authoritative over the conflicting prose sentence in the inputs.
- Charter review cadence is assumed to be quarterly, or sooner if Forge’s operational reality changes materially.

## How to use this charter
- **Primary use:** When making engineering choices, pick options that fit the baseline posture + dimension stances below.
- **When unsure:** default to baseline, and log an assumption or open question.
- **When writing Decision Records (ADRs):** map each option to these dimensions/levels and check against red lines.
- **Scope:** applies to the Forge repository’s CLI, library, orchestration, provider integrations, configuration, and test/automation surfaces.
- **Non-goals:** feature behavior specs, product roadmap decisions, and one-off implementation instructions.

---

## Rubric: 1–5 rigor levels
**We use a 1–5 scale across dimensions.** (A higher level means more rigor, safety, and long-term cost—usually slower delivery.)

| Level | Label | Meaning |
|------:|-------|---------|
| 1 | Explore | Reversible exploration or spikes; local-only learning; minimal ceremony. |
| 2 | Lean | Practical internal delivery with basic safeguards and limited blast radius. |
| 3 | Standard | Durable repository default with maintainable code, targeted validation, and explicit tradeoffs. |
| 4 | High Assurance | Stronger contracts, validation, rollout safety, and operational evidence. |
| 5 | Critical | Maximum rigor for safety, security, and reliability critical work; exceptions are rare and explicit. |

### Anti-bikeshedding rules
- **Baseline first:** choose one baseline rigor level for the project; everything inherits it unless overridden.
- **Override only deltas:** only specify overrides where you truly differ from baseline.
- **Whole numbers only:** no half-levels.
- **Use triggers to decide:** “raise the bar when…” and “shortcuts allowed when…” settle adjacent-level debates.
- **If uncertain:** use baseline and record an assumption + revisit trigger.

---

## Project baseline posture
- **Baseline level:** 3 — Standard
- **Rationale (2–4 bullets):**
  - solid coding standards
  - no hacks
  - a single experienced operator with no delivery deadline can afford durable defaults
  - hardening work benefits more from predictable behavior and clean follow-up paths than from raw speed

### Context snapshot
- **Users:** Internal
- **Lifetime:** Months; long enough that cleanup and consistency matter.
- **Runtime environments:** Server and on-prem runs, usually through CLI execution or embedded library use.
- **Stack (expected / unknowns):** Python 3.11+, Poetry-managed package, LangGraph orchestration, model/provider integrations, and pytest/ruff/black/isort/mypy; deployment/SLO shape remains intentionally lightweight.
- **Risk flags:** Secret-bearing provider credentials, model/provider variance, CLI/library contract drift, and regressions in orchestration or harness flows.

### Project classification (planning defaults)
- **Type:** Hardening
    - **Greenfield** — new system; no existing prod users/data; migrations/back-compat usually N/A.
    - **Brownfield** — existing live system/users/data; compatibility and safe rollout often required.
    - **Integration** — new component that must plug into existing systems/contracts; compatibility applies at boundaries.
    - **Modernization** — reshaping/replacing an existing system (refactor/replatform/strangler); migration plan usually required.
    - **Hardening** — stability/security/perf/ops work only; minimal new features; tighten gates.
- **Operational reality:** Not in production today; no prod users or data; the established Python/LangGraph stack is being stabilized before any broader adoption.
- **Default implications (inherit unless overridden by a feature):**
  - **Backward compatibility:** not required by default, but intentional breaking changes that affect shared internal use must be documented.
  - **Migration planning:** not required unless a change introduces persisted state, durable artifacts, or a new external boundary.
  - **Rollout controls (flags/canary/gradual):** none by default; add them only for destructive operations or new shared interfaces.
  - **Deprecation policy:** not required yet; remove dead paths directly when blast radius is truly local and documented.
  - **Observability threshold:** standard visibility for failures, retries, and final outcomes on critical workflows.

---

## Domains / areas (optional overrides)

No standing domain overrides are defined yet. Add one only when a bounded area has meaningfully different trust boundaries, failure modes, or rigor requirements than the project baseline.

### None currently defined
- **What it is:** Placeholder indicating that all current work inherits the project baseline.
- **Touches / trust boundary:** No separate standing trust boundary beyond the overall repository posture.
- **What can go wrong (blast radius):** Ad hoc exceptions can become inconsistent norms if they are not turned into explicit domain overrides.
- **Special constraints:** Create a real domain override only when repeated exceptions or a clearly bounded subsystem justify it.
- **Overrides (if any):**
  - None.
  - Revisit when a subsystem needs a stable higher or lower bar than baseline.

---

## Posture at a glance (quick scan)

| Dimension | Default level (1–5) | Notes / intent |
|---|---:|---|
| Speed vs Quality | 3 | Prefer durable, reviewable changes over hacks. |
| Type safety / static analysis | 3 | Typed core paths and normal lint/type checks on touched code. |
| Testing rigor | 3 | Targeted regression coverage with strong offline coverage for core flows. |
| Scalability & performance | 2 | Keep core paths reasonable; optimize after evidence. |
| Reliability & operability | 3 | Favor deterministic behavior and explicit recovery/failure surfaces. |
| Security & privacy | 3 | Keep secrets, execution boundaries, and trust assumptions explicit. |
| Observability | 3 | Enough telemetry to debug failures and outcomes without excessive noise. |
| Developer experience (DX) | 3 | Maintain predictable local workflows and practical automation. |
| UX polish (or API usability) | 3 | CLI and library interfaces should be clear and unsurprising for repeated internal use. |

---

## Dimensions (details + guardrails)

---

### 1) Speed vs Quality
- **Default stance (level):** 3
- **Default posture statement:** Prefer boring, reviewable, maintainable changes over clever shortcuts; optimize for durable improvement unless the work is explicitly exploratory and kept local.

**Raise the bar when:**
- changes create irreversible migration or trust-boundary cost
- new external interfaces or contracts are introduced
- rollback or recovery would be expensive or unclear

**Allowed shortcuts when:**
- exploration is time-boxed before merge
- iteration is fixture-backed or local-only with explicit follow-up
- the reduced-rigor path is logged as debt or an exception before it becomes shipped behavior

**Non-negotiables / red lines:**
- do not waive speed vs quality expectations on shipped work
- do not hide known risk without recording an exception

**Domain overrides (if any):**
- No standing overrides.

---

### 2) Type safety / static analysis strictness
- **Default stance (level):** 3
- **Default posture statement:** Keep core contracts readable and explicit with normal static checks on touched code, especially around shared state, config, and public interfaces.
- **Tooling assumptions:** Python type hints, Ruff, Black, isort, mypy, and existing repository conventions.

**Raise the bar when:**
- public library APIs, config schemas, or orchestration state shapes change
- provider adapters, persistence, or contract objects become more shared or harder to recover

**Allowed shortcuts when:**
- time-boxed exploration stays isolated before merge
- legacy or third-party boundary code remains partially typed only when runtime validation compensates and follow-up is explicit

**Non-negotiables / red lines:**
- do not waive type safety and static analysis expectations on shipped work
- do not hide known risk without recording an exception

**Domain overrides (if any):**
- No standing overrides.

---

### 3) Testing rigor
- **Default stance (level):** 3
- **Default posture statement:** Ship targeted regression coverage for changed behavior and keep core orchestration paths testable offline.
- **Test pyramid expectation:** Prefer fast unit and offline integration tests in `pytest`; use provider-specific online verification only when credentials are available and that boundary truly changed.

**Raise the bar when:**
- orchestration graph, persistence, policy, or contract logic changes
- new external/provider interfaces or parsing behavior are introduced
- a bug fix needs durable regression protection

**Allowed shortcuts when:**
- time-boxed exploration happens before merge
- optional online provider coverage is deferred when offline coverage plus contract checks sufficiently bound the risk

**Non-negotiables / red lines:**
- do not waive testing rigor expectations on shipped work
- do not hide known risk without recording an exception

**Domain overrides (if any):**
- No standing overrides.

---

### 4) Scalability & performance
- **Default stance (level):** 2
- **Default posture statement:** Prefer simple, readable implementations and measure before optimizing; tune hotspots only when evidence shows a real bottleneck.
- **Performance targets (if any):** CLI setup/list paths should feel immediate; heavier runs should expose progress and bounded cost rather than chase premature micro-optimizations.

**Raise the bar when:**
- a hot path is repeatedly exercised in core CLI or library flows
- added orchestration, provider, or file-system work materially increases latency or cost

**Allowed shortcuts when:**
- a rare admin, migration, or diagnostic path is not performance-sensitive
- optimization is deferred behind a clear measurement or telemetry plan

**Non-negotiables / red lines:**
- do not introduce obviously unbounded or pathological work in core paths without documenting and justifying it

**Domain overrides (if any):**
- No standing overrides.

---

### 5) Reliability & operability
- **Default stance (level):** 3
- **Default posture statement:** Default to deterministic behavior, explicit failure surfaces, and easy recovery for CLI runs and library consumers.
- **Reliability targets (if any):** Predictable command outcomes, inspectable run state/artifacts where applicable, and no silent corruption of workspace or persistence state.

**Raise the bar when:**
- persistence, checkpointing, or artifact-writing behavior changes
- failure recovery is ambiguous or downstream automation depends on the result

**Allowed shortcuts when:**
- low-value convenience paths fail closed with a clear error instead of elaborate recovery
- retry/backoff sophistication waits until there is evidence of instability

**Non-negotiables / red lines:**
- do not waive reliability and operability expectations on shipped work
- do not hide known risk without recording an exception

**Domain overrides (if any):**
- No standing overrides.

---

### 6) Security & privacy
- **Default stance (level):** 3
- **Default posture statement:** Keep credentials, workspace boundaries, and model/provider trust assumptions explicit; prefer least surprise over permissive defaults.
- **Threat model scope:** Repository code, CLI execution, local/on-prem runtime, provider API credentials, workspace reads/writes, and generated artifacts.
- **Data sensitivity:** Internal development data and API secrets; no regulated production user data is assumed today.

**Raise the bar when:**
- secrets handling, networked provider calls, or file-system write boundaries change
- a new external interface, plugin, or automation surface is added
- code may execute or transform untrusted input or artifacts

**Allowed shortcuts when:**
- local-only prototypes avoid hardening layers while handling no real secrets or shared environments
- non-sensitive internal experiments use simpler auth/config flows with explicit expiry or revisit

**Non-negotiables / red lines:**
- do not waive security and privacy expectations on shipped work
- do not hide known risk without recording an exception
- never trust model/provider output as safe to execute or persist without validation

**Domain overrides (if any):**
- No standing overrides.

---

### 7) Observability
- **Default stance (level):** 3
- **Default posture statement:** Expose enough state to debug failures, retries, and outcomes without drowning the operator in noise.
- **Minimum telemetry:** Consistent logs for start/end, critical decisions, failures, retries, and produced artifacts for important workflows.

**Raise the bar when:**
- long-running, multi-step, or partially recoverable flows change
- operator debugging would otherwise depend on reproducing opaque state

**Allowed shortcuts when:**
- local-only experiments use lighter logging when failure analysis remains straightforward
- low-risk helper paths skip detailed metrics until they prove valuable

**Non-negotiables / red lines:**
- do not waive observability expectations on shipped work
- do not hide known risk without recording an exception

**Domain overrides (if any):**
- No standing overrides.

---

### 8) Developer experience (DX) & automation
- **Default stance (level):** 3
- **Default posture statement:** Protect fast local development with predictable commands and automation, but do not overbuild tooling for a one-person team.
- **Automation baseline:** Use Poetry-driven commands and keep formatting, linting, typing, and targeted `pytest` runs as the normal pre-merge validation path for touched surfaces.

**Raise the bar when:**
- repeated manual steps cause drift or avoidable mistakes
- onboarding, routine maintenance, or command discoverability would otherwise be unclear

**Allowed shortcuts when:**
- rare maintenance tasks remain manual if the steps are documented nearby
- lightweight scripts are used before investing in a more polished framework

**Non-negotiables / red lines:**
- do not waive developer tooling and automation expectations on shipped work

**Domain overrides (if any):**
- No standing overrides.

---

### 9) UX polish (or API usability if no UI)
- **Default stance (level):** 3
- **Default posture statement:** CLI and library surfaces should be clear, unsurprising, and easy for an internal operator to debug and script against.
- **Usability targets:** Clear command names/help text, explicit errors, readable library inputs/returns, and stable-enough output semantics for repeated internal use.

**Raise the bar when:**
- adding shared CLI commands, config knobs, or library entrypoints
- ambiguous output or error behavior would slow repeated use or automation

**Allowed shortcuts when:**
- early internal-only commands use simpler ergonomics before interface patterns settle
- cosmetic polish waits when behavior is correct and discoverable

**Non-negotiables / red lines:**
- do not waive ux polish and api usability expectations on shipped work
- do not hide known risk without recording an exception

**Domain overrides (if any):**
- No standing overrides.

---

## Cross-cutting red lines (global non-negotiables)
- No hidden risk: known compromises must be logged as debt, an ADR, or an approved exception.
- No secret leakage, silent permission broadening, or unsafe trust in model/provider output.
- No merged change that makes Forge materially harder to test, debug, or reason about without explicit approval.

---

## Exceptions / overrides process
- **Who can approve:** Spenser
- **Where exceptions are recorded:** .system/charter/CHARTER.md#exceptions
- **Minimum required fields for an exception:**
  - **What:** the exact rule, shortcut, or deviation being approved
  - **Why:** the reason baseline posture is not the right choice here
  - **Scope:** the bounded codepath, component, or time window affected
  - **Risk:** the expected downside plus any mitigation or rollback plan
  - **Expiry / revisit date:** a concrete date or explicit revisit trigger
  - **Owner:** the person accountable for carrying or retiring the exception
- **Default rule:** exceptions are time-boxed; if not renewed, revert to baseline posture.

---

## Debt tracking expectations
- **Where debt is tracked:** the `debt` system
- **What counts as “debt” worth logging:** any intentional shortcut, known validation gap, missing cleanup, or temporary operational workaround that survives the current change.
- **Required fields per debt item:**
  - description of the shortcut or gap
  - owner plus revisit date or trigger
  - paydown trigger, risk, or consequence if left in place
- **Review cadence:** After each new feature is deployed
- **Paydown trigger(s):** when touching the same area again, before broadening usage or trust boundaries, after regressions/incidents, and at the stated review cadence.

---

## Decision Records (ADRs): how to use this charter
- **Decision record format:** json
- **Decision record location:** decisions
- When evaluating options, explicitly map each option to:
  - impacted dimensions
  - expected level (1–5) per impacted dimension
  - conflicts with any red lines
- Always include at least:
  - **Fast path** option (optimize speed / lower rigor where allowed)
  - **Robust path** option (optimize reliability/security/maintainability)
  - **Balanced** option (default unless project says otherwise)
- The chosen decision must state **why it matches this charter**, or link to an approved exception.

---

## Review & updates
- **Review cadence:** Quarterly, and sooner if Forge’s operational reality changes.
- **Update triggers:** production launch; new external users, data, or contracts; introduction of persisted state or stronger compatibility promises; new runtime or deployment environments; team growth beyond a single operator; or repeated exceptions that indicate the baseline is wrong.