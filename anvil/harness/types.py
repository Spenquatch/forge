from __future__ import annotations

import posixpath
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

VALID_TASK_KINDS = {"patch", "analysis_review"}
ANALYSIS_REVIEW_BOUNDED_KIND = "analysis_review_bounded_v1"
ANALYSIS_REVIEW_TRUST_KIND = "analysis_review_trust_v1"
ANALYSIS_REVIEW_LEGACY_KIND = "analysis_review_v1"
ANALYSIS_REVIEW_STRATEGY_KINDS = {
    ANALYSIS_REVIEW_BOUNDED_KIND,
    ANALYSIS_REVIEW_TRUST_KIND,
    ANALYSIS_REVIEW_LEGACY_KIND,
}
VALID_VALIDATOR_RUN_WHEN = {
    "patch_only",
    "analysis_only",
    "always",
    "workspace_changed",
    "mode_allow",
    "mode_require",
}
VALID_MISSING_HANDLING = {"fail", "skip", "not_applicable"}
VALID_EVIDENCE_CAP_POLICIES = {"trim_to_cap", "strict"}
VALID_FOCUS_GATE_DEFAULT_PATHS = {"adjudicate", "deliberate"}
VALID_FOCUS_GATE_CLARIFICATION_POLICIES = {"block_for_clarification"}
M1_ALLOWED_FOCUS_TYPES = ["seam"]
_WORKSPACE_REF_LOCATION_SUFFIX_RE = re.compile(
    r"^(?P<path>.+?):(?P<ranges>\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)$"
)


def is_analysis_review_strategy_kind(strategy_kind: str) -> bool:
    return strategy_kind in ANALYSIS_REVIEW_STRATEGY_KINDS


def _reject_unknown_keys(
    data: dict[str, Any], *, allowed_keys: set[str], field_name: str
) -> None:
    unknown_keys = sorted(set(data.keys()) - allowed_keys)
    if unknown_keys:
        raise ValueError(
            f"{field_name} contains unsupported keys: {', '.join(unknown_keys)}."
        )


def _validate_m1_allowed_focus_types(value: Any, *, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list.")
    normalized = [str(item).strip().lower() for item in value]
    if normalized != M1_ALLOWED_FOCUS_TYPES:
        raise ValueError(f"{field_name} must be exactly {M1_ALLOWED_FOCUS_TYPES!r}.")
    return normalized


def strip_workspace_ref_location_suffix(value: str) -> str:
    text = str(value or "").strip()
    if not text or "://" in text:
        return text
    match = _WORKSPACE_REF_LOCATION_SUFFIX_RE.match(text)
    if not match:
        return text
    return match.group("path")


def normalize_workspace_ref(value: Any, *, workspace_root: str | Path | None = None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" in text:
        return text
    normalized = strip_workspace_ref_location_suffix(text).replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute():
        root = Path(workspace_root or Path.cwd()).resolve(strict=False)
        try:
            normalized = candidate.resolve(strict=False).relative_to(root).as_posix()
        except ValueError:
            if normalized.startswith("/.") and not normalized.startswith("//"):
                normalized = posixpath.normpath(normalized.lstrip("/"))
                if normalized == ".":
                    return ""
                while normalized.startswith("./"):
                    normalized = normalized[2:]
                return normalized
            return candidate.as_posix()
    else:
        normalized = posixpath.normpath(normalized)
        if normalized == ".":
            return ""
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def normalize_workspace_ref_list(
    values: Any, *, workspace_root: str | Path | None = None
) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        value = normalize_workspace_ref(item, workspace_root=workspace_root)
        if value:
            normalized.append(value)
    return normalized


def dedupe_preserving_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def canonical_workspace_ref_list(
    values: Any, *, workspace_root: str | Path | None = None
) -> list[str]:
    return dedupe_preserving_order(
        normalize_workspace_ref_list(values, workspace_root=workspace_root)
    )


@dataclass
class TaskFocusGateConfig:
    enabled: Optional[bool] = None
    allowed_focus_types: Optional[list[str]] = None
    clarification_policy: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TaskFocusGateConfig | None":
        if data is None:
            return None
        if not isinstance(data, dict):
            raise ValueError("focus_gate must be a mapping when provided.")
        _reject_unknown_keys(
            data,
            allowed_keys={"enabled", "allowed_focus_types", "clarification_policy"},
            field_name="focus_gate",
        )
        allowed_focus_types = data.get("allowed_focus_types")
        clarification_policy = data.get("clarification_policy")
        normalized_clarification_policy = None
        if clarification_policy is not None:
            normalized_clarification_policy = str(clarification_policy).strip().lower()
            if (
                normalized_clarification_policy
                not in VALID_FOCUS_GATE_CLARIFICATION_POLICIES
            ):
                raise ValueError(
                    "focus_gate.clarification_policy must be one of: "
                    + ", ".join(sorted(VALID_FOCUS_GATE_CLARIFICATION_POLICIES))
                    + "."
                )
        return cls(
            enabled=(
                None
                if "enabled" not in data or data.get("enabled") is None
                else bool(data.get("enabled"))
            ),
            allowed_focus_types=(
                None
                if allowed_focus_types is None
                else _validate_m1_allowed_focus_types(
                    allowed_focus_types, field_name="focus_gate.allowed_focus_types"
                )
            ),
            clarification_policy=normalized_clarification_policy,
        )


@dataclass
class StrategyFocusGateConfig:
    enabled: Optional[bool] = None
    default_path: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "StrategyFocusGateConfig | None":
        if data is None:
            return None
        if not isinstance(data, dict):
            raise ValueError("focus_gate must be a mapping when provided.")
        _reject_unknown_keys(
            data,
            allowed_keys={"enabled", "default_path"},
            field_name="focus_gate",
        )
        default_path = data.get("default_path")
        normalized_default_path = None
        if default_path is not None:
            normalized_default_path = str(default_path).strip().lower()
            if normalized_default_path not in VALID_FOCUS_GATE_DEFAULT_PATHS:
                raise ValueError(
                    "focus_gate.default_path must be one of: "
                    + ", ".join(sorted(VALID_FOCUS_GATE_DEFAULT_PATHS))
                    + "."
                )
        return cls(
            enabled=(
                None
                if "enabled" not in data or data.get("enabled") is None
                else bool(data.get("enabled"))
            ),
            default_path=normalized_default_path,
        )


@dataclass
class FocusGateAnswer:
    question_prompt: str
    selected_option: str
    freeform_answer: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "FocusGateAnswer | None":
        if data is None:
            return None
        if not isinstance(data, dict):
            raise ValueError("focus_gate_answer must be a mapping when provided.")
        question_prompt = str(data.get("question_prompt", "")).strip()
        if not question_prompt:
            raise ValueError(
                "focus_gate_answer.question_prompt must be a non-empty string."
            )
        selected_option = str(data.get("selected_option", "")).strip()
        if not selected_option:
            raise ValueError(
                "focus_gate_answer.selected_option must be a non-empty string."
            )
        freeform_answer = data.get("freeform_answer", "")
        return cls(
            question_prompt=question_prompt,
            selected_option=selected_option,
            freeform_answer="" if freeform_answer is None else str(freeform_answer),
        )


@dataclass
class WorkspaceWritePolicy:
    mode: str = "forbid"  # forbid | allow | require
    allowed_paths: list[str] = field(default_factory=list)
    denied_paths: list[str] = field(default_factory=list)
    allow_untracked: bool = False
    allow_renames: bool = False
    allow_deletions: bool = False
    max_touched_files: Optional[int] = None
    require_clean_start: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkspaceWritePolicy":
        if not isinstance(data, dict):
            raise ValueError("workspace_write_policy must be a mapping.")
        mode = str(data.get("mode", "forbid")).strip().lower()
        if mode not in {"forbid", "allow", "require"}:
            raise ValueError(
                "workspace_write_policy.mode must be one of: forbid, allow, require."
            )
        max_touched_raw = data.get("max_touched_files")
        max_touched_files = None if max_touched_raw is None else int(max_touched_raw)
        if max_touched_files is not None and max_touched_files < 0:
            raise ValueError("workspace_write_policy.max_touched_files must be >= 0 or null.")
        if mode == "forbid" and max_touched_files is None:
            max_touched_files = 0
        return cls(
            mode=mode,
            allowed_paths=[str(x) for x in data.get("allowed_paths", [])],
            denied_paths=[str(x) for x in data.get("denied_paths", [])],
            allow_untracked=bool(data.get("allow_untracked", False)),
            allow_renames=bool(data.get("allow_renames", False)),
            allow_deletions=bool(data.get("allow_deletions", False)),
            max_touched_files=max_touched_files,
            require_clean_start=bool(data.get("require_clean_start", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def allows_workspace_writes(self) -> bool:
        return self.mode in {"allow", "require"}

    def requires_workspace_writes(self) -> bool:
        return self.mode == "require"


@dataclass
class ReviewRequirements:
    require_evidence_per_recommendation: bool = False
    require_classification: bool = False
    require_priority: bool = False
    min_recommendations: int = 0
    evidence_cap_policy: str = "trim_to_cap"

    @classmethod
    def defaults_for_task_kind(cls, task_kind: str) -> "ReviewRequirements":
        if task_kind == "analysis_review":
            return cls(
                require_evidence_per_recommendation=True,
                require_classification=True,
                require_priority=True,
                min_recommendations=1,
                evidence_cap_policy="trim_to_cap",
            )
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, task_kind: str) -> "ReviewRequirements":
        defaults = cls.defaults_for_task_kind(task_kind)
        if data is None:
            return defaults
        if not isinstance(data, dict):
            raise ValueError("review_requirements must be a mapping when provided.")
        min_recommendations = int(data.get("min_recommendations", defaults.min_recommendations))
        if min_recommendations < 0:
            raise ValueError("review_requirements.min_recommendations must be >= 0.")
        evidence_cap_policy = str(
            data.get("evidence_cap_policy", defaults.evidence_cap_policy)
        ).strip().lower()
        if evidence_cap_policy not in VALID_EVIDENCE_CAP_POLICIES:
            raise ValueError(
                "review_requirements.evidence_cap_policy must be one of: "
                + ", ".join(sorted(VALID_EVIDENCE_CAP_POLICIES))
                + "."
            )
        return cls(
            require_evidence_per_recommendation=bool(
                data.get(
                    "require_evidence_per_recommendation",
                    defaults.require_evidence_per_recommendation,
                )
            ),
            require_classification=bool(
                data.get("require_classification", defaults.require_classification)
            ),
            require_priority=bool(data.get("require_priority", defaults.require_priority)),
            min_recommendations=min_recommendations,
            evidence_cap_policy=evidence_cap_policy,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskSpec:
    id: str
    objective: str
    workspace_write_policy: WorkspaceWritePolicy
    task_kind: str = "patch"
    acceptance: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    context: str = ""
    notes: str = ""
    files_hint: list[str] = field(default_factory=list)
    prompt_addendum: str = ""
    review_requirements: ReviewRequirements = field(default_factory=ReviewRequirements)
    focus_gate: TaskFocusGateConfig | None = None
    focus_gate_answer: FocusGateAnswer | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskSpec":
        if "workspace_write_policy" not in data:
            raise ValueError(
                "Task spec is missing required field: workspace_write_policy. "
                "Declare whether target-workspace writes are forbidden, allowed, or required."
            )
        policy = WorkspaceWritePolicy.from_dict(dict(data["workspace_write_policy"]))
        task_kind_raw = str(data.get("task_kind") or "").strip().lower()
        if not task_kind_raw:
            task_kind_raw = "analysis_review" if policy.mode == "forbid" else "patch"
        if task_kind_raw not in VALID_TASK_KINDS:
            raise ValueError(
                "task_kind must be one of: " + ", ".join(sorted(VALID_TASK_KINDS))
            )
        return cls(
            id=str(data.get("id") or data.get("name") or "task"),
            objective=str(data["objective"]),
            workspace_write_policy=policy,
            task_kind=task_kind_raw,
            acceptance=[str(x) for x in data.get("acceptance", [])],
            constraints=[str(x) for x in data.get("constraints", [])],
            context=str(data.get("context", "") or ""),
            notes=str(data.get("notes", "") or ""),
            files_hint=[str(x) for x in data.get("files_hint", [])],
            prompt_addendum=str(data.get("prompt_addendum", "") or ""),
            review_requirements=ReviewRequirements.from_dict(
                data.get("review_requirements"),
                task_kind=task_kind_raw,
            ),
            focus_gate=TaskFocusGateConfig.from_dict(data.get("focus_gate")),
            focus_gate_answer=FocusGateAnswer.from_dict(data.get("focus_gate_answer")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RoleConfig:
    provider: str
    model: Optional[str] = None
    effort: Optional[str] = None
    access: str = "read"  # read | write | danger
    timeout_sec: int = 1800
    max_turns: Optional[int] = None
    max_budget_usd: Optional[float] = None
    extra_args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    disable_bare: bool = False
    skip_git_repo_check: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoleConfig":
        return cls(
            provider=str(data["provider"]),
            model=(None if data.get("model") in (None, "") else str(data.get("model"))),
            effort=(None if data.get("effort") in (None, "") else str(data.get("effort"))),
            access=str(data.get("access", "read")),
            timeout_sec=int(data.get("timeout_sec", 1800)),
            max_turns=(None if data.get("max_turns") is None else int(data.get("max_turns"))),
            max_budget_usd=(
                None if data.get("max_budget_usd") is None else float(data.get("max_budget_usd"))
            ),
            extra_args=[str(x) for x in data.get("extra_args", [])],
            env={str(k): str(v) for k, v in dict(data.get("env", {})).items()},
            disable_bare=bool(data.get("disable_bare", False)),
            skip_git_repo_check=bool(data.get("skip_git_repo_check", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidatorConfig:
    name: str
    run: str
    timeout_sec: int = 600
    required: bool = True
    shell: str = "/bin/bash"
    run_when: str = "patch_only"
    requires_paths: list[str] = field(default_factory=list)
    on_missing_surface: str = "fail"
    required_binaries: list[str] = field(default_factory=list)
    on_missing_binary: str = "fail"

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, default_run_when: str = "patch_only") -> "ValidatorConfig":
        run_when = str(data.get("run_when", default_run_when)).strip().lower()
        if run_when not in VALID_VALIDATOR_RUN_WHEN:
            raise ValueError(
                "validators[].run_when must be one of: "
                + ", ".join(sorted(VALID_VALIDATOR_RUN_WHEN))
            )
        on_missing_surface = str(data.get("on_missing_surface", "fail")).strip().lower()
        if on_missing_surface not in VALID_MISSING_HANDLING:
            raise ValueError(
                "validators[].on_missing_surface must be one of: "
                + ", ".join(sorted(VALID_MISSING_HANDLING))
            )
        on_missing_binary = str(data.get("on_missing_binary", "fail")).strip().lower()
        if on_missing_binary not in VALID_MISSING_HANDLING:
            raise ValueError(
                "validators[].on_missing_binary must be one of: "
                + ", ".join(sorted(VALID_MISSING_HANDLING))
            )
        return cls(
            name=str(data["name"]),
            run=str(data["run"]),
            timeout_sec=int(data.get("timeout_sec", 600)),
            required=bool(data.get("required", True)),
            shell=str(data.get("shell", "/bin/bash")),
            run_when=run_when,
            requires_paths=[str(x) for x in data.get("requires_paths", [])],
            on_missing_surface=on_missing_surface,
            required_binaries=[str(x) for x in data.get("required_binaries", [])],
            on_missing_binary=on_missing_binary,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewLoopPolicy:
    min_loops: int = 0
    max_loops: int = 0
    always_run_first_revision: bool = False
    max_open_medium_issues: Optional[int] = None
    min_grounding_score: Optional[float] = None
    min_actionability_score: Optional[float] = None
    min_scope_compliance_score: Optional[float] = None

    @classmethod
    def defaults_for_strategy_kind(cls, strategy_kind: str) -> "ReviewLoopPolicy":
        if is_analysis_review_strategy_kind(strategy_kind):
            return cls(
                min_loops=1,
                max_loops=3,
                always_run_first_revision=True,
                max_open_medium_issues=0,
                min_grounding_score=0.80,
                min_actionability_score=0.75,
                min_scope_compliance_score=0.85,
            )
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, strategy_kind: str) -> "ReviewLoopPolicy":
        defaults = cls.defaults_for_strategy_kind(strategy_kind)
        if data is None:
            return defaults
        if not isinstance(data, dict):
            raise ValueError("review_loops must be a mapping when provided.")
        stop_when = dict(data.get("stop_when", {}))
        policy = cls(
            min_loops=int(data.get("min_loops", defaults.min_loops)),
            max_loops=int(data.get("max_loops", defaults.max_loops)),
            always_run_first_revision=bool(
                data.get("always_run_first_revision", defaults.always_run_first_revision)
            ),
            max_open_medium_issues=(
                defaults.max_open_medium_issues
                if stop_when.get("max_open_medium_issues") is None
                else int(stop_when.get("max_open_medium_issues"))
            ),
            min_grounding_score=(
                defaults.min_grounding_score
                if stop_when.get("min_grounding_score") is None
                else float(stop_when.get("min_grounding_score"))
            ),
            min_actionability_score=(
                defaults.min_actionability_score
                if stop_when.get("min_actionability_score") is None
                else float(stop_when.get("min_actionability_score"))
            ),
            min_scope_compliance_score=(
                defaults.min_scope_compliance_score
                if stop_when.get("min_scope_compliance_score") is None
                else float(stop_when.get("min_scope_compliance_score"))
            ),
        )
        if policy.min_loops < 0 or policy.max_loops < 0:
            raise ValueError("review_loops min/max must be >= 0.")
        if policy.max_loops < policy.min_loops:
            raise ValueError("review_loops.max_loops must be >= review_loops.min_loops.")
        for field_name in (
            "min_grounding_score",
            "min_actionability_score",
            "min_scope_compliance_score",
        ):
            value = getattr(policy, field_name)
            if value is not None and not (0 <= value <= 1):
                raise ValueError(f"review_loops.stop_when.{field_name} must be between 0 and 1.")
        if policy.max_open_medium_issues is not None and policy.max_open_medium_issues < 0:
            raise ValueError("review_loops.stop_when.max_open_medium_issues must be >= 0.")
        return policy

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_loops": self.min_loops,
            "max_loops": self.max_loops,
            "always_run_first_revision": self.always_run_first_revision,
            "stop_when": {
                "max_open_medium_issues": self.max_open_medium_issues,
                "min_grounding_score": self.min_grounding_score,
                "min_actionability_score": self.min_actionability_score,
                "min_scope_compliance_score": self.min_scope_compliance_score,
            },
        }


@dataclass
class StrategyConfig:
    name: str
    kind: str
    roles: dict[str, RoleConfig]
    validators: list[ValidatorConfig] = field(default_factory=list)
    max_repair_loops: int = 1
    rerun_falsifier_after_patch: bool = True
    patch_on_inconclusive: bool = False
    prompt_preamble: str = ""
    review_loops: ReviewLoopPolicy = field(default_factory=ReviewLoopPolicy)
    focus_gate: StrategyFocusGateConfig | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrategyConfig":
        kind = str(data.get("kind") or "pfr_v1")
        roles = {str(name): RoleConfig.from_dict(cfg) for name, cfg in dict(data.get("roles", {})).items()}
        validators = [
            ValidatorConfig.from_dict(v, default_run_when="patch_only")
            for v in data.get("validators", [])
        ]
        return cls(
            name=str(data.get("name") or data.get("id") or "strategy"),
            kind=kind,
            roles=roles,
            validators=validators,
            max_repair_loops=int(data.get("max_repair_loops", 1)),
            rerun_falsifier_after_patch=bool(data.get("rerun_falsifier_after_patch", True)),
            patch_on_inconclusive=bool(data.get("patch_on_inconclusive", False)),
            prompt_preamble=str(data.get("prompt_preamble", "") or ""),
            review_loops=ReviewLoopPolicy.from_dict(data.get("review_loops"), strategy_kind=kind),
            focus_gate=StrategyFocusGateConfig.from_dict(data.get("focus_gate")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "roles": {name: cfg.to_dict() for name, cfg in self.roles.items()},
            "validators": [v.to_dict() for v in self.validators],
            "max_repair_loops": self.max_repair_loops,
            "rerun_falsifier_after_patch": self.rerun_falsifier_after_patch,
            "patch_on_inconclusive": self.patch_on_inconclusive,
            "prompt_preamble": self.prompt_preamble,
            "review_loops": self.review_loops.to_dict(),
            "focus_gate": None if self.focus_gate is None else asdict(self.focus_gate),
        }


@dataclass
class StageRequest:
    role_name: str
    role_config: RoleConfig
    prompt_text: str
    schema: dict[str, Any]
    cwd: str
    out_dir: str


@dataclass
class ProviderRun:
    role_name: str
    provider: str
    model: Optional[str]
    access: str
    ok: bool
    exit_code: int
    duration_sec: float
    cwd: str
    command: list[str]
    stdout_path: str
    stderr_path: str
    prompt_path: str
    schema_path: str
    output_path: Optional[str]
    raw_output_path: Optional[str] = None
    normalized_output_path: Optional[str] = None
    structured_output: Optional[dict[str, Any]] = None
    raw_meta: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    failure_kind: Optional[str] = None
    failure_summary: Optional[str] = None
    schema_validation_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationRun:
    name: str
    command: str
    required: bool
    status: str  # passed | failed | error | skipped | not_applicable
    ok: bool
    applicable: bool
    exit_code: Optional[int]
    duration_sec: float
    stdout_path: str
    stderr_path: str
    stdout_tail: str
    stderr_tail: str
    error: Optional[str] = None
    skip_reason: Optional[str] = None
    missing_paths: list[str] = field(default_factory=list)
    missing_binaries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
