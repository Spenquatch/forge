from __future__ import annotations

from typing import Any, cast

from ..selection import select_best_draft
from ..state import DraftRecord, HarnessState


def select_best_draft_node(state: HarnessState) -> HarnessState:
    drafts = list(state.get("drafts") or [])
    best = select_best_draft(cast(list[dict[str, Any]], drafts))
    if best is None:
        return state
    state["best_draft_id"] = best.get("draft_id")
    state["selected_draft_id"] = best.get("draft_id")
    for index, draft in enumerate(drafts):
        if draft.get("draft_id") == best.get("draft_id"):
            drafts[index] = cast(DraftRecord, best)
            break
    state["drafts"] = drafts
    return state
