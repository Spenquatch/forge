from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_m2_focus_gate_live_acceptance.py"
CANONICAL_SCRIPT_PATH = REPO_ROOT / "scripts" / "run_focus_gate_acceptance.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SHIM = _load_module("run_m2_focus_gate_live_acceptance", SCRIPT_PATH)
CANONICAL = _load_module("run_focus_gate_acceptance", CANONICAL_SCRIPT_PATH)


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_m2_helper_is_an_explicit_compatibility_shim(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def _fake_main(argv=None, *, default_config_path):
        recorded["argv"] = argv
        recorded["default_config_path"] = default_config_path
        return 17

    monkeypatch.setattr(SHIM._CANONICAL, "main", _fake_main)

    exit_code = SHIM.main(["--workspace", "/tmp/example"])

    assert exit_code == 17
    assert recorded["argv"] == ["--workspace", "/tmp/example"]
    assert recorded["default_config_path"] == CANONICAL.LEGACY_DEFAULT_CONFIG_PATH


def test_m2_helper_exports_legacy_default_surface() -> None:
    assert SHIM.DEFAULT_CONFIG_PATH == CANONICAL.LEGACY_DEFAULT_CONFIG_PATH
    assert SHIM.DEFAULT_OUT_ROOT == CANONICAL.DEFAULT_OUT_ROOT
    assert SHIM.EXAMPLE_TASK_PATH == CANONICAL.EXAMPLE_TASK_PATH
    assert SHIM.EXAMPLE_STRATEGIES == CANONICAL.EXAMPLE_STRATEGIES
    assert SHIM.LEGACY_SCENARIO_DEFAULTS == CANONICAL.LEGACY_SCENARIO_DEFAULTS


def test_m2_helper_load_manifest_config_keeps_legacy_strategy_shorthand(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest_path = tmp_path / "m2_focus_gate_local.yaml"
    _write_manifest(
        manifest_path,
        {
            "task": SHIM.EXAMPLE_TASK_PATH,
            "workspace": str(workspace),
            "out_root": ".forge-harness-runs-live",
            "strategies": dict(SHIM.EXAMPLE_STRATEGIES),
        },
    )

    manifest = SHIM.load_manifest_config(manifest_path)

    assert [scenario.name for scenario in manifest.scenarios] == ["bounded", "trust"]
    assert all(scenario.expected_gate_path == "adjudicate" for scenario in manifest.scenarios)
    assert all(scenario.expected_focus_type == "seam" for scenario in manifest.scenarios)
    assert all(scenario.expected_decision_state == "selected" for scenario in manifest.scenarios)
