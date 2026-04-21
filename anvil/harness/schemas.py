from __future__ import annotations

from typing import Any

from .contracts import GROUNDING_MODE_VALUES

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
        "required": ["verdict", "summary", "workspace_write_intent", "issues", "missing_validations", "confidence"],
        "additionalProperties": False,
    }


def analysis_output_schema(
    *,
    require_issue_resolution_map: bool = False,
    require_topic_resolution_map: bool = False,
) -> dict[str, Any]:
    recommendation_schema = {
        "type": "object",
        "properties": {
            **RECOMMENDATION_SCHEMA["properties"],
            "review_surface": REVIEW_SURFACE_SCHEMA,
        },
        "required": [*RECOMMENDATION_SCHEMA["required"], "review_surface"],
        "additionalProperties": False,
    }
    properties: dict[str, Any] = {
        "status": {
            "type": "string",
            "enum": ["done", "partial", "blocked", "revised", "no_change_needed"],
        },
        **COMMON_PROPS,
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
            "verdict": {"type": "string", "enum": ["accept", "accept_partial", "revise", "reject"]},
            **COMMON_PROPS,
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
            "scope_escapes": {"type": "array", "items": SCOPE_ESCAPE_SCHEMA},
            "grounding_score": {"type": "number", "minimum": 0, "maximum": 1},
            "actionability_score": {"type": "number", "minimum": 0, "maximum": 1},
            "scope_compliance_score": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "verdict",
            "summary",
            "workspace_write_intent",
            "issues",
            "resolved_issue_ids",
            "carried_forward_issue_ids",
            "waived_issue_ids",
            "topics",
            "resolved_topic_ids",
            "carried_forward_topic_ids",
            "waived_topic_ids",
            "recommendation_reviews",
            "scope_escapes",
            "grounding_score",
            "actionability_score",
            "scope_compliance_score",
            "confidence",
        ],
        "additionalProperties": False,
    }
