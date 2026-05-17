from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Mapping, cast

from .executor import HarnessLangGraphExecutor
from .runner import HarnessError
from .runner import HarnessRunner as _HarnessRunner

HarnessRunner = _HarnessRunner

_SUCCESSFUL_RUN_VERDICTS = {
    "accepted",
    "accepted_with_warnings",
    "accepted_partial",
}
_SUCCESSFUL_PLANNING_TERMINAL_STATUS = "success"
_PLANNING_TERMINAL_STATUSES = {
    "success",
    "clarification_needed",
    "failed",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forge Harness CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser(
        "run", help="Run a task with a configured mini-harness strategy"
    )
    run.add_argument("--task", required=True, help="Path to task YAML/JSON")
    run.add_argument("--strategy", required=True, help="Path to strategy YAML/JSON")
    run.add_argument("--workspace", required=True, help="Target workspace directory")
    run.add_argument(
        "--out-root",
        default=".forge-harness-runs",
        help="Directory that will receive run artifacts",
    )
    run.add_argument(
        "--config",
        default="config/models.yaml",
        help="Path to the Forge provider config file",
    )
    run.add_argument(
        "--thread-id",
        default=None,
        help="Optional stable thread ID to use for checkpointed runs",
    )
    run.add_argument(
        "--checkpoint",
        choices=["memory", "sqlite"],
        default="memory",
        help="Harness checkpoint backend",
    )
    run.add_argument(
        "--auto-fit-strategy",
        choices=["true", "false"],
        default="true",
        help="Auto-fit obviously mismatched task/strategy pairs before model work",
    )
    run.add_argument(
        "--analysis-review-execution-mode",
        choices=["legacy_bridge", "graph_owned"],
        default="legacy_bridge",
        help="Runtime entrypoint for analysis_review strategies",
    )
    run.add_argument(
        "--json",
        action="store_true",
        help="Print the final summary JSON to stdout instead of a short status line",
    )
    return parser


def _print_summary(summary: dict[str, Any]) -> None:
    verdicts = summary.get("verdicts") or {}
    artifacts = summary.get("artifacts") or {}
    if _is_planning_summary(summary):
        print(f"terminal_status={summary.get('terminal_status')}")
        stop_reason = str(summary.get("stop_reason") or "").strip()
        if stop_reason:
            print(f"stop_reason={stop_reason}")
        clarification_requests = summary.get("clarification_requests") or []
        if clarification_requests:
            print(f"clarification_requests={len(clarification_requests)}")
    print(f"run_verdict={verdicts.get('run_verdict', summary.get('verdict'))}")
    print(f"content_verdict={verdicts.get('content_verdict')}")
    print(f"validator_verdict={verdicts.get('validator_verdict')}")
    print(f"policy_verdict={verdicts.get('policy_verdict')}")
    print(f"config_verdict={verdicts.get('config_verdict', 'pass')}")
    print(f"run_dir={artifacts.get('run_dir')}")
    print(f"report={artifacts.get('report_md')}")
    print(f"summary={artifacts.get('summary_json')}")
    if artifacts.get("plan_md"):
        print(f"plan={artifacts.get('plan_md')}")
    if artifacts.get("plan_json"):
        print(f"plan_json={artifacts.get('plan_json')}")
    if artifacts.get("final_artifact"):
        print(f"final_artifact={artifacts.get('final_artifact')}")
    if artifacts.get("final_answer_md"):
        print(f"final_answer={artifacts.get('final_answer_md')}")
    if artifacts.get("partial_answer_md"):
        print(f"partial_answer={artifacts.get('partial_answer_md')}")


def _planning_terminal_status_from_summary(summary: dict[str, Any]) -> str:
    return str(summary.get("terminal_status") or "").strip()


def _is_planning_summary(summary: dict[str, Any]) -> bool:
    if _planning_terminal_status_from_summary(summary) in _PLANNING_TERMINAL_STATUSES:
        return True
    strategy = summary.get("strategy")
    if isinstance(strategy, dict):
        if str(strategy.get("runtime_target") or "").strip() == "planning_v1":
            return True
    strategy_graph_spec = summary.get("strategy_graph_spec")
    if isinstance(strategy_graph_spec, dict):
        return (
            str(strategy_graph_spec.get("runtime_target") or "").strip()
            == "planning_v1"
        )
    return False


def summary_from_state_v1(state: Mapping[str, Any]) -> dict[str, Any]:
    summary_payload = state.get("summary_payload")
    if isinstance(summary_payload, dict):
        return summary_payload
    artifact_map = cast(dict[str, dict[str, Any]], state.get("artifact_index") or {})
    summary = {
        "verdict": state.get("run_verdict"),
        "verdicts": {
            "run_verdict": state.get("run_verdict"),
            "content_verdict": state.get("content_verdict"),
            "validator_verdict": state.get("validator_verdict"),
            "policy_verdict": state.get("policy_verdict"),
            "config_verdict": state.get("config_verdict"),
        },
        "artifacts": {
            key: value.get("path")
            for key, value in artifact_map.items()
            if isinstance(value, dict) and value.get("path")
        },
    }
    planning_terminal_status = str(state.get("planning_terminal_status") or "").strip()
    if planning_terminal_status in _PLANNING_TERMINAL_STATUSES:
        verdicts = cast(dict[str, Any], summary["verdicts"])
        summary["terminal_status"] = planning_terminal_status
        summary["stop_reason"] = str(
            state.get("planning_stop_reason") or state.get("stop_reason") or ""
        ).strip()
        summary["clarification_requests"] = list(
            state.get("clarification_requests") or []
        )
        summary["verdict"] = planning_terminal_status
        verdicts["run_verdict"] = planning_terminal_status
        verdicts["content_verdict"] = planning_terminal_status
    return summary


async def _run_with_executor(args) -> dict[str, Any]:
    executor = HarnessLangGraphExecutor(checkpoint=args.checkpoint)
    state = await executor.execute(
        task_path=args.task,
        strategy_path=args.strategy,
        workspace=args.workspace,
        out_root=args.out_root,
        config_path=args.config,
        thread_id=args.thread_id,
        auto_fit_strategy=(args.auto_fit_strategy == "true"),
        analysis_review_execution_mode=args.analysis_review_execution_mode,
    )
    return summary_from_state_v1(cast(Mapping[str, Any], state))


def _summary_exit_code(summary: dict[str, Any]) -> int:
    terminal_status = _planning_terminal_status_from_summary(summary)
    if terminal_status in _PLANNING_TERMINAL_STATUSES:
        return 0 if terminal_status == _SUCCESSFUL_PLANNING_TERMINAL_STATUS else 1
    verdicts = summary.get("verdicts") or {}
    run_verdict = str(verdicts.get("run_verdict", summary.get("verdict")) or "")
    return 0 if run_verdict in _SUCCESSFUL_RUN_VERDICTS else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "run":
        try:
            summary = asyncio.run(_run_with_executor(args))
        except (
            HarnessError,
            RuntimeError,
            ValueError,
            KeyError,
            FileNotFoundError,
        ) as exc:
            print(f"error={exc}", file=sys.stderr)
            return 2

        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=False))
        else:
            _print_summary(summary)
        return _summary_exit_code(summary)

    print(f"Unknown command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
