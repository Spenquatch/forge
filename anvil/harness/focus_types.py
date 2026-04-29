from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .contracts import canonical_artifact_focus_id, canonical_seam_id_for_paths

FocusType = Literal["seam", "artifact"]
AdaptationBasis = Literal["selected_focus_paths", "artifact_singleton"]


@dataclass(frozen=True)
class FocusAdapterPlan:
    primary_focus_id: str | None
    secondary_focus_ids: tuple[str, ...]
    downstream_primary_seam_id: str | None
    downstream_primary_seam_paths: tuple[str, ...]
    adaptation_basis: AdaptationBasis | None

    def to_dict(self) -> dict[str, object]:
        return {
            "primary_focus_id": self.primary_focus_id,
            "secondary_focus_ids": list(self.secondary_focus_ids),
            "downstream_primary_seam_id": self.downstream_primary_seam_id,
            "downstream_primary_seam_paths": list(self.downstream_primary_seam_paths),
            "adaptation_basis": self.adaptation_basis,
        }


@dataclass(frozen=True)
class FocusTypeAdapter:
    focus_type: FocusType

    def canonical_focus_id_for_paths(self, paths: list[str]) -> str | None:
        if not paths:
            return None
        if self.focus_type == "artifact":
            return canonical_artifact_focus_id(paths[0])
        return canonical_seam_id_for_paths(paths)

    def build_adapter_plan(
        self,
        *,
        selected_focus_id: str | None,
        selected_focus_paths: list[str],
        secondary_focus_ids: list[str],
    ) -> FocusAdapterPlan:
        if not selected_focus_id or not selected_focus_paths:
            return FocusAdapterPlan(
                primary_focus_id=None,
                secondary_focus_ids=tuple(secondary_focus_ids),
                downstream_primary_seam_id=None,
                downstream_primary_seam_paths=(),
                adaptation_basis=None,
            )

        return FocusAdapterPlan(
            primary_focus_id=selected_focus_id,
            secondary_focus_ids=tuple(secondary_focus_ids),
            downstream_primary_seam_id=canonical_seam_id_for_paths(
                selected_focus_paths
            ),
            downstream_primary_seam_paths=tuple(selected_focus_paths),
            adaptation_basis=(
                "artifact_singleton"
                if self.focus_type == "artifact"
                else "selected_focus_paths"
            ),
        )


def coerce_focus_type(raw_value: object, *, fallback: FocusType = "seam") -> FocusType:
    normalized = str(raw_value or "").strip().lower()
    if normalized == "artifact":
        return "artifact"
    if normalized == "seam":
        return "seam"
    return fallback


def focus_type_adapter(
    raw_value: object, *, fallback: FocusType = "seam"
) -> FocusTypeAdapter:
    return FocusTypeAdapter(coerce_focus_type(raw_value, fallback=fallback))
