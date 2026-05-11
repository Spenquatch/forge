#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import traceback
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import anvil.harness.runner as runner_module
from anvil.harness.runner import HarnessRunner
from tests import test_harness_runner as fixtures


@dataclass(frozen=True)
class CaseExpectation:
    run_verdict: str
    decision_state: str
    refinement_status: str | None


@dataclass(frozen=True)
class CaseResult:
    name: str
    run_verdict: str
    decision_state: str
    refinement_status: str | None
    run_dir: Path
    report_path: Path
    summary_path: Path
    focus_refinement: dict[str, Any] | None


_CASE_NAMES = ("applied", "second_success", "exhausted", "ambiguity")
_CASE_EXPECTATIONS = {
    "applied": CaseExpectation(
        run_verdict="accepted",
        decision_state="selected",
        refinement_status="applied",
    ),
    "second_success": CaseExpectation(
        run_verdict="accepted",
        decision_state="selected",
        refinement_status="applied",
    ),
    "exhausted": CaseExpectation(
        run_verdict="no_viable_focus",
        decision_state="no_viable_focus",
        refinement_status="exhausted",
    ),
    "ambiguity": CaseExpectation(
        run_verdict="blocked_for_clarification",
        decision_state="clarification_requested",
        refinement_status=None,
    ),
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministic non-pytest driver for the bounded deliberate seam "
            "refinement runner paths."
        )
    )
    parser.add_argument(
        "--case",
        choices=("all",) + _CASE_NAMES,
        default="all",
        help="Which deterministic scenario to run.",
    )
    parser.add_argument(
        "--out-root",
        default=".forge-harness-runs/manual/focus-gate-refinement-driver",
        help="Directory where per-case run artifacts are written.",
    )
    return parser.parse_args()


@contextmanager
def _patch_attr(obj: object, name: str, replacement: object) -> Iterator[None]:
    original = getattr(obj, name)
    setattr(obj, name, replacement)
    try:
        yield
    finally:
        setattr(obj, name, original)


def _make_refiner_override(
    case_name: str,
    adapter: fixtures._BoundedRefinementFocusGateHarnessAdapter,
) -> Callable[..., tuple[dict[str, Any] | None, str | None]]:
    original_refine = HarnessRunner._refine_selected_focus_from_probe_candidate

    if case_name == "second_success":

        def _fail_first_candidate(
            self: HarnessRunner,
            *,
            focus_decision: dict[str, Any],
            focus_probe: dict[str, Any],
            candidate: dict[str, Any],
        ) -> tuple[dict[str, Any] | None, str | None]:
            if (
                str(candidate.get("canonical_focus_id") or "").strip()
                == adapter.narrowed_primary_id
            ):
                return None, "downstream_bridge_drift"
            return original_refine(
                self,
                focus_decision=focus_decision,
                focus_probe=focus_probe,
                candidate=candidate,
            )

        return _fail_first_candidate

    def _reject_all_candidates(
        self: HarnessRunner,
        *,
        focus_decision: dict[str, Any],
        focus_probe: dict[str, Any],
        candidate: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None]:
        del self, focus_decision, focus_probe
        focus_id = str(candidate.get("canonical_focus_id") or "").strip()
        if focus_id == adapter.narrowed_primary_id:
            return None, "downstream_bridge_drift"
        return None, "canonical_drift"

    return _reject_all_candidates


def _run_case(case_name: str, out_root: Path) -> CaseResult:
    with tempfile.TemporaryDirectory(prefix=f"focus-gate-{case_name}-") as temp_dir:
        temp_root = Path(temp_dir)
        workspace = fixtures._prepare_workspace(temp_root)
        task_path, strategy_path = fixtures._write_task_and_strategy(
            temp_root,
            task_focus_gate=fixtures._task_focus_gate_block(),
            strategy_focus_gate=fixtures._strategy_focus_gate_block(
                default_path="deliberate"
            ),
        )

        if case_name == "ambiguity":
            adapter = fixtures._NeverAskCloseContestHarnessAdapter()
        else:
            adapter = fixtures._BoundedRefinementFocusGateHarnessAdapter()

        refinement_patch: object
        if case_name in {"second_success", "exhausted"}:
            refinement_patch = _make_refiner_override(case_name, adapter)
            refinement_context = _patch_attr(
                HarnessRunner,
                "_refine_selected_focus_from_probe_candidate",
                refinement_patch,
            )
        else:
            refinement_context = nullcontext()

        case_out_root = out_root / case_name
        with (
            _patch_attr(runner_module, "reload_config", lambda path: ({}, {})),
            _patch_attr(runner_module, "get_provider", lambda name: adapter),
            refinement_context,
        ):
            runner = HarnessRunner(
                task_path=task_path,
                strategy_path=strategy_path,
                workspace=workspace,
                out_root=case_out_root,
            )
            summary = runner.run()

    focus_decision = summary["focus_decision"]
    run_details = summary.get("run_details") or {}
    focus_refinement = run_details.get("focus_refinement")
    expectation = _CASE_EXPECTATIONS[case_name]
    actual_refinement_status = None
    if isinstance(focus_refinement, dict):
        actual_refinement_status = str(focus_refinement.get("status") or "").strip() or None

    if summary["verdict"] != expectation.run_verdict:
        raise RuntimeError(
            f"{case_name}: expected verdict {expectation.run_verdict}, "
            f"got {summary['verdict']}."
        )
    actual_decision_state = str(focus_decision.get("decision_state") or "").strip()
    if actual_decision_state != expectation.decision_state:
        raise RuntimeError(
            f"{case_name}: expected decision_state {expectation.decision_state}, "
            f"got {actual_decision_state}."
        )
    if actual_refinement_status != expectation.refinement_status:
        raise RuntimeError(
            f"{case_name}: expected focus_refinement status "
            f"{expectation.refinement_status!r}, got {actual_refinement_status!r}."
        )

    return CaseResult(
        name=case_name,
        run_verdict=str(summary["verdict"]),
        decision_state=actual_decision_state,
        refinement_status=actual_refinement_status,
        run_dir=runner.run_dir,
        report_path=runner.run_dir / "REPORT.md",
        summary_path=runner.run_dir / "summary.json",
        focus_refinement=focus_refinement if isinstance(focus_refinement, dict) else None,
    )


def _print_case_result(result: CaseResult) -> None:
    print(f"case={result.name}")
    print("status=PASS")
    print(f"run_verdict={result.run_verdict}")
    print(f"decision_state={result.decision_state}")
    print(f"focus_refinement_status={result.refinement_status or 'null'}")
    if result.focus_refinement:
        print(
            "focus_refinement="
            + json.dumps(result.focus_refinement, separators=(",", ":"))
        )
    print(f"run_dir={result.run_dir}")
    print(f"report={result.report_path}")
    print(f"summary={result.summary_path}")
    print()


def main() -> int:
    args = _parse_args()
    out_root = Path(args.out_root).expanduser()
    if not out_root.is_absolute():
        out_root = (REPO_ROOT / out_root).resolve(strict=False)

    case_names = list(_CASE_NAMES) if args.case == "all" else [args.case]
    overall_ok = True
    for case_name in case_names:
        try:
            result = _run_case(case_name, out_root)
        except Exception as exc:
            overall_ok = False
            print(f"case={case_name}")
            print("status=FAIL")
            print(f"error={exc}")
            print()
            traceback.print_exc()
            continue
        _print_case_result(result)

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
