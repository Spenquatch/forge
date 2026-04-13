from __future__ import annotations

import pytest

from anvil import config_loader
from anvil.harness import files as harness_files


def test_load_config_raises_helpful_error_when_pyyaml_missing(
    tmp_path, monkeypatch
) -> None:
    config_path = tmp_path / "models.yaml"
    config_path.write_text("providers: {}\n", encoding="utf-8")

    real_import_module = config_loader.importlib.import_module

    def fake_import_module(name: str, package=None):
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml'")
        return real_import_module(name, package)

    monkeypatch.setattr(config_loader.importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match="PyYAML is required"):
        config_loader.load_config(str(config_path))


def test_load_structured_file_raises_helpful_error_when_pyyaml_missing(
    tmp_path, monkeypatch
) -> None:
    task_path = tmp_path / "task.yaml"
    task_path.write_text("id: example\n", encoding="utf-8")

    real_import_module = harness_files.importlib.import_module

    def fake_import_module(name: str, package=None):
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml'")
        return real_import_module(name, package)

    monkeypatch.setattr(harness_files.importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match="PyYAML is required"):
        harness_files.load_structured_file(task_path)
