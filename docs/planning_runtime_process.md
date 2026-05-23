# Planning Runtime Process

This document explains what the current `planning` harness runtime actually
does today.

It is a bounded, deterministic repository-planning engine. Its canonical owner
is still the deterministic layer that inspects local workspace evidence and
emits a structured planning package. That package is the bounded canonical
first pass, not an automatic claim of full closure across every cited surface.
When
`planning_execution.mode: graph_owned_with_planner_review` is selected, the
runtime adds one bounded provider-backed review stage after deterministic
structure derivation; that review may annotate or challenge the package, but it
does not replace seams, workstreams, slices, coverage truth, or stop reasons.

Primary implementation entrypoints:

- `anvil/harness/subgraphs/planning_v1.py`
- `anvil/harness/planning_runtime.py`
- `anvil/harness/strategy_graph.py`

## Overview

At a high level, the planner:

1. Resolves `files_hint` and other repo cues into concrete workspace paths.
2. Scans a bounded set of files and candidate matches.
3. Chooses a primary cut, or center-of-gravity area, for the feature.
4. Decomposes that cut into architectural seams.
5. Translates seams into workstreams.
6. Translates workstreams into executable slices with acceptance criteria.
7. Emits deterministic first-pass coverage, assumptions, and truthful stop reasons.
8. Optionally runs bounded planner review over the finished package and records expansion delta separately.

## Resolution 1: One-Screen Flow

```mermaid
flowchart LR
    A["Task + strategy input"] --> B["Resolve files_hint and repo cues"]
    B --> C["Bounded workspace scan"]
    C --> D["Choose primary cut"]
    D --> E["Decompose into seams"]
    E --> F["Build workstreams"]
    F --> G["Emit executable slices"]
    G --> H["Write planning package"]
```

## Resolution 2: Phase-Level Runtime

This view maps the runtime to the four planning phases exposed by
`planning_v1`.

```mermaid
flowchart TD
    A["Prepare planning state"] --> B["Design doc phase"]
    B --> B1["Resolve files_hint"]
    B1 --> B2["Collect bounded repo evidence"]
    B2 --> B3["Choose credible primary cut"]

    B3 --> C["Seam decomposition phase"]
    C --> C1["Group evidence by architectural surface"]
    C1 --> C2["Emit seam records"]

    C2 --> D["Parallel planning phase"]
    D --> D1["Translate seams into workstreams"]
    D1 --> D2["Attach dependency reasoning"]

    D2 --> E["Slice emission phase"]
    E --> E1["Emit executable slices"]
    E1 --> E2["Attach acceptance criteria"]

    E2 --> F["Coverage and reporting"]
    F --> F1["coverage_ledger"]
    F --> F2["assumptions_register"]
    F --> F3["uncovered_delta"]
    F --> F4["provider_review_delta"]
    F --> F5["terminal_status and stop_reason"]
```

## Resolution 3: Decision and Stop Paths

This view shows why some planning runs return quickly.

```mermaid
flowchart TD
    A["Start planning run"] --> B{"files_hint resolves?"}
    B -- "No" --> C["clarification_needed<br/>stop_reason: files_hint_unresolved"]
    B -- "Yes" --> D{"Objective in bounded planning corpus?"}
    D -- "No" --> E["failed<br/>stop_reason: planning_request_out_of_corpus"]
    D -- "Yes" --> F["Bounded repo scan and primary-cut selection"]
    F --> G{"Credible cut found?"}
    G -- "No" --> H["clarification_needed or failed"]
    G -- "Yes" --> I["Emit seams, workstreams, and slices"]
    I --> J["success"]
```

## Resolution 4: Artifact Shape

The output is a planning package, not model-generated prose. It keeps
deterministic first-pass truth separate from provider-review expansion
findings.

```mermaid
flowchart TD
    A["Planning runtime output"] --> B["plan.json"]
    A --> C["PLAN.md"]
    A --> D["summary.json"]

    B --> B1["seams"]
    B --> B2["workstreams"]
    B --> B3["slices"]
    B --> B4["phase_results"]
    B --> B5["coverage_ledger"]
    B --> B6["assumptions_register"]
    B --> B7["uncovered_delta"]
    B --> B8["provider_review_delta"]

    C --> C1["Human-readable plan narrative"]
    C --> C2["Repo evidence grounding"]
    C --> C3["Execution slices and acceptance criteria"]

    D --> D1["terminal_status"]
    D --> D2["stop_reason"]
    D --> D3["run_mode"]
    D --> D4["artifact paths"]
```

## What Each Step Computes

### 1. Resolve `files_hint` and repo cues

The runtime starts from task inputs such as `files_hint`, objective text, and
workspace state. It converts those hints into concrete repository paths that it
can inspect within a bounded budget.

### 2. Scan a bounded set of files and matches

The planner does not crawl the entire repository without limits. It uses a
bounded discovery pass and a bounded file-inspection pass so planning remains
deterministic and truthful.

### 3. Choose a primary cut

From the bounded evidence, the runtime selects the most credible
center-of-gravity surface for the requested feature. This becomes the primary
cut used to anchor the plan.

### 4. Decompose into architectural seams

The runtime groups the evidence into architectural seams. A seam is a bounded
surface that can be reasoned about independently enough to support execution
planning.

### 5. Turn seams into workstreams

Each seam becomes a workstream with dependency reasoning. This is where the
planner decides which work can be parallelized and which work should be
sequenced.

### 6. Turn workstreams into executable slices

Each workstream is translated into one or more slices with concrete acceptance
criteria. These slices are intended to be the next actionable units of work.

### 7. Emit deterministic first-pass coverage, assumptions, and stop reasons

The runtime records what dimensions it believes are covered, what assumptions
remain, and why it stopped. That is why the package includes machine-readable
coverage and terminal metadata rather than only freeform narrative.

This deterministic first pass can still leave cited surfaces under-planned or
evidence-only. That possibility is part of the honesty contract, not a reason
to flatten the final story into full closure.

### 8. Emit provider-review expansion delta without replacing deterministic ownership

When planner review runs, it reports structured expansion or clarification
delta in `provider_review_delta`. That delta can cite uncovered or
under-planned surfaces, but it does not rewrite canonical seam, workstream, or
slice IDs.

## Key Output Fields

The most important planning-package fields are:

- `seams`: the bounded architectural surfaces selected by the runtime
- `workstreams`: execution-oriented groupings derived from the seams
- `slices`: the next executable units of work with acceptance criteria
- `phase_results`: per-phase success or stop summaries
- `coverage_ledger`: structured evidence of what the deterministic first pass covered
- `uncovered_delta`: deterministic first-pass uncovered or assumption-blocked dimensions
- `provider_review_delta`: provider-identified expansion or clarification findings layered on top of the deterministic package
- `PLAN.md`: human-readable plan artifact
- `plan.json`: machine-readable plan artifact

## Practical Summary

The current `planning` kind is best understood as:

- a supported harness/runtime kind
- a deterministic repo-planning engine whose public artifact truth is a bounded canonical first pass
- a producer of structured planning artifacts
- not a provider-backed planner loop

If a planning run returns quickly, that usually means the bounded planner
either:

- grounded itself fast and emitted a complete planning package, or
- stopped early with a truthful clarification or failure outcome
