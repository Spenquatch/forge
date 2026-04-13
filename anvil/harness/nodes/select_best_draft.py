from __future__ import annotations

from ..selection import select_best_draft
from ..state import HarnessState


def select_best_draft_node(state: HarnessState) -> HarnessState:
    best = select_best_draft(list(state.get("drafts") or []))
    if best is None:
        return state
    state["best_draft_id"] = best.get("draft_id")
    state["selected_draft_id"] = best.get("draft_id")
    drafts = list(state.get("drafts") or [])
    for index, draft in enumerate(drafts):
        if draft.get("draft_id") == best.get("draft_id"):
            drafts[index] = best
            break
    state["drafts"] = drafts
    return state
