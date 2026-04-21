from __future__ import annotations

from typing import Any

TOPIC_STATUS_FIELD_BY_NAME = {
    "open": "open_topic_ids",
    "carried_forward": "carried_forward_topic_ids",
    "waived": "waived_topic_ids",
    "resolved": "resolved_topic_ids",
}

_LEDGER_STATUSES_BY_STATUS_NAME = {
    "open": {"open"},
    "carried_forward": {"carried_forward"},
    "waived": {"waived"},
    "resolved": {"addressed"},
}


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
