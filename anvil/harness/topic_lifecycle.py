from __future__ import annotations

from typing import Any

TOPIC_STATUS_FIELD_BY_NAME = {
    "open": "open_topic_ids",
    "carried_forward": "carried_forward_topic_ids",
    "waived": "waived_topic_ids",
    "resolved": "resolved_topic_ids",
    "disagreed": "disagreed_topic_ids",
}

_LEDGER_STATUSES_BY_STATUS_NAME = {
    "open": {"open"},
    "carried_forward": {"carried_forward"},
    "waived": {"waived"},
    "resolved": {"addressed"},
    "disagreed": {"disagree"},
}

_UNRESOLVED_LEDGER_STATUSES = {"open", "carried_forward"}


def topic_status_field_name(status_name: str) -> str:
    return TOPIC_STATUS_FIELD_BY_NAME[status_name]


def topic_ids_for_status_name(
    topic_ledger: list[dict[str, Any]],
    *,
    status_name: str,
) -> list[str]:
    allowed_statuses = _LEDGER_STATUSES_BY_STATUS_NAME[status_name]
    return sorted(
        str(item.get("topic_id") or "").strip()
        for item in topic_ledger
        if str(item.get("topic_id") or "").strip()
        and str(item.get("resolution_status") or "").strip() in allowed_statuses
    )


def unresolved_topic_ids(topic_ledger: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            *topic_ids_for_status_name(topic_ledger, status_name="open"),
            *topic_ids_for_status_name(topic_ledger, status_name="carried_forward"),
        }
    )


def partial_accept_topic_eligibility(
    topic_ledger: list[dict[str, Any]],
    *,
    accepted_recommendation_indices: list[int],
) -> dict[str, Any]:
    accepted_index_set = set(accepted_recommendation_indices)
    blocked_recommendation_indices: set[int] = set()
    global_blocking_topic_ids: set[str] = set()

    for item in topic_ledger:
        if str(item.get("resolution_status") or "").strip() not in _UNRESOLVED_LEDGER_STATUSES:
            continue
        topic_id = str(item.get("topic_id") or "").strip()
        recommendation_index = item.get("recommendation_index")
        if recommendation_index in (None, ""):
            if topic_id:
                global_blocking_topic_ids.add(topic_id)
            continue
        try:
            normalized_index = int(recommendation_index)
        except (TypeError, ValueError):
            if topic_id:
                global_blocking_topic_ids.add(topic_id)
            continue
        if normalized_index in accepted_index_set:
            blocked_recommendation_indices.add(normalized_index)

    return {
        "eligible_recommendation_indices": sorted(
            index for index in accepted_index_set if index not in blocked_recommendation_indices
        ),
        "blocked_recommendation_indices": sorted(blocked_recommendation_indices),
        "global_blocking_topic_ids": sorted(global_blocking_topic_ids),
    }
