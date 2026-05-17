import importlib
import os
from pathlib import Path

from anvil.config_loader import ProviderCfg
from anvil.config_validator import ConfigurationValidator, ValidationLevel


def _write_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def test_missing_optional_dependency_is_warning_not_error(
    monkeypatch,
) -> None:
    validator = ConfigurationValidator()
    cfg = ProviderCfg(
        type="api",
        class_path="anvil.providers.openai.OpenAIProvider",
        key_env="OPENAI_API_KEY",
        model_name="gpt-4o-mini",
        models={"gpt-4o-mini/*": {}},
    )

    real_import_module = importlib.import_module

    def fake_import_module(name: str, package=None):
        if name == "anvil.providers.openai":
            raise ImportError(
                "No module named 'langchain_openai'", name="langchain_openai"
            )
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    result = validator._validate_dependencies("openai", cfg)

    assert result.level == ValidationLevel.WARNING
    assert "Missing dependencies" in result.message


def test_missing_cli_binary_is_warning() -> None:
    validator = ConfigurationValidator()
    cfg = ProviderCfg(
        type="cli",
        class_path="anvil.providers.codex_cli.CodexCliProvider",
        binary="definitely-not-a-real-codex-binary",
        model_name="gpt-5-codex",
        models={"gpt-5-codex/*": {}},
    )

    result = validator._validate_cli_config("codex_cli", cfg)

    assert result is not None
    assert result.level == ValidationLevel.WARNING
    assert result.field == "binary"


def test_provider_readiness_ready_cli_binary_exists(
    tmp_path: Path, monkeypatch
) -> None:
    binary_path = tmp_path / "codex"
    _write_executable(binary_path)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH', '')}")

    validator = ConfigurationValidator()
    cfg = ProviderCfg(
        type="cli",
        class_path="pathlib.Path",
        binary="codex",
        model_name="gpt-5-codex",
        models={"gpt-5-codex/*": {}},
    )

    readiness = validator.get_provider_readiness("codex_cli", cfg)

    assert readiness.ready is True
    assert readiness.status == "ready"
    assert readiness.missing_items == []


def test_provider_readiness_cli_binary_missing() -> None:
    validator = ConfigurationValidator()
    cfg = ProviderCfg(
        type="cli",
        class_path="pathlib.Path",
        binary="definitely-not-a-real-codex-binary",
        model_name="gpt-5-codex",
        models={"gpt-5-codex/*": {}},
    )

    readiness = validator.get_provider_readiness("codex_cli", cfg)

    assert readiness.ready is False
    assert readiness.missing_items == [
        "binary 'definitely-not-a-real-codex-binary' not found on PATH"
    ]


def test_provider_readiness_api_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    validator = ConfigurationValidator()
    cfg = ProviderCfg(
        type="api",
        class_path="pathlib.Path",
        key_env="OPENAI_API_KEY",
        model_name="gpt-4o-mini",
        models={"gpt-4o-mini/*": {}},
    )

    readiness = validator.get_provider_readiness("openai", cfg)

    assert readiness.ready is False
    assert readiness.missing_items == ["API key env OPENAI_API_KEY not set"]


def test_provider_readiness_api_key_env_not_configured() -> None:
    validator = ConfigurationValidator()
    cfg = ProviderCfg(
        type="api",
        class_path="pathlib.Path",
        model_name="gpt-4o-mini",
        models={"gpt-4o-mini/*": {}},
    )

    readiness = validator.get_provider_readiness("openai", cfg)

    assert readiness.ready is False
    assert readiness.missing_items == ["key_env not configured"]


def test_provider_readiness_optional_dependency_reports_missing_item(
    monkeypatch,
) -> None:
    validator = ConfigurationValidator()
    cfg = ProviderCfg(
        type="api",
        class_path="anvil.providers.openai.OpenAIProvider",
        key_env="OPENAI_API_KEY",
        model_name="gpt-4o-mini",
        models={"gpt-4o-mini/*": {}},
    )

    real_import_module = importlib.import_module

    def fake_import_module(name: str, package=None):
        if name == "anvil.providers.openai":
            raise ImportError(
                "No module named 'langchain_openai'", name="langchain_openai"
            )
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    readiness = validator.get_provider_readiness("openai", cfg)

    assert readiness.ready is False
    assert readiness.missing_items == [
        "provider dependency langchain_openai not installed",
        "API key env OPENAI_API_KEY not set",
    ]


def test_provider_readiness_llama_cpp_model_path_not_configured() -> None:
    validator = ConfigurationValidator()
    cfg = ProviderCfg(
        type="local",
        framework="llama_cpp",
        class_path="pathlib.Path",
        models={"default/*": {}},
    )

    readiness = validator.get_provider_readiness("qwen3-gguf", cfg)

    assert readiness.ready is False
    assert readiness.missing_items == ["model_path not configured"]


def test_provider_readiness_llama_cpp_model_file_missing() -> None:
    validator = ConfigurationValidator()
    cfg = ProviderCfg(
        type="local",
        framework="llama_cpp",
        class_path="pathlib.Path",
        model_path="models/gguf/missing.gguf",
        models={"default/*": {}},
    )

    readiness = validator.get_provider_readiness("qwen3-gguf", cfg)

    assert readiness.ready is False
    assert readiness.missing_items == ["model file models/gguf/missing.gguf not found"]


def test_provider_readiness_transformers_local_model_missing() -> None:
    validator = ConfigurationValidator()
    cfg = ProviderCfg(
        type="local",
        framework="transformers",
        class_path="pathlib.Path",
        model_name="models/hf/missing-model",
        models={"default/*": {}},
    )

    readiness = validator.get_provider_readiness("phi3-mini", cfg)

    assert readiness.ready is False
    assert readiness.missing_items == ["model file models/hf/missing-model not found"]


def test_provider_readiness_transformers_remote_model_id_is_not_missing() -> None:
    validator = ConfigurationValidator()
    cfg = ProviderCfg(
        type="local",
        framework="transformers",
        class_path="pathlib.Path",
        model_name="microsoft/Phi-3-mini-4k-instruct",
        models={"default/*": {}},
    )

    readiness = validator.get_provider_readiness("phi3-mini", cfg)

    assert readiness.ready is True
    assert readiness.status == "ready"
