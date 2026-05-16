from __future__ import annotations

from ..reporting import publish_state_artifacts_v1
from ..state import HarnessState


def write_artifacts_node(state: HarnessState) -> HarnessState:
    return publish_state_artifacts_v1(state)
