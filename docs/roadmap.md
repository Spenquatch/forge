# Roadmap

Forge is moving toward a planning refinery that can generate, measure, patch, and gate work with durable evidence. The active repo surfaces today are the analysis-review harness and the leadership/orchestration foundation that powers configurable multi-role runs.

Two cross-cutting investments shape the roadmap:

- durable run records so each loop can explain what happened, what it cost, and why it stopped
- explicit coverage evidence so "nothing important was missed" becomes a mechanical gate instead of a judgment call

## Current focus

### Stabilize the current execution surface

- keep the CLI fast and predictable
- make provider initialization lazy by default
- enforce shared budget and stop-condition handling across roles
- keep offline smoke coverage deterministic
- keep the bounded public `C3` strategy surface honest: parser-owned
  enforcement, explicit compatibility warnings for `analysis_review_v1`, and
  docs/example taxonomy that match live behavior without promoting
  fixture-backed internal strategies to canonical public authoring

### Add durable run visibility

- ship a Run Store that records runs, spans, provider choices, timings, and artifact pointers
- make run data inspectable through `anvil runs` commands
- keep schema versions explicit for config, artifacts, and storage

### Move agent behavior into configuration

- define agent contracts, prompt profiles, model policy, validation, and repair strategy in config
- keep orchestration code small by running configured micro-agents inside a limited node set

### Deliver planning mode and measurable coverage

- add a decomposition-first planning artifact with stable IDs
- gate plans with structured deltas instead of loose prose review
- produce a coverage ledger and assumptions register for deterministic refine loops

## Future directions

### Leadership optimization

- upgrade leadership selection with bounded exploration, neutral priors, and circuit-breaker behavior
- make provider choice constraint-aware instead of purely preference-based

### Evaluation and search

- build a bench harness for repeatable task suites
- add Monte Carlo trial selection for prompt, model, and parameter sweeps

### Reliability hardening

- enforce per-role timeouts, bounded retries, and output guardrails
- keep artifacts either valid and parseable or clearly failed

### Optional long-horizon work

- explore RL and meta-learning only after the measurable foundations are stable
- add optional throughput and API surfaces without making the CLI secondary
