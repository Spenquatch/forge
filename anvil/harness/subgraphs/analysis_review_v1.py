from __future__ import annotations

from ..state import HarnessState
from ._bridge import run_harness_runner


def analysis_review_v1_subgraph(state: HarnessState) -> HarnessState:
    return run_harness_runner(state)
