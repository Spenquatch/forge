from __future__ import annotations

"""Artifact and reporting helpers for the LangGraph-backed harness surface."""

import copy
import json
from pathlib import Path
from typing import Any

from .files import write_json, write_text
from .report import render_report
from .selection import select_best_draft

_FULLY_ACCEPTED_RUN_VERDICTS = {"accepted", "accepted_with_warnings"}
_PARTIAL_ACCEPTED_RUN_VERDICTS = {"accepted_partial"}


def artifact_ref(path: str | Path, *, kind: str, description: str) -> dict[str, str]:
    return {
        "kind": kind,
        "path": str(path),
        "description": description,
    }


def ensure_run_dir(run_dir: str | Path) -> Path:
    path = Path(run_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _accepted_recommendation_indices(summary: dict[str, Any]) -> list[int]:
    reviews = summary.get("recommendation_reviews") or []
    indices: list[int] = []
    for item in reviews:
        if not isinstance(item, dict):
            continue
        verdict = str(item.get("verdict") or "").strip().lower()
        if verdict not in {"accept", "accept_with_caveat"}:
            continue
        try:
            indices.append(int(item.get("recommendation_index")))
        except (TypeError, ValueError):
            continue
    return sorted(set(indices))


def _render_analysis_section(lines: list[str], title: str, section: Any) -> None:
    if not isinstance(section, dict):
        return
    items = [str(item).strip() for item in section.get("items", []) if str(item).strip()]
    none_reason = str(section.get("none_reason") or "").strip()
    if not items and not none_reason:
        return
    lines.extend([f"## {title}", ""])
    if items:
        for item in items:
            lines.append(f"- {item}")
    if none_reason:
        lines.append(f"- none_reason: {none_reason}")
    lines.append("")


def build_partial_answer_payload(summary: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not payload:
        return None
    recommendation_indices = _accepted_recommendation_indices(summary)
    recommendations = payload.get("recommendations")
    if not isinstance(recommendations, list) or not recommendations or not recommendation_indices:
        return None
    selected_recommendations = [
        copy.deepcopy(item)
        for index, item in enumerate(recommendations, start=1)
        if index in recommendation_indices and isinstance(item, dict)
    ]
    if not selected_recommendations:
        return None
    excluded_indices = [
        index for index in range(1, len(recommendations) + 1) if index not in recommendation_indices
    ]
    partial_payload = copy.deepcopy(payload)
    partial_payload["summary"] = (
        str(payload.get("summary") or "").strip()
        + (
            f"\n\nPartial acceptance: recommendations {', '.join(str(i) for i in recommendation_indices)} "
            f"are included; recommendations {', '.join(str(i) for i in excluded_indices) or 'none'} were excluded."
        )
    ).strip()
    partial_payload["recommendations"] = selected_recommendations
    partial_payload["included_recommendation_indices"] = recommendation_indices
    partial_payload["excluded_recommendation_indices"] = excluded_indices
    partial_payload["recommendation_reviews"] = copy.deepcopy(summary.get("recommendation_reviews") or [])
    partial_payload["caveats"] = [
        f"This is a partial answer. Excluded recommendations: {', '.join(str(i) for i in excluded_indices) or 'none'}."
    ]
    return partial_payload


def _augment_best_draft_payload(best_draft: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    enriched = copy.deepcopy(payload)
    caveats = [str(item) for item in enriched.get("caveats", []) if str(item).strip()]
    review_state = str(best_draft.get("review_state") or "not_evaluated")
    metadata = best_draft.get("metadata") or {}
    if review_state != "evaluated":
        failure_kind = str(metadata.get("review_failure_kind") or "").strip()
        failure_summary = str(metadata.get("review_failure_summary") or "").strip()
        message = "This draft was not evaluated by a successful critic/auditor stage."
        if failure_kind or failure_summary:
            detail = failure_summary or failure_kind.replace("_", " ")
            message = f"{message} Latest review attempt: {detail}."
        caveats.append(message)
    if caveats:
        enriched["caveats"] = caveats
    return enriched


def render_deliverable_markdown(
    task_id: str,
    payload: dict[str, Any],
    *,
    artifact_label: str,
    accepted: bool,
) -> str:
    lines: list[str] = [f"# {artifact_label}: {task_id}", ""]
    if not accepted:
        lines.extend(
            [
                "> [!WARNING]",
                "> This run did not reach a fully accepted verdict. This file may contain a best-effort or partial deliverable.",
                "",
            ]
        )

    summary_text = str(payload.get("summary", "") or "").strip()
    if summary_text:
        lines.extend(["## Summary", "", summary_text, ""])

    caveats = payload.get("caveats")
    if isinstance(caveats, list) and caveats:
        lines.append("## Caveats")
        lines.append("")
        for item in caveats:
            lines.append(f"- {item}")
        lines.append("")

    _render_analysis_section(lines, "Strengths", payload.get("strengths"))
    _render_analysis_section(lines, "Uncertainties", payload.get("uncertainties"))

    files_reviewed = payload.get("files_reviewed")
    if isinstance(files_reviewed, list) and files_reviewed:
        lines.extend(["## Files Reviewed", ""])
        for item in files_reviewed:
            if str(item).strip():
                lines.append(f"- {item}")
        lines.append("")

    recommendations = payload.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        lines.extend(["## Recommendations", ""])
        for index, item in enumerate(recommendations, start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or f"Recommendation {index}")
            classification = str(item.get("classification") or "").strip()
            priority = str(item.get("priority") or "").strip()
            header_parts = [title]
            meta = ", ".join(bit for bit in (classification, priority) if bit)
            if meta:
                header_parts.append(f"({meta})")
            lines.append(f"### {index}. {' '.join(header_parts)}")
            lines.append("")
            for field_name, label in (
                ("rationale", "Rationale"),
                ("proposed_change", "Suggested change"),
                ("suggested_change", "Suggested change"),
            ):
                value = item.get(field_name)
                if value:
                    lines.extend([f"**{label}:** {value}", ""])
            evidence = item.get("evidence")
            if isinstance(evidence, list) and evidence:
                lines.append("**Evidence:**")
                for evidence_item in evidence:
                    if isinstance(evidence_item, dict):
                        path = evidence_item.get("path") or evidence_item.get("file") or "workspace"
                        note = evidence_item.get("note")
                        lines.append(f"- {path}" + (f" — {note}" if note else ""))
                    else:
                        lines.append(f"- {evidence_item}")
                lines.append("")
            confidence = item.get("confidence")
            if confidence is not None:
                lines.extend([f"**Confidence:** {confidence}", ""])
    else:
        lines.extend(["## Structured Output", "", "```json", json.dumps(payload, indent=2, sort_keys=False), "```", ""])

    return "\n".join(lines).rstrip() + "\n"


def apply_final_artifacts(summary: dict[str, Any]) -> dict[str, Any]:
    """Ensure the summary includes best-draft selection and deliverable artifacts.

    Accepted runs get ``FINAL_ANSWER.*``. Partially accepted runs get
    ``PARTIAL_ANSWER.*``. Other runs get ``BEST_DRAFT.*``. The summary/report are
    rewritten after the selection step so the artifacts are internally consistent.
    """

    summary = copy.deepcopy(summary)
    run_dir = ensure_run_dir((summary.get("artifacts") or {}).get("run_dir") or summary.get("run_dir") or ".")
    artifacts = dict(summary.get("artifacts") or {})
    task = summary.get("task") or {}
    task_id = str(task.get("id") or "task")
    bounded_review_summary = summary.get("bounded_review_summary")
    if not isinstance(bounded_review_summary, dict) or not bounded_review_summary:
        run_details = summary.get("run_details") or {}
        bounded_review_summary = run_details.get("bounded_review_summary")
        if isinstance(bounded_review_summary, dict) and bounded_review_summary:
            summary["bounded_review_summary"] = copy.deepcopy(bounded_review_summary)

    drafts = list(summary.get("drafts") or [])
    best_draft = select_best_draft(drafts)
    if best_draft is not None:
        summary["best_draft_id"] = best_draft.get("draft_id")
        summary.setdefault("selected_draft_id", best_draft.get("draft_id"))
        for index, draft in enumerate(drafts):
            if draft.get("draft_id") == best_draft.get("draft_id"):
                drafts[index] = best_draft
                break
    summary["drafts"] = drafts

    verdict = str(summary.get("verdict") or "")
    fully_accepted = verdict in _FULLY_ACCEPTED_RUN_VERDICTS
    partially_accepted = verdict in _PARTIAL_ACCEPTED_RUN_VERDICTS
    payload: dict[str, Any] | None = None
    artifact_kind = None
    artifact_json_path: Path | None = None
    artifact_md_path: Path | None = None

    if fully_accepted:
        payload = summary.get("final_answer")
        if not isinstance(payload, dict) or not payload:
            if best_draft is not None:
                payload = copy.deepcopy((best_draft.get("metadata") or {}).get("payload") or {})
        if isinstance(payload, dict) and payload:
            artifact_kind = "final_answer"
            artifact_json_path = run_dir / "FINAL_ANSWER.json"
            artifact_md_path = run_dir / "FINAL_ANSWER.md"
    elif partially_accepted:
        payload = summary.get("partial_answer")
        if not isinstance(payload, dict) or not payload:
            source_payload = summary.get("final_answer")
            if (not isinstance(source_payload, dict) or not source_payload) and best_draft is not None:
                source_payload = copy.deepcopy((best_draft.get("metadata") or {}).get("payload") or {})
            payload = build_partial_answer_payload(summary, source_payload)
        if isinstance(payload, dict) and payload:
            artifact_kind = "partial_answer"
            artifact_json_path = run_dir / "PARTIAL_ANSWER.json"
            artifact_md_path = run_dir / "PARTIAL_ANSWER.md"
            summary["partial_answer"] = payload
    else:
        if best_draft is not None:
            payload = copy.deepcopy((best_draft.get("metadata") or {}).get("payload") or {})
            if isinstance(payload, dict) and payload:
                payload = _augment_best_draft_payload(best_draft, payload)
            artifact_kind = "best_draft"
            artifact_json_path = run_dir / "BEST_DRAFT.json"
            artifact_md_path = run_dir / "BEST_DRAFT.md"
            summary["best_draft"] = best_draft

    if artifact_json_path is not None and artifact_md_path is not None and isinstance(payload, dict) and payload:
        write_json(artifact_json_path, payload)
        write_text(
            artifact_md_path,
            render_deliverable_markdown(
                task_id,
                payload,
                artifact_label=(
                    "Final Answer"
                    if fully_accepted
                    else "Partial Answer"
                    if partially_accepted
                    else "Best Draft"
                ),
                accepted=fully_accepted,
            ),
        )
        artifacts["final_artifact"] = str(artifact_md_path)
        artifacts["final_artifact_json"] = str(artifact_json_path)
        artifacts["final_artifact_kind"] = artifact_kind
        if fully_accepted:
            artifacts["final_answer_json"] = str(artifact_json_path)
            artifacts["final_answer_md"] = str(artifact_md_path)
            summary["final_answer"] = payload
        elif partially_accepted:
            artifacts["partial_answer_json"] = str(artifact_json_path)
            artifacts["partial_answer_md"] = str(artifact_md_path)
        else:
            artifacts["best_draft_json"] = str(artifact_json_path)
            artifacts["best_draft_md"] = str(artifact_md_path)
    else:
        artifacts.setdefault("final_artifact", "")
        artifacts.setdefault("final_artifact_kind", "none")

    contract = summary.get("analysis_review_contract")
    if isinstance(contract, dict) and contract:
        contract_path = run_dir / "analysis_review.contract.effective.json"
        write_json(contract_path, contract)
        artifacts["analysis_review_contract_json"] = str(contract_path)

    issue_ledger = summary.get("issue_ledger")
    if isinstance(issue_ledger, list) and issue_ledger:
        issue_ledger_path = run_dir / "issue_ledger.final.json"
        write_json(issue_ledger_path, issue_ledger)
        artifacts["issue_ledger_json"] = str(issue_ledger_path)

    summary_path = run_dir / "summary.json"
    report_path = run_dir / "REPORT.md"
    artifacts["report_md"] = str(report_path)
    artifacts["summary_json"] = str(summary_path)
    artifacts["run_dir"] = str(run_dir)
    summary["artifacts"] = artifacts

    write_json(summary_path, summary)
    write_text(report_path, render_report(summary))
    return summary


def write_state_artifacts(state: dict[str, Any]) -> dict[str, Any]:
    """Write report/summary artifacts for a state-style payload.

    This is used by the new harness graph in the rare path where the graph exits
    early before the imperative runner creates on-disk artifacts.
    """

    run_dir_raw = state.get("run_dir") or state.get("out_root") or ".forge-harness-runs"
    run_dir = ensure_run_dir(run_dir_raw)
    summary = {
        "run_id": state.get("run_id"),
        "thread_id": state.get("thread_id"),
        "workspace": state.get("workspace_root"),
        "task": state.get("task_spec") or {},
        "strategy_name": (state.get("strategy_spec") or {}).get("name"),
        "strategy_kind": state.get("strategy_kind"),
        "warnings": list(state.get("warnings") or []),
        "verdict": state.get("run_verdict") or state.get("content_verdict") or "invalid_config",
        "verdicts": {
            "run_verdict": state.get("run_verdict"),
            "content_verdict": state.get("content_verdict"),
            "validator_verdict": state.get("validator_verdict"),
            "policy_verdict": state.get("policy_verdict"),
            "config_verdict": state.get("config_verdict"),
        },
        "final_summary": state.get("summary_text"),
        "workspace_write_policy": ((state.get("task_spec") or {}).get("workspace_write_policy") or {}),
        "workspace_policy_checks": list(state.get("policy_checks") or []),
        "agent_stages": list(state.get("stage_history") or []),
        "validator_rounds": list(state.get("validator_rounds") or []),
        "drafts": list(state.get("drafts") or []),
        "issue_ledger": list(state.get("issue_history") or []),
        "artifacts": {
            "run_dir": str(run_dir),
        },
    }
    summary = apply_final_artifacts(summary)
    state.setdefault("artifact_index", {})["summary_json"] = artifact_ref(
        summary["artifacts"]["summary_json"],
        kind="summary_json",
        description="Machine-readable harness run summary",
    )
    state.setdefault("artifact_index", {})["report_md"] = artifact_ref(
        summary["artifacts"]["report_md"],
        kind="report_md",
        description="Human-readable harness run report",
    )
    state["summary_payload"] = summary
    return state
