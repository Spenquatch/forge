from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from .executor import HarnessLangGraphExecutor
from .runner import HarnessError, HarnessRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forge Harness CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a task with a configured mini-harness strategy")
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
        "--json",
        action="store_true",
        help="Print the final summary JSON to stdout instead of a short status line",
    )
    return parser


def _print_summary(summary: dict[str, Any]) -> None:
    verdicts = summary.get("verdicts") or {}
    artifacts = summary.get("artifacts") or {}
    print(f"run_verdict={verdicts.get('run_verdict', summary.get('verdict'))}")
    print(f"content_verdict={verdicts.get('content_verdict')}")
    print(f"validator_verdict={verdicts.get('validator_verdict')}")
    print(f"policy_verdict={verdicts.get('policy_verdict')}")
    print(f"config_verdict={verdicts.get('config_verdict', 'pass')}")
    print(f"run_dir={artifacts.get('run_dir')}")
    print(f"report={artifacts.get('report_md')}")
    print(f"summary={artifacts.get('summary_json')}")
    if artifacts.get("final_artifact"):
        print(f"final_artifact={artifacts.get('final_artifact')}")
    if artifacts.get("final_answer_md"):
        print(f"final_answer={artifacts.get('final_answer_md')}")
    if artifacts.get("partial_answer_md"):
        print(f"partial_answer={artifacts.get('partial_answer_md')}")


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
    )
    summary_payload = state.get("summary_payload")
    if isinstance(summary_payload, dict):
        return summary_payload
    return {
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
            for key, value in dict(state.get("artifact_index") or {}).items()
            if isinstance(value, dict) and value.get("path")
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "run":
        try:
            if args.checkpoint == "memory":
                runner = HarnessRunner(
                    task_path=args.task,
                    strategy_path=args.strategy,
                    workspace=args.workspace,
                    out_root=args.out_root,
                    config_path=args.config,
                    thread_id=args.thread_id,
                    auto_fit_strategy=(args.auto_fit_strategy == "true"),
                )
                summary = runner.run()
            else:
                summary = asyncio.run(_run_with_executor(args))
        except (HarnessError, RuntimeError, ValueError, KeyError) as exc:
            print(f"error={exc}", file=sys.stderr)
            return 2

        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=False))
        else:
            _print_summary(summary)
        return 0

    print(f"Unknown command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
