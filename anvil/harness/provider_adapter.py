from __future__ import annotations

"""Normalized provider adapter surface for harness stages.

This module is the LangGraph-facing name for the provider adapter layer described
in ADR-0023. The existing imperative mini-harness implementation lives in
``anvil.harness.providers``; this file re-exports that behavior under the new
module path while preserving the older imports used by existing tests.
"""

from .providers import ForgeProviderAdapter, get_provider, resolve_provider_name
from .types import ProviderRun as StageRun
from .types import StageRequest

__all__ = [
    "ForgeProviderAdapter",
    "StageRequest",
    "StageRun",
    "get_provider",
    "resolve_provider_name",
]
