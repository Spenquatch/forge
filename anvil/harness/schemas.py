from __future__ import annotations

from typing import Any

from .contracts import (
    BOUNDED_ATTESTATION_INPUT_SCHEMA_VERSION,
    GROUNDING_MODE_VALUES,
    TRUST_EXECUTION_MODE_VALUES,
)
from .types import VALID_SINGLETON_FOCUS_TYPES

ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        },
        "title": {"type": "string"},
        "evidence": {"type": "string"},
        "how_to_check": {"type": "string"},
        "repair_hint": {"type": "string"},
    },
    "required": ["severity", "title", "evidence", "how_to_check", "repair_hint"],
    "additionalProperties": False,
}


ANALYSIS_ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issue_id": {"type": "string"},
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        },
        "kind": {
            "type": "string",
            "enum": [
                "factual_error",
                "overclaim",
                "missing_evidence",
                "missing_priority",
                "missing_classification",
                "missed_issue",
                "scope_drift",
                "confidence_calibration",
                "insufficient_specificity",
                "missing_section",
                "other",
            ],
        },
        "blocking_class": {
            "type": "string",
            "enum": ["correctness", "actionability", "completeness", "presentation"],
        },
        "recommendation_index": {
            "anyOf": [
                {"type": "integer", "minimum": 1},
                {"type": "null"},
            ]
        },
        "title": {"type": "string"},
        "evidence": {"type": "string"},
        "repair_hint": {"type": "string"},
        "blocking_class_override_reason": {
            "anyOf": [
                {"type": "string"},
                {"type": "null"},
            ]
        },
        "why_not_raised_earlier": {
            "anyOf": [
                {"type": "string"},
                {"type": "null"},
            ]
        },
    },
    "required": [
        "issue_id",
        "severity",
        "kind",
        "blocking_class",
        "title",
        "evidence",
        "repair_hint",
    ],
    "additionalProperties": False,
}


ANALYSIS_TOPIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topic_id": {"type": "string"},
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        },
        "title": {"type": "string"},
        "evidence": {"type": "string"},
        "repair_hint": {"type": "string"},
        "recommendation_index": {
            "anyOf": [
                {"type": "integer", "minimum": 1},
                {"type": "null"},
            ]
        },
    },
    "required": [
        "topic_id",
        "severity",
        "title",
        "evidence",
        "repair_hint",
        "recommendation_index",
    ],
    "additionalProperties": False,
}


RECOMMENDATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "classification": {
            "type": "string",
            "enum": ["confirmed_issue", "risk", "recommendation"],
        },
        "priority": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        },
        "title": {"type": "string"},
        "rationale": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "proposed_change": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "verified_evidence_refs": {
            "type": "array",
            "items": {"type": "string"},
        },
        "checked_files": {
            "type": "array",
            "items": {"type": "string"},
        },
        "affected_files": {
            "type": "array",
            "items": {"type": "string"},
        },
        "grounding_mode": {
            "type": "string",
            "enum": list(GROUNDING_MODE_VALUES),
        },
    },
    "required": [
        "classification",
        "priority",
        "title",
        "rationale",
        "evidence",
        "proposed_change",
        "confidence",
    ],
    "additionalProperties": False,
}


REVIEW_SURFACE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "must_check_files": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "optional_check_files": {
            "type": "array",
            "items": {"type": "string"},
        },
        "scope_note": {"type": "string"},
    },
    "required": ["must_check_files", "optional_check_files", "scope_note"],
    "additionalProperties": False,
}


SCOPE_ESCAPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["path", "reason"],
    "additionalProperties": False,
}


ISSUE_RESOLUTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issue_id": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["addressed", "not_addressed", "disagree"],
        },
        "change_summary": {"type": "string"},
        "residual_risk": {"type": "string"},
    },
    "required": ["issue_id", "status", "change_summary", "residual_risk"],
    "additionalProperties": False,
}


TOPIC_RESOLUTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topic_id": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["addressed", "not_addressed", "disagree"],
        },
        "change_summary": {"type": "string"},
        "residual_risk": {"type": "string"},
        "recommendation_index": {
            "anyOf": [
                {"type": "integer", "minimum": 1},
                {"type": "null"},
            ]
        },
    },
    "required": [
        "topic_id",
        "status",
        "change_summary",
        "residual_risk",
        "recommendation_index",
    ],
    "additionalProperties": False,
}


RECOMMENDATION_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "recommendation_index": {"type": "integer", "minimum": 1},
        "verdict": {
            "type": "string",
            "enum": ["accept", "accept_with_caveat", "revise", "reject"],
        },
        "open_issue_ids": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "checked_files": {"type": "array", "items": {"type": "string"}},
        "verified_evidence_refs": {"type": "array", "items": {"type": "string"}},
        "confidence_assessment": {
            "type": "string",
            "enum": ["too_low", "well_calibrated", "too_high", "not_assessed"],
        },
    },
    "required": [
        "recommendation_index",
        "verdict",
        "open_issue_ids",
        "summary",
        "confidence_assessment",
    ],
    "additionalProperties": False,
}


REVIEW_ISSUE_CLOSURE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issue_id": {"type": "string"},
        "checked_files": {"type": "array", "items": {"type": "string"}},
        "verified_evidence_refs": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["issue_id", "checked_files", "verified_evidence_refs", "summary"],
    "additionalProperties": False,
}


REVIEW_TOPIC_CLOSURE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topic_id": {"type": "string"},
        "checked_files": {"type": "array", "items": {"type": "string"}},
        "verified_evidence_refs": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["topic_id", "checked_files", "verified_evidence_refs", "summary"],
    "additionalProperties": False,
}


SECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {"type": "string"},
        },
        "none_reason": {"type": "string"},
    },
    "required": ["items", "none_reason"],
    "additionalProperties": False,
}


def _seam_schema(*, reason_field: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "seam_id": {"type": "string"},
            "summary": {"type": "string"},
            reason_field: {"type": "string"},
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
        "required": ["seam_id", "summary", reason_field, "paths"],
        "additionalProperties": False,
    }


NULLABLE_INT_SCHEMA: dict[str, Any] = {
    "anyOf": [
        {"type": "integer", "minimum": 0},
        {"type": "null"},
    ]
}


NULLABLE_RECOMMENDATION_INDEX_SCHEMA: dict[str, Any] = {
    "anyOf": [
        {"type": "integer", "minimum": 1},
        {"type": "null"},
    ]
}


BOUNDED_ATTESTATION_REVIEW_STAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "role_name": {"type": "string"},
        "round_index": {"type": "integer", "minimum": 0},
        "issue_count": {"type": "integer", "minimum": 0},
        "issue_cap": NULLABLE_INT_SCHEMA,
        "missing_topic_count": {"type": "integer", "minimum": 0},
        "missing_topic_cap": NULLABLE_INT_SCHEMA,
        "new_topic_count": {"type": "integer", "minimum": 0},
        "new_topic_cap": NULLABLE_INT_SCHEMA,
        "resolved_topic_count": {"type": "integer", "minimum": 0},
        "carried_forward_topic_count": {"type": "integer", "minimum": 0},
        "waived_topic_count": {"type": "integer", "minimum": 0},
        "open_topic_count": {"type": "integer", "minimum": 0},
        "new_medium_or_higher_issue_count": {"type": "integer", "minimum": 0},
        "topic_ledger_count": {"type": "integer", "minimum": 0},
        "new_medium_or_higher_issue_cap": NULLABLE_INT_SCHEMA,
        "scope_escape_count": {"type": "integer", "minimum": 0},
    },
    "required": [
        "role_name",
        "round_index",
        "issue_count",
        "issue_cap",
        "missing_topic_count",
        "missing_topic_cap",
        "new_topic_count",
        "new_topic_cap",
        "resolved_topic_count",
        "carried_forward_topic_count",
        "waived_topic_count",
        "open_topic_count",
        "new_medium_or_higher_issue_count",
        "topic_ledger_count",
        "new_medium_or_higher_issue_cap",
        "scope_escape_count",
    ],
    "additionalProperties": False,
}


BOUNDED_ATTESTATION_ISSUE_LEDGER_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issue_id": {"type": "string"},
        "source_stage_id": {"type": "string"},
        "first_seen_round": NULLABLE_INT_SCHEMA,
        "last_seen_round": NULLABLE_INT_SCHEMA,
        "severity": {"type": "string"},
        "kind": {"type": "string"},
        "blocking_class": {"type": "string"},
        "recommendation_index": NULLABLE_RECOMMENDATION_INDEX_SCHEMA,
        "title": {"type": "string"},
        "evidence": {"type": "string"},
        "repair_hint": {"type": "string"},
        "why_not_raised_earlier": {
            "anyOf": [
                {"type": "string"},
                {"type": "null"},
            ]
        },
        "resolution_status": {"type": "string"},
        "resolution_note": {"type": "string"},
    },
    "required": [
        "issue_id",
        "source_stage_id",
        "first_seen_round",
        "last_seen_round",
        "severity",
        "kind",
        "blocking_class",
        "recommendation_index",
        "title",
        "evidence",
        "repair_hint",
        "why_not_raised_earlier",
        "resolution_status",
        "resolution_note",
    ],
    "additionalProperties": False,
}


BOUNDED_ATTESTATION_TOPIC_LEDGER_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topic_id": {"type": "string"},
        "title": {"type": "string"},
        "severity": {"type": "string"},
        "evidence": {"type": "string"},
        "recommendation_index": NULLABLE_RECOMMENDATION_INDEX_SCHEMA,
        "introduced_by": {"type": "string"},
        "introduced_in_stage_index": NULLABLE_INT_SCHEMA,
        "resolution_status": {"type": "string"},
        "resolution_note": {"type": "string"},
        "resolved_in_stage_index": NULLABLE_INT_SCHEMA,
    },
    "required": [
        "topic_id",
        "title",
        "severity",
        "evidence",
        "recommendation_index",
        "introduced_by",
        "introduced_in_stage_index",
        "resolution_status",
        "resolution_note",
        "resolved_in_stage_index",
    ],
    "additionalProperties": False,
}


FOCUS_GATE_CANDIDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "focus_id": {"type": "string"},
        "focus_summary": {"type": "string"},
        "candidate_paths": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "why_candidate": {"type": "string"},
        "evidence_refs": {
            "type": "array",
            "items": {"type": "string"},
        },
        "score": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "focus_id",
        "focus_summary",
        "candidate_paths",
        "why_candidate",
        "evidence_refs",
        "score",
    ],
    "additionalProperties": False,
}


FOCUS_GATE_QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string"},
        "options": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["prompt", "options"],
    "additionalProperties": False,
}


FOCUS_GATE_ADAPTER_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "primary_focus_id": {
            "anyOf": [
                {"type": "string"},
                {"type": "null"},
            ]
        },
        "secondary_focus_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "downstream_primary_seam_id": {
            "anyOf": [
                {"type": "string"},
                {"type": "null"},
            ]
        },
        "downstream_primary_seam_paths": {
            "type": "array",
            "items": {"type": "string"},
        },
        "adaptation_basis": {
            "anyOf": [
                {
                    "type": "string",
                    "enum": ["selected_focus_paths", "artifact_singleton"],
                },
                {"type": "null"},
            ]
        },
    },
    "required": [
        "primary_focus_id",
        "secondary_focus_ids",
        "downstream_primary_seam_id",
        "downstream_primary_seam_paths",
        "adaptation_basis",
    ],
    "additionalProperties": False,
}


def planning_phase_result_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "phase_id": {"type": "string"},
            "status": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["phase_id", "status", "summary"],
        "additionalProperties": True,
    }


def planning_seam_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "seam_id": {"type": "string"},
            "summary": {"type": "string"},
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
        "required": ["seam_id", "summary", "paths"],
        "additionalProperties": True,
    }


def planning_workstream_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "workstream_id": {"type": "string"},
            "summary": {"type": "string"},
            "seam_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "worktree_recommended": {"type": "boolean"},
        },
        "required": [
            "workstream_id",
            "summary",
            "seam_ids",
            "worktree_recommended",
        ],
        "additionalProperties": True,
    }


def planning_slice_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "slice_id": {"type": "string"},
            "summary": {"type": "string"},
            "workstream_id": {"type": "string"},
            "seam_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "acceptance_criteria": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
        "required": [
            "slice_id",
            "summary",
            "workstream_id",
            "seam_ids",
            "acceptance_criteria",
        ],
        "additionalProperties": True,
    }


def plan_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": ["plan_artifact_v1"]},
            "run_id": {"type": "string"},
            "task": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "task_kind": {"type": "string", "enum": ["planning"]},
                    "objective": {"type": "string"},
                },
                "required": ["id", "task_kind", "objective"],
                "additionalProperties": True,
            },
            "strategy": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "kind": {"type": "string"},
                    "runtime_target": {"type": "string", "enum": ["planning_v1"]},
                    "phases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                },
                "required": ["name", "kind", "runtime_target", "phases"],
                "additionalProperties": True,
            },
            "terminal_status": {
                "type": "string",
                "enum": ["success", "clarification_needed", "failed"],
            },
            "run_mode": {
                "type": "string",
                "enum": [
                    "fixture-backed",
                    "deterministic-live",
                    "provider-reviewed",
                ],
            },
            "stop_reason": {"type": "string"},
            "problem_statement": {"type": "string"},
            "clarification_requests": {
                "type": "array",
                "items": {"type": "string"},
            },
            "repo_evidence_refs": {
                "type": "array",
                "items": {"type": "string"},
            },
            "rubric_results": {
                "type": "array",
                "items": {"type": "string"},
            },
            "seams": {
                "type": "array",
                "items": planning_seam_schema(),
            },
            "workstreams": {
                "type": "array",
                "items": planning_workstream_schema(),
            },
            "slices": {
                "type": "array",
                "items": planning_slice_schema(),
            },
            "phase_results": {
                "type": "array",
                "items": planning_phase_result_schema(),
            },
            "policy_versions": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": True,
            },
            "search_pass_count": {"type": "integer", "minimum": 0},
            "inspected_file_count": {"type": "integer", "minimum": 0},
            "discovery_budget_escalated": {"type": "boolean"},
        },
        "required": [
            "schema_version",
            "run_id",
            "task",
            "strategy",
            "terminal_status",
            "run_mode",
            "stop_reason",
            "problem_statement",
            "clarification_requests",
            "repo_evidence_refs",
            "rubric_results",
            "seams",
            "workstreams",
            "slices",
            "phase_results",
            "policy_versions",
            "search_pass_count",
            "inspected_file_count",
            "discovery_budget_escalated",
        ],
        "additionalProperties": True,
    }


COMMON_PROPS: dict[str, Any] = {
    "summary": {"type": "string"},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "workspace_write_intent": {
        "type": "string",
        "enum": ["none", "repo_patch"],
    },
}


def single_pass_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["done", "partial", "blocked"]},
            **COMMON_PROPS,
            "changes_made": {"type": "array", "items": {"type": "string"}},
            "claims_to_verify": {"type": "array", "items": {"type": "string"}},
            "tests_recommended": {"type": "array", "items": {"type": "string"}},
            "known_risks": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "status",
            "summary",
            "workspace_write_intent",
            "changes_made",
            "claims_to_verify",
            "tests_recommended",
            "known_risks",
            "confidence",
        ],
        "additionalProperties": False,
    }


def proposer_schema() -> dict[str, Any]:
    return single_pass_schema()


def patcher_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["fixed", "partial", "blocked", "no_change_needed"],
            },
            **COMMON_PROPS,
            "changes_made": {"type": "array", "items": {"type": "string"}},
            "resolved_issues": {"type": "array", "items": {"type": "string"}},
            "remaining_issues": {"type": "array", "items": {"type": "string"}},
            "tests_recommended": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "status",
            "summary",
            "workspace_write_intent",
            "changes_made",
            "resolved_issues",
            "remaining_issues",
            "tests_recommended",
            "confidence",
        ],
        "additionalProperties": False,
    }


def falsifier_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["accept", "reject", "inconclusive"]},
            **COMMON_PROPS,
            "issues": {"type": "array", "items": ISSUE_SCHEMA},
            "missing_validations": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "verdict",
            "summary",
            "workspace_write_intent",
            "issues",
            "missing_validations",
            "confidence",
        ],
        "additionalProperties": False,
    }


def analysis_output_schema(
    *,
    require_issue_resolution_map: bool = False,
    require_topic_resolution_map: bool = False,
) -> dict[str, Any]:
    primary_seam_schema = _seam_schema(reason_field="why_primary")
    secondary_seam_schema = _seam_schema(reason_field="why_not_primary")
    recommendation_schema = {
        "type": "object",
        "properties": {
            **RECOMMENDATION_SCHEMA["properties"],
            "seam_id": {"type": "string"},
            "seam_expansion_reason": {"type": "string"},
            "review_surface": REVIEW_SURFACE_SCHEMA,
        },
        "required": [
            *RECOMMENDATION_SCHEMA["required"],
            "seam_id",
            "seam_expansion_reason",
            "review_surface",
        ],
        "additionalProperties": False,
    }
    properties: dict[str, Any] = {
        "status": {
            "type": "string",
            "enum": ["done", "partial", "blocked", "revised", "no_change_needed"],
        },
        **COMMON_PROPS,
        "primary_seam": primary_seam_schema,
        "secondary_seams_considered": {
            "type": "array",
            "items": secondary_seam_schema,
        },
        "scope_escapes": {"type": "array", "items": SCOPE_ESCAPE_SCHEMA},
        "recommendations": {
            "type": "array",
            "items": recommendation_schema,
            "minItems": 1,
        },
        "strengths": SECTION_SCHEMA,
        "uncertainties": SECTION_SCHEMA,
        "files_reviewed": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
    }
    required = [
        "status",
        "summary",
        "workspace_write_intent",
        "primary_seam",
        "secondary_seams_considered",
        "scope_escapes",
        "recommendations",
        "strengths",
        "uncertainties",
        "files_reviewed",
        "confidence",
    ]
    if require_issue_resolution_map:
        properties["issue_resolution_map"] = {
            "type": "array",
            "items": ISSUE_RESOLUTION_SCHEMA,
        }
        required.append("issue_resolution_map")
    if require_topic_resolution_map:
        properties["topic_resolution_map"] = {
            "type": "array",
            "items": TOPIC_RESOLUTION_SCHEMA,
        }
        required.append("topic_resolution_map")
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def analysis_review_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["accept", "accept_partial", "revise", "reject"],
            },
            **COMMON_PROPS,
            "files_reviewed": {"type": "array", "items": {"type": "string"}},
            "issues": {"type": "array", "items": ANALYSIS_ISSUE_SCHEMA},
            "resolved_issue_ids": {"type": "array", "items": {"type": "string"}},
            "carried_forward_issue_ids": {"type": "array", "items": {"type": "string"}},
            "waived_issue_ids": {"type": "array", "items": {"type": "string"}},
            "topics": {"type": "array", "items": ANALYSIS_TOPIC_SCHEMA},
            "resolved_topic_ids": {"type": "array", "items": {"type": "string"}},
            "carried_forward_topic_ids": {"type": "array", "items": {"type": "string"}},
            "waived_topic_ids": {"type": "array", "items": {"type": "string"}},
            "recommendation_reviews": {
                "type": "array",
                "items": RECOMMENDATION_REVIEW_SCHEMA,
                "minItems": 1,
            },
            "issue_closure_reviews": {
                "type": "array",
                "items": REVIEW_ISSUE_CLOSURE_SCHEMA,
            },
            "topic_closure_reviews": {
                "type": "array",
                "items": REVIEW_TOPIC_CLOSURE_SCHEMA,
            },
            "scope_escapes": {"type": "array", "items": SCOPE_ESCAPE_SCHEMA},
            "grounding_score": {"type": "number", "minimum": 0, "maximum": 1},
            "actionability_score": {"type": "number", "minimum": 0, "maximum": 1},
            "scope_compliance_score": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "verdict",
            "summary",
            "workspace_write_intent",
            "files_reviewed",
            "issues",
            "resolved_issue_ids",
            "carried_forward_issue_ids",
            "waived_issue_ids",
            "topics",
            "resolved_topic_ids",
            "carried_forward_topic_ids",
            "waived_topic_ids",
            "recommendation_reviews",
            "issue_closure_reviews",
            "topic_closure_reviews",
            "scope_escapes",
            "grounding_score",
            "actionability_score",
            "scope_compliance_score",
            "confidence",
        ],
        "additionalProperties": False,
    }


def bounded_attestation_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "schema_version": {
                "type": "string",
                "const": BOUNDED_ATTESTATION_INPUT_SCHEMA_VERSION,
            },
            "source": {
                "type": "object",
                "properties": {
                    "strategy_kind": {"type": "string"},
                    "mode": {"type": "string", "enum": ["bounded"]},
                    "analysis_stage_role_name": {"type": "string"},
                    "analysis_stage_index": {"type": "integer", "minimum": 0},
                    "bounded_payload_sha256": {"type": "string"},
                },
                "required": [
                    "strategy_kind",
                    "mode",
                    "analysis_stage_role_name",
                    "analysis_stage_index",
                    "bounded_payload_sha256",
                ],
                "additionalProperties": False,
            },
            "focus_decision": {
                "anyOf": [
                    focus_gate_output_schema(),
                    {"type": "null"},
                ]
            },
            "contract": {
                "type": "object",
                "properties": {
                    "contract_version": {"type": "string"},
                    "strategy_kind": {"type": "string"},
                    "trust_execution_mode": {
                        "type": "string",
                        "enum": list(TRUST_EXECUTION_MODE_VALUES),
                    },
                },
                "required": [
                    "contract_version",
                    "strategy_kind",
                    "trust_execution_mode",
                ],
                "additionalProperties": False,
            },
            "bounded_analysis": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "recommendations": {
                        "type": "array",
                        "items": RECOMMENDATION_SCHEMA,
                        "minItems": 1,
                    },
                    "files_reviewed": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "primary_seam": _seam_schema(reason_field="why_primary"),
                    "secondary_seams_considered": {
                        "type": "array",
                        "items": _seam_schema(reason_field="why_not_primary"),
                    },
                    "scope_escapes": {
                        "type": "array",
                        "items": SCOPE_ESCAPE_SCHEMA,
                    },
                },
                "required": [
                    "summary",
                    "recommendations",
                    "files_reviewed",
                    "primary_seam",
                    "secondary_seams_considered",
                    "scope_escapes",
                ],
                "additionalProperties": False,
            },
            "review_surface": {
                "type": "object",
                "properties": {
                    "recommendation_count": {"type": "integer", "minimum": 0},
                    "recommendations_with_review_surface": {
                        "type": "integer",
                        "minimum": 0,
                    },
                    "review_stages": {
                        "type": "array",
                        "items": BOUNDED_ATTESTATION_REVIEW_STAGE_SCHEMA,
                    },
                    "scope_escape_count": {"type": "integer", "minimum": 0},
                },
                "required": [
                    "recommendation_count",
                    "recommendations_with_review_surface",
                    "review_stages",
                    "scope_escape_count",
                ],
                "additionalProperties": False,
            },
            "ledgers": {
                "type": "object",
                "properties": {
                    "issue_ledger": {
                        "type": "array",
                        "items": BOUNDED_ATTESTATION_ISSUE_LEDGER_ITEM_SCHEMA,
                    },
                    "topic_ledger": {
                        "type": "array",
                        "items": BOUNDED_ATTESTATION_TOPIC_LEDGER_ITEM_SCHEMA,
                    },
                },
                "required": ["issue_ledger", "topic_ledger"],
                "additionalProperties": False,
            },
            "provenance_context": {
                "type": "object",
                "properties": {
                    "normalized_ref_count": {"type": "integer", "minimum": 0},
                    "recommendation_evidence_index": {
                        "type": "object",
                        "patternProperties": {
                            "^[0-9]+$": {
                                "type": "array",
                                "items": {"type": "string"},
                            }
                        },
                        "additionalProperties": False,
                    },
                },
                "required": [
                    "normalized_ref_count",
                    "recommendation_evidence_index",
                ],
                "additionalProperties": False,
            },
        },
        "required": [
            "schema_version",
            "source",
            "focus_decision",
            "contract",
            "bounded_analysis",
            "review_surface",
            "ledgers",
            "provenance_context",
        ],
        "additionalProperties": False,
    }


def focus_gate_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "gate_path": {
                "type": "string",
                "enum": ["adjudicate", "deliberate"],
            },
            "focus_type": {
                "type": "string",
                "enum": list(VALID_SINGLETON_FOCUS_TYPES),
            },
            "decision_state": {
                "type": "string",
                "enum": ["selected", "clarification_requested", "no_viable_focus"],
            },
            "decision_basis": {
                "type": "string",
                "enum": ["request_only", "repo_probe", "rerun_answer"],
            },
            "selected_focus_id": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "null"},
                ]
            },
            "selected_focus_summary": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "null"},
                ]
            },
            "selected_focus_paths": {
                "type": "array",
                "items": {"type": "string"},
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "confidence_band": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "files_hint_disposition": {
                "type": "string",
                "enum": ["helped", "hurt", "ignored", "absent"],
            },
            "checked_files": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 6,
            },
            "candidates": {
                "type": "array",
                "items": FOCUS_GATE_CANDIDATE_SCHEMA,
                "maxItems": 3,
            },
            "question": FOCUS_GATE_QUESTION_SCHEMA,
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
            },
            "adapter_plan": FOCUS_GATE_ADAPTER_PLAN_SCHEMA,
        },
        "required": [
            "gate_path",
            "focus_type",
            "decision_state",
            "decision_basis",
            "selected_focus_id",
            "selected_focus_summary",
            "selected_focus_paths",
            "confidence",
            "confidence_band",
            "files_hint_disposition",
            "checked_files",
            "candidates",
            "question",
            "warnings",
            "adapter_plan",
        ],
        "additionalProperties": False,
    }


def focus_probe_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "focus_type": {
                "type": "string",
                "enum": list(VALID_SINGLETON_FOCUS_TYPES),
            },
            "files_hint_disposition": {
                "type": "string",
                "enum": ["helped", "hurt", "ignored", "absent"],
            },
            "checked_files": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 6,
            },
            "candidates": {
                "type": "array",
                "items": FOCUS_GATE_CANDIDATE_SCHEMA,
                "maxItems": 3,
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "focus_type",
            "files_hint_disposition",
            "checked_files",
            "candidates",
            "warnings",
        ],
        "additionalProperties": False,
    }


def focus_gate_probe_output_schema() -> dict[str, Any]:
    return focus_probe_output_schema()
