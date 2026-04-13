from __future__ import annotations

from typing import Any


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
                "other",
            ],
        },
        "title": {"type": "string"},
        "evidence": {"type": "string"},
        "repair_hint": {"type": "string"},
    },
    "required": ["severity", "kind", "title", "evidence", "repair_hint"],
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


def analysis_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["done", "partial", "blocked", "revised", "no_change_needed"],
            },
            **COMMON_PROPS,
            "recommendations": {
                "type": "array",
                "items": RECOMMENDATION_SCHEMA,
            },
            "strengths": {"type": "array", "items": {"type": "string"}},
            "uncertainties": {"type": "array", "items": {"type": "string"}},
            "files_reviewed": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "status",
            "summary",
            "workspace_write_intent",
            "recommendations",
            "strengths",
            "uncertainties",
            "files_reviewed",
            "confidence",
        ],
        "additionalProperties": False,
    }


def analysis_review_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["accept", "revise", "reject"]},
            **COMMON_PROPS,
            "issues": {"type": "array", "items": ANALYSIS_ISSUE_SCHEMA},
            "missing_topics": {"type": "array", "items": {"type": "string"}},
            "grounding_score": {"type": "number", "minimum": 0, "maximum": 1},
            "actionability_score": {"type": "number", "minimum": 0, "maximum": 1},
            "scope_compliance_score": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "verdict",
            "summary",
            "workspace_write_intent",
            "issues",
            "missing_topics",
            "grounding_score",
            "actionability_score",
            "scope_compliance_score",
            "confidence",
        ],
        "additionalProperties": False,
    }
