from __future__ import annotations

"""Internal strategy graph vocabulary for harness metadata selection."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .types import (
    ANALYSIS_REVIEW_LEGACY_KIND,
    ANALYSIS_REVIEW_TRUST_KIND,
    PLANNING_RUNTIME_TARGET,
    StrategyConfig,
    infer_runtime_target_for_strategy_kind,
    is_analysis_review_strategy_kind,
)

STRATEGY_GRAPH_SCHEMA_VERSION = "strategy_graph_spec_v1"
STRATEGY_GRAPH_SUBSET = "bounded_strategy_graph_v1"


@dataclass(frozen=True)
class StageSpec:
    stage_id: str
    role_name: str
    capabilities: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "role_name": self.role_name,
            "capabilities": list(self.capabilities),
        }


@dataclass(frozen=True)
class LinearEdgeSpec:
    from_stage_id: str
    to_stage_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "from_stage_id": self.from_stage_id,
            "to_stage_id": self.to_stage_id,
        }


@dataclass(frozen=True)
class LoopSpec:
    loop_id: str
    kind: str
    from_stage_id: str
    to_stage_id: str
    min_iterations: int
    max_iterations: int
    continue_when: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "kind": self.kind,
            "from_stage_id": self.from_stage_id,
            "to_stage_id": self.to_stage_id,
            "min_iterations": self.min_iterations,
            "max_iterations": self.max_iterations,
            "continue_when": self.continue_when,
        }


@dataclass(frozen=True)
class BranchPathSpec:
    path_id: str
    condition_value: str
    target_stage_id: str | None = None
    terminal_outcome_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "condition_value": self.condition_value,
            "target_stage_id": self.target_stage_id,
            "terminal_outcome_id": self.terminal_outcome_id,
        }


@dataclass(frozen=True)
class ConditionalBranchSpec:
    branch_id: str
    stage_id: str
    condition_key: str
    paths: tuple[BranchPathSpec, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "stage_id": self.stage_id,
            "condition_key": self.condition_key,
            "paths": [path.to_dict() for path in self.paths],
        }


@dataclass(frozen=True)
class TerminalOutcomeSpec:
    outcome_id: str
    summary: str

    def to_dict(self) -> dict[str, str]:
        return {
            "outcome_id": self.outcome_id,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class PlanningPhaseSpec:
    phase_id: str
    stage_type: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.phase_id,
            "stage_type": self.stage_type,
        }


@dataclass(frozen=True)
class StrategyGraphSpec:
    spec_id: str
    strategy_kind: str
    runtime_target: str
    stages: tuple[StageSpec, ...]
    phases: tuple[PlanningPhaseSpec, ...] = ()
    linear_edges: tuple[LinearEdgeSpec, ...] = ()
    loops: tuple[LoopSpec, ...] = ()
    conditional_branches: tuple[ConditionalBranchSpec, ...] = ()
    terminal_outcomes: tuple[TerminalOutcomeSpec, ...] = ()
    post_runtime_action: str = "select_best_draft"
    schema_version: str = STRATEGY_GRAPH_SCHEMA_VERSION
    subset: str = STRATEGY_GRAPH_SUBSET

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "spec_id": self.spec_id,
            "subset": self.subset,
            "strategy_kind": self.strategy_kind,
            "runtime_target": self.runtime_target,
            "stages": [stage.to_dict() for stage in self.stages],
            "phases": [phase.to_dict() for phase in self.phases],
            "linear_edges": [edge.to_dict() for edge in self.linear_edges],
            "loops": [loop.to_dict() for loop in self.loops],
            "conditional_branches": [
                branch.to_dict() for branch in self.conditional_branches
            ],
            "terminal_outcomes": [
                outcome.to_dict() for outcome in self.terminal_outcomes
            ],
            "post_runtime_action": self.post_runtime_action,
        }


def route_after_strategy_selection(state: Mapping[str, Any]) -> str:
    if str(state.get("config_verdict") or "pass") == "invalid_config":
        return "write_artifacts"
    runtime_target = _runtime_target_from_state(state)
    if runtime_target in {
        "single_pass",
        "pfr_v1",
        "analysis_review_v1",
        PLANNING_RUNTIME_TARGET,
    }:
        return runtime_target
    return "write_artifacts"


def build_strategy_graph_spec(
    strategy_kind: str, strategy_spec: Mapping[str, Any] | None = None
) -> StrategyGraphSpec:
    strategy_kind = _normalize_strategy_kind(strategy_kind)
    strategy_spec = strategy_spec or {}
    runtime_target = str(
        strategy_spec.get("runtime_target")
        or infer_runtime_target_for_strategy_kind(strategy_kind)
        or ""
    ).strip()
    if runtime_target == PLANNING_RUNTIME_TARGET:
        return _build_planning_spec(strategy_kind, strategy_spec)
    if strategy_kind == "single_pass":
        return _build_single_pass_spec()
    if strategy_kind == "pfr_v1":
        return _build_pfr_spec(strategy_spec)
    if is_analysis_review_strategy_kind(strategy_kind):
        return _build_analysis_review_spec(strategy_kind, strategy_spec)
    return _build_unsupported_spec(strategy_kind)


def _normalize_strategy_kind(strategy_kind: str) -> str:
    normalized = str(strategy_kind or "single_pass").strip() or "single_pass"
    if normalized == ANALYSIS_REVIEW_LEGACY_KIND:
        return "analysis_review_bounded_v1"
    return normalized


def _runtime_target_from_state(state: Mapping[str, Any]) -> str:
    graph_spec = state.get("strategy_graph_spec")
    if isinstance(graph_spec, Mapping):
        runtime_target = str(graph_spec.get("runtime_target") or "").strip()
        if runtime_target:
            return runtime_target
    strategy_spec = state.get("strategy_spec")
    if isinstance(strategy_spec, Mapping):
        runtime_target = str(strategy_spec.get("runtime_target") or "").strip()
        if runtime_target:
            return runtime_target
    return str(
        infer_runtime_target_for_strategy_kind(str(state.get("strategy_kind") or ""))
        or ""
    ).strip()


def _build_single_pass_spec() -> StrategyGraphSpec:
    return StrategyGraphSpec(
        spec_id="single_pass.direct",
        strategy_kind="single_pass",
        runtime_target="single_pass",
        stages=(
            StageSpec(
                stage_id="solver",
                role_name="solver",
                capabilities=("produce_solution",),
            ),
        ),
        terminal_outcomes=(
            TerminalOutcomeSpec(
                outcome_id="solution_complete",
                summary="Single-pass execution returns one candidate solution.",
            ),
        ),
    )


def _build_pfr_spec(strategy_spec: Mapping[str, Any]) -> StrategyGraphSpec:
    max_repair_loops = int(strategy_spec.get("max_repair_loops", 1) or 0)
    rerun_falsifier = bool(strategy_spec.get("rerun_falsifier_after_patch", True))
    patch_on_inconclusive = bool(strategy_spec.get("patch_on_inconclusive", False))
    spec_id = (
        "pfr_v1"
        f".repair_{max_repair_loops}"
        f".rerun_{int(rerun_falsifier)}"
        f".patch_inconclusive_{int(patch_on_inconclusive)}"
    )
    return StrategyGraphSpec(
        spec_id=spec_id,
        strategy_kind="pfr_v1",
        runtime_target="pfr_v1",
        stages=(
            StageSpec(
                stage_id="proposer",
                role_name="proposer",
                capabilities=("produce_solution",),
            ),
            StageSpec(
                stage_id="falsifier",
                role_name="falsifier",
                capabilities=("review_solution", "issue_verdict"),
            ),
            StageSpec(
                stage_id="patcher",
                role_name="patcher",
                capabilities=("repair_solution",),
            ),
        ),
        linear_edges=(
            (
                LinearEdgeSpec("proposer", "falsifier"),
                LinearEdgeSpec("patcher", "falsifier"),
            )
            if rerun_falsifier
            else (LinearEdgeSpec("proposer", "falsifier"),)
        ),
        loops=(
            (
                LoopSpec(
                    loop_id="pfr_repair_loop",
                    kind="single_back_edge",
                    from_stage_id="patcher",
                    to_stage_id="falsifier",
                    min_iterations=0,
                    max_iterations=max_repair_loops,
                    continue_when="falsifier_or_validator_requests_patch",
                ),
            )
            if rerun_falsifier and max_repair_loops > 0
            else ()
        ),
        conditional_branches=(
            ConditionalBranchSpec(
                branch_id="falsifier_verdict",
                stage_id="falsifier",
                condition_key="repair_decision",
                paths=(
                    BranchPathSpec(
                        path_id="accept",
                        condition_value="accept",
                        terminal_outcome_id="solution_accepted",
                    ),
                    BranchPathSpec(
                        path_id="repair",
                        condition_value="repair",
                        target_stage_id="patcher",
                    ),
                    BranchPathSpec(
                        path_id="manual_review",
                        condition_value="manual_review",
                        terminal_outcome_id="solution_needs_manual_review",
                    ),
                ),
            ),
        ),
        terminal_outcomes=(
            TerminalOutcomeSpec(
                outcome_id="solution_accepted",
                summary="P/F/R completes with an accepted solution.",
            ),
            TerminalOutcomeSpec(
                outcome_id="solution_needs_manual_review",
                summary="P/F/R exits without a clean falsifier acceptance.",
            ),
        ),
    )


def _build_analysis_review_spec(
    strategy_kind: str, strategy_spec: Mapping[str, Any]
) -> StrategyGraphSpec:
    focus_gate = _focus_gate_config(strategy_spec)
    review_loops = _review_loops_config(strategy_spec)
    trust_review = _trust_review_config(strategy_spec)
    focus_gate_enabled = bool(focus_gate.get("enabled"))
    default_path = str(focus_gate.get("default_path") or "adjudicate")
    max_loops = max(
        int(review_loops.get("max_loops", 0) or 0),
        int(review_loops.get("min_loops", 0) or 0),
        1 if bool(review_loops.get("always_run_first_revision")) else 0,
    )
    runtime_target = "analysis_review_v1"
    execution_mode = str(trust_review.get("execution_mode") or "legacy_full_review")
    spec_id_parts = [strategy_kind]
    spec_id_parts.append(
        f"focus_gate_{default_path}" if focus_gate_enabled else "focus_gate_off"
    )
    spec_id_parts.append(
        f"loops_{int(review_loops.get('min_loops', 0) or 0)}_{max_loops}"
    )
    if strategy_kind == ANALYSIS_REVIEW_TRUST_KIND:
        spec_id_parts.append(f"trust_{execution_mode}")

    stages = []
    if focus_gate_enabled:
        stages.append(
            StageSpec(
                stage_id="focus_gate",
                role_name="focus_gate",
                capabilities=("select_focus",),
            )
        )
    stages.extend(
        [
            StageSpec(
                stage_id="proposer",
                role_name="proposer",
                capabilities=("produce_analysis",),
            ),
            StageSpec(
                stage_id="critic",
                role_name="critic",
                capabilities=("review_analysis", "open_issues"),
            ),
            StageSpec(
                stage_id="reviser",
                role_name="reviser",
                capabilities=("revise_analysis", "address_issues"),
            ),
            StageSpec(
                stage_id="auditor",
                role_name="auditor",
                capabilities=("review_analysis", "close_or_carry_issues"),
            ),
        ]
    )
    if (
        strategy_kind == ANALYSIS_REVIEW_TRUST_KIND
        and execution_mode == "attestation_over_bounded"
    ):
        stages.append(
            StageSpec(
                stage_id="attestation_auditor",
                role_name="auditor",
                capabilities=("attest_bounded_review",),
            )
        )

    branches = []
    if focus_gate_enabled:
        branches.append(
            ConditionalBranchSpec(
                branch_id="focus_gate_decision",
                stage_id="focus_gate",
                condition_key="decision_state",
                paths=(
                    BranchPathSpec(
                        path_id="selected",
                        condition_value="selected",
                        target_stage_id="proposer",
                    ),
                    BranchPathSpec(
                        path_id="blocked",
                        condition_value="blocked",
                        terminal_outcome_id="focus_gate_blocked",
                    ),
                    BranchPathSpec(
                        path_id="no_viable_focus",
                        condition_value="no_viable_focus",
                        terminal_outcome_id="focus_gate_no_viable_focus",
                    ),
                ),
            )
        )

    review_exit_target_stage = (
        "attestation_auditor"
        if (
            strategy_kind == ANALYSIS_REVIEW_TRUST_KIND
            and execution_mode == "attestation_over_bounded"
        )
        else None
    )
    review_exit_terminal = (
        None if review_exit_target_stage is not None else "analysis_review_complete"
    )
    branches.extend(
        [
            ConditionalBranchSpec(
                branch_id="critic_revision_gate",
                stage_id="critic",
                condition_key="revision_required",
                paths=(
                    BranchPathSpec(
                        path_id="revise",
                        condition_value="true",
                        target_stage_id="reviser",
                    ),
                    BranchPathSpec(
                        path_id="complete",
                        condition_value="false",
                        target_stage_id=review_exit_target_stage,
                        terminal_outcome_id=review_exit_terminal,
                    ),
                ),
            ),
            ConditionalBranchSpec(
                branch_id="auditor_revision_gate",
                stage_id="auditor",
                condition_key="revision_required",
                paths=(
                    BranchPathSpec(
                        path_id="revise",
                        condition_value="true",
                        target_stage_id="reviser",
                    ),
                    BranchPathSpec(
                        path_id="complete",
                        condition_value="false",
                        target_stage_id=review_exit_target_stage,
                        terminal_outcome_id=review_exit_terminal,
                    ),
                ),
            ),
        ]
    )

    terminal_outcomes = [
        TerminalOutcomeSpec(
            outcome_id="analysis_review_complete",
            summary="Analysis-review execution returns a final analysis payload.",
        )
    ]
    if focus_gate_enabled:
        terminal_outcomes.extend(
            [
                TerminalOutcomeSpec(
                    outcome_id="focus_gate_blocked",
                    summary="Focus gating blocks execution pending clarification.",
                ),
                TerminalOutcomeSpec(
                    outcome_id="focus_gate_no_viable_focus",
                    summary="Focus gating exits without a viable focus candidate.",
                ),
            ]
        )
    if review_exit_target_stage is not None:
        branches.append(
            ConditionalBranchSpec(
                branch_id="attestation_finalize",
                stage_id="attestation_auditor",
                condition_key="completion",
                paths=(
                    BranchPathSpec(
                        path_id="complete",
                        condition_value="done",
                        terminal_outcome_id="trust_attestation_complete",
                    ),
                ),
            )
        )
        terminal_outcomes.append(
            TerminalOutcomeSpec(
                outcome_id="trust_attestation_complete",
                summary="Trust attestation completes after bounded review converges.",
            )
        )

    linear_edges = [
        LinearEdgeSpec("proposer", "critic"),
        LinearEdgeSpec("reviser", "auditor"),
    ]

    return StrategyGraphSpec(
        spec_id=".".join(spec_id_parts),
        strategy_kind=strategy_kind,
        runtime_target=runtime_target,
        stages=tuple(stages),
        linear_edges=tuple(linear_edges),
        loops=(
            LoopSpec(
                loop_id="analysis_review_revision_loop",
                kind="single_back_edge",
                from_stage_id="auditor",
                to_stage_id="reviser",
                min_iterations=int(review_loops.get("min_loops", 0) or 0),
                max_iterations=max_loops,
                continue_when="review_requests_revision",
            ),
        ),
        conditional_branches=tuple(branches),
        terminal_outcomes=tuple(terminal_outcomes),
    )


def _build_planning_spec(
    strategy_kind: str, strategy_spec: Mapping[str, Any]
) -> StrategyGraphSpec:
    parsed_strategy = StrategyConfig.from_dict(
        {"kind": strategy_kind, **dict(strategy_spec)}
    )
    phases = tuple(
        PlanningPhaseSpec(phase_id=phase.id, stage_type=phase.stage_type)
        for phase in parsed_strategy.phases
    )
    return StrategyGraphSpec(
        spec_id=f"{strategy_kind}.{PLANNING_RUNTIME_TARGET}",
        strategy_kind=strategy_kind,
        runtime_target=PLANNING_RUNTIME_TARGET,
        stages=tuple(
            StageSpec(
                stage_id=phase.phase_id,
                role_name="planner",
                capabilities=(phase.stage_type,),
            )
            for phase in phases
        ),
        phases=phases,
        linear_edges=tuple(
            LinearEdgeSpec(phases[index].phase_id, phases[index + 1].phase_id)
            for index in range(len(phases) - 1)
        ),
        terminal_outcomes=(
            TerminalOutcomeSpec(
                outcome_id="planning_success",
                summary="Planning runtime emitted a deterministic planning package.",
            ),
            TerminalOutcomeSpec(
                outcome_id="planning_clarification_needed",
                summary="Planning runtime stopped with clarification requests.",
            ),
            TerminalOutcomeSpec(
                outcome_id="planning_failed",
                summary="Planning runtime stopped with a failure.",
            ),
        ),
        post_runtime_action="write_artifacts",
    )


def _build_unsupported_spec(strategy_kind: str) -> StrategyGraphSpec:
    return StrategyGraphSpec(
        spec_id=f"unsupported.{strategy_kind}",
        strategy_kind=strategy_kind,
        runtime_target="write_artifacts",
        terminal_outcomes=(
            TerminalOutcomeSpec(
                outcome_id="unsupported_strategy",
                summary="Unsupported strategy kinds fall back to write_artifacts.",
            ),
        ),
        stages=(),
    )


def _focus_gate_config(strategy_spec: Mapping[str, Any]) -> Mapping[str, Any]:
    focus_gate = strategy_spec.get("focus_gate")
    if isinstance(focus_gate, Mapping):
        return focus_gate
    return {}


def _review_loops_config(strategy_spec: Mapping[str, Any]) -> Mapping[str, Any]:
    review_loops = strategy_spec.get("review_loops")
    if isinstance(review_loops, Mapping):
        return review_loops
    return {}


def _trust_review_config(strategy_spec: Mapping[str, Any]) -> Mapping[str, Any]:
    trust_review = strategy_spec.get("trust_review")
    if isinstance(trust_review, Mapping):
        return trust_review
    return {}
