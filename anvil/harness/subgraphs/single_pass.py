from __future__ import annotations

from ..state import HarnessState
from ._bridge import run_harness_runner


def single_pass_subgraph(state: HarnessState) -> HarnessState:
    return run_harness_runner(state)
