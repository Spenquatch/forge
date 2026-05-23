from __future__ import annotations

from ..single_pass_runtime import execute_single_pass_runtime
from ..state import HarnessState


def single_pass_subgraph(state: HarnessState) -> HarnessState:
    return execute_single_pass_runtime(state)
