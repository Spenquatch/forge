from __future__ import annotations

from ..planning_runtime import execute_planning_runtime
from ..state import HarnessState


def planning_v1_subgraph(state: HarnessState) -> HarnessState:
    return execute_planning_runtime(state)
