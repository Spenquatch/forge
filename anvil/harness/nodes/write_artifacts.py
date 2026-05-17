from __future__ import annotations

from typing import Any, cast

from ..reporting import publish_state_artifacts_v1
from ..state import HarnessState


def write_artifacts_node(state: HarnessState) -> HarnessState:
    return cast(HarnessState, publish_state_artifacts_v1(cast(dict[str, Any], state)))
