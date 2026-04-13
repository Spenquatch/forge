#!/usr/bin/env python
"""
Forge setup verification script (offline by default).

Usage:
  poetry run python scripts/test_setup.py
  poetry run python scripts/test_setup.py --online
  poetry run python scripts/test_setup.py --skip-pytest
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _print_step(title: str) -> None:
    print(f"\n== {title} ==")


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True)
    return int(proc.returncode)


def _check_python_version() -> bool:
    _print_step("Python Version")
    v = sys.version_info
    print(f"Python: {v.major}.{v.minor}.{v.micro}")
    ok = (v.major, v.minor) >= (3, 10) and (v.major, v.minor) < (3, 12)
    if not ok:
        print("FAIL: supported range is >=3.10,<3.12 (see pyproject.toml).")
    else:
        print("OK")
    return ok


def _check_config_exists() -> bool:
    _print_step("Config Files")
    cfg = REPO_ROOT / "config" / "models.yaml"
    if not cfg.exists():
        print(f"FAIL: missing `{cfg.relative_to(REPO_ROOT)}`")
        return False
    print(f"OK: found `{cfg.relative_to(REPO_ROOT)}`")
    return True


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Missing dependency PyYAML; run `poetry install`.") from e

    data = yaml.safe_load(path.read_text())
    return data or {}


def _check_env_vars(config: dict[str, Any], *, require_keys: bool) -> bool:
    _print_step("Environment Variables")
    providers = (config.get("providers") or {}) if isinstance(config, dict) else {}
    ok = True
    for name, p in providers.items():
        if not isinstance(p, dict):
            continue
        key_env = p.get("key_env")
        if not key_env:
            continue
        present = bool(os.getenv(str(key_env)))
        if present:
            print(f"OK: {name} key `{key_env}` is set")
        else:
            msg = f"MISSING: {name} key `{key_env}` is not set"
            if require_keys:
                print(f"FAIL: {msg}")
                ok = False
            else:
                print(f"WARN: {msg} (provider tests will fail until set)")
    return ok


def _check_local_model_paths(config: dict[str, Any]) -> bool:
    _print_step("Local Model Paths")
    providers = (config.get("providers") or {}) if isinstance(config, dict) else {}
    ok = True
    for name, p in providers.items():
        if not isinstance(p, dict):
            continue
        p_type = (p.get("type") or "").lower()
        framework = (p.get("framework") or "").lower()
        model_name = p.get("model_name")
        model_path = p.get("model_path")

        if p_type != "local":
            continue

        if framework == "transformers" and isinstance(model_name, str):
            # If model_name looks like a local path, validate it exists.
            if any(sep in model_name for sep in ("/", "\\")):
                candidate = (
                    (REPO_ROOT / model_name).resolve()
                    if not Path(model_name).is_absolute()
                    else Path(model_name)
                )
                if candidate.exists():
                    print(f"OK: {name} model path exists: `{candidate}`")
                else:
                    print(
                        f"WARN: {name} model path does not exist: `{candidate}` (might be a remote HF id)"
                    )
        elif framework == "llama_cpp" and isinstance(model_path, str):
            candidate = (
                (REPO_ROOT / model_path).resolve()
                if not Path(model_path).is_absolute()
                else Path(model_path)
            )
            if candidate.exists():
                print(f"OK: {name} model file exists: `{candidate}`")
            else:
                print(f"FAIL: {name} model file does not exist: `{candidate}`")
                ok = False

    return ok


def _validate_config() -> bool:
    _print_step("Config Validation")
    try:
        from anvil.config_validator import (  # type: ignore
            get_config_validator,
            validate_config,
        )
        from anvil.orchestrator import reload_config  # type: ignore
    except Exception as e:
        print(f"FAIL: unable to import Forge modules: {e}")
        return False

    providers_cfg, _ = reload_config()
    _ = get_config_validator()
    report = validate_config(providers_cfg)
    if not report.is_valid:
        print("FAIL: configuration validation failed")
        print(report.format_report())
        return False
    if report.has_warnings:
        print("WARN: configuration validation has warnings")
        print(report.format_report())
        return True
    print("OK")
    return True


def _run_anvil_list() -> bool:
    _print_step("CLI Smoke Check: `poetry run python -m anvil list`")
    rc = _run([sys.executable, "-m", "anvil", "list"], cwd=REPO_ROOT)
    if rc != 0:
        print(f"FAIL: command exited with {rc}")
        return False
    print("OK")
    return True


def _run_offline_pytest() -> bool:
    _print_step("Offline Tests: pytest smoke")
    try:
        import pytest  # type: ignore  # noqa: F401
    except Exception:
        print("SKIP: pytest not available in this environment")
        return True

    test_path = REPO_ROOT / "tests" / "test_lg_offline_smoke.py"
    if not test_path.exists():
        print(f"SKIP: missing `{test_path.relative_to(REPO_ROOT)}`")
        return True

    rc = _run([sys.executable, "-m", "pytest", "-q", str(test_path)], cwd=REPO_ROOT)
    if rc != 0:
        print(f"FAIL: pytest exited with {rc}")
        return False
    print("OK")
    return True


def _run_online_provider_tests(config: dict[str, Any]) -> bool:
    _print_step("Online Provider Smoke Tests (optional)")
    providers = (config.get("providers") or {}) if isinstance(config, dict) else {}
    names = [k for k in providers.keys() if isinstance(k, str)]
    if not names:
        print("SKIP: no configured providers found")
        return True

    ok = True
    for name in names:
        print(f"\n-- `poetry run python -m anvil test {name}` --")
        rc = _run([sys.executable, "-m", "anvil", "test", name], cwd=REPO_ROOT)
        if rc != 0:
            ok = False
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Forge environment and setup (offline by default)."
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Also run `poetry run python -m anvil test <provider>` for configured providers.",
    )
    parser.add_argument(
        "--skip-pytest", action="store_true", help="Skip offline pytest smoke test."
    )
    parser.add_argument(
        "--require-keys",
        action="store_true",
        help="Fail if required provider API keys are missing.",
    )
    args = parser.parse_args()

    overall_ok = True

    overall_ok &= _check_python_version()
    overall_ok &= _check_config_exists()

    config = _load_yaml(REPO_ROOT / "config" / "models.yaml")
    overall_ok &= _check_env_vars(config, require_keys=bool(args.require_keys))
    overall_ok &= _check_local_model_paths(config)
    overall_ok &= _validate_config()
    overall_ok &= _run_anvil_list()

    if not args.skip_pytest:
        overall_ok &= _run_offline_pytest()

    if args.online:
        overall_ok &= _run_online_provider_tests(config)

    print("\n" + "=" * 60)
    if overall_ok:
        print("✅ SETUP OK")
        return 0
    print("❌ SETUP FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
