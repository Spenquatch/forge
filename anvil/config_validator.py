# anvil/config_validator.py
"""
Advanced Configuration Validation System for AI/ML Pipelines.

Follows industry best practices:
- Schema-based validation with Pydantic
- Validation chains for complex rules
- Runtime validation for hot-swapping
- Clear error reporting with suggestions
- Performance validation
- Security validation
"""

import importlib
import logging
import os
import re
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)
CLASS_PATH_PATTERN = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*\.)*[a-zA-Z_][a-zA-Z0-9_]*$")


class ValidationLevel(Enum):
    """Validation severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationType(Enum):
    """Types of validation checks."""

    SCHEMA = "schema"
    DEPENDENCY = "dependency"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPATIBILITY = "compatibility"
    RUNTIME = "runtime"


@dataclass
class ValidationResult:
    """Result of a validation check."""

    valid: bool
    level: ValidationLevel
    validation_type: ValidationType
    message: str
    component: str
    field: Optional[str] = None
    suggestion: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        location = f"{self.component}.{self.field}" if self.field else self.component
        return f"[{self.level.value.upper()}] {location}: {self.message}"


class ValidationReport:
    """Comprehensive validation report."""

    def __init__(self) -> None:
        self.results: List[ValidationResult] = []
        self.timestamp: Optional[float] = None
        self._stats: Dict[ValidationLevel, int] = {
            level: 0 for level in ValidationLevel
        }

    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result."""
        self.results.append(result)
        self._stats[result.level] += 1

    @property
    def is_valid(self) -> bool:
        """Check if overall validation passed (no errors or critical issues)."""
        return (
            self._stats[ValidationLevel.ERROR] == 0
            and self._stats[ValidationLevel.CRITICAL] == 0
        )

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return self._stats[ValidationLevel.WARNING] > 0

    def get_results_by_level(self, level: ValidationLevel) -> List[ValidationResult]:
        """Get results filtered by severity level."""
        return [r for r in self.results if r.level == level]

    def get_summary(self) -> Dict[str, Any]:
        """Get validation summary statistics."""
        return {
            "total_checks": len(self.results),
            "passed": self.is_valid,
            "has_warnings": self.has_warnings,
            "stats": dict(self._stats),
            "critical_issues": self._stats[ValidationLevel.CRITICAL],
            "errors": self._stats[ValidationLevel.ERROR],
            "warnings": self._stats[ValidationLevel.WARNING],
            "info": self._stats[ValidationLevel.INFO],
        }

    def format_report(self, include_info: bool = False) -> str:
        """Format validation report as human-readable text."""
        lines = ["=" * 60, "CONFIGURATION VALIDATION REPORT", "=" * 60]

        summary = self.get_summary()
        lines.append(f"Status: {'✅ PASSED' if summary['passed'] else '❌ FAILED'}")
        lines.append(f"Total Checks: {summary['total_checks']}")
        lines.append(
            f"Critical: {summary['critical_issues']}, Errors: {summary['errors']}, "
            f"Warnings: {summary['warnings']}, Info: {summary['info']}"
        )
        lines.append("")

        # Group results by level
        for level in [
            ValidationLevel.CRITICAL,
            ValidationLevel.ERROR,
            ValidationLevel.WARNING,
        ]:
            level_results = self.get_results_by_level(level)
            if level_results:
                lines.append(f"{level.value.upper()} ISSUES:")
                lines.append("-" * 40)
                for result in level_results:
                    lines.append(f"  • {result}")
                    if result.suggestion:
                        lines.append(f"    💡 Suggestion: {result.suggestion}")
                lines.append("")

        return "\\n".join(lines)


@dataclass
class ProviderReadiness:
    """Normalized readiness summary for one configured provider."""

    missing_items: List[str]

    @property
    def ready(self) -> bool:
        return not self.missing_items

    @property
    def status(self) -> str:
        if self.ready:
            return "ready"
        return f"missing {'; '.join(self.missing_items)}"


class ConfigurationValidator:
    """
    Advanced configuration validation system.

    Features:
    - Schema validation
    - Dependency validation
    - Performance validation
    - Security validation
    - Runtime validation for hot-swapping
    - Custom validation rules
    """

    def __init__(self):
        """Initialize the configuration validator."""
        self.custom_validators: List[Callable] = []
        self.dependency_cache: Dict[str, Dict[str, Any]] = {}

        logger.info("Configuration validator initialized")

    def validate_provider_config(self, name: str, config) -> ValidationReport:
        """
        Comprehensive validation of a provider configuration.

        Args:
            name: Provider name
            config: Provider configuration

        Returns:
            ValidationReport with all validation results
        """
        report = ValidationReport()

        # Basic validation
        report.add_result(self._validate_basic_config(name, config))

        # Dependency validation
        report.add_result(self._validate_dependencies(name, config))

        # CLI runtime validation
        cli_result = self._validate_cli_config(name, config)
        if cli_result:
            report.add_result(cli_result)

        # Model configuration validation
        if hasattr(config, "models") and config.models:
            for model_key, model_config in config.models.items():
                if isinstance(model_config, dict):
                    result = self._validate_model_config(name, model_key, model_config)
                    if result:
                        report.add_result(result)

        # Security validation
        sec_result = self._validate_security_config(name, config)
        if sec_result:
            report.add_result(sec_result)

        logger.debug(
            f"Validated provider config: {name} - {'✅' if report.is_valid else '❌'}"
        )
        return report

    def validate_runtime_overrides(self, overrides: Dict[str, Any]) -> ValidationReport:
        """
        Validate runtime configuration overrides.

        Args:
            overrides: Runtime override configuration

        Returns:
            ValidationReport with validation results
        """
        report = ValidationReport()

        for key, value in overrides.items():
            # Validate role-specific overrides
            if isinstance(value, dict):
                for param_name, param_value in value.items():
                    result = self._validate_parameter(key, param_name, param_value)
                    if result:
                        report.add_result(result)
            else:
                # Validate top-level overrides
                result = self._validate_parameter("runtime", key, value)
                if result:
                    report.add_result(result)

        logger.debug(
            f"Validated runtime overrides - {'✅' if report.is_valid else '❌'}"
        )
        return report

    def _validate_basic_config(self, name: str, config) -> ValidationResult:
        """Validate basic configuration structure."""
        try:
            # Check required attributes
            required_attrs = ["type", "class_path"]
            missing_attrs = []

            for attr in required_attrs:
                if not hasattr(config, attr) or not getattr(config, attr):
                    missing_attrs.append(attr)

            if missing_attrs:
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.SCHEMA,
                    message=f"Missing required attributes: {', '.join(missing_attrs)}",
                    component=name,
                    suggestion="Ensure all required configuration fields are present",
                )

            # Validate class path format
            class_path = getattr(config, "class_path", "")
            if not CLASS_PATH_PATTERN.match(class_path):
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.SCHEMA,
                    message="Invalid class path format",
                    component=name,
                    field="class_path",
                    suggestion="Use format like 'module.submodule.ClassName'",
                )

            return ValidationResult(
                valid=True,
                level=ValidationLevel.INFO,
                validation_type=ValidationType.SCHEMA,
                message="Basic configuration valid",
                component=name,
            )

        except Exception as e:
            return ValidationResult(
                valid=False,
                level=ValidationLevel.ERROR,
                validation_type=ValidationType.SCHEMA,
                message=f"Configuration validation error: {str(e)}",
                component=name,
            )

    def _validate_dependencies(self, name: str, config) -> ValidationResult:
        """Validate that required dependencies are available."""
        status = self._get_dependency_status(config)
        return ValidationResult(
            valid=bool(status["valid"]),
            level=status["level"],
            validation_type=ValidationType.DEPENDENCY,
            message=status["message"],
            component=name,
            suggestion=status.get("suggestion"),
            metadata=status.get("metadata"),
        )

    def get_provider_readiness(self, name: str, config) -> ProviderReadiness:
        """Return normalized missing prerequisites for a provider."""
        dependency_items: List[str] = []
        auth_items: List[str] = []
        binary_items: List[str] = []
        local_model_items: List[str] = []
        other_items: List[str] = []
        seen: set[str] = set()

        provider_type = str(getattr(config, "type", "") or "").lower()
        class_path = str(getattr(config, "class_path", "") or "")

        if not provider_type:
            self._append_missing(other_items, seen, "type not configured")

        if not class_path:
            self._append_missing(dependency_items, seen, "class_path not configured")
        elif not CLASS_PATH_PATTERN.match(class_path):
            self._append_missing(dependency_items, seen, "invalid class_path format")
        else:
            dependency_issue = self._normalize_dependency_issue(
                self._validate_dependencies(name, config)
            )
            if dependency_issue:
                self._append_missing(dependency_items, seen, dependency_issue)

        if provider_type == "api":
            key_env = str(getattr(config, "key_env", "") or "")
            if not key_env:
                self._append_missing(auth_items, seen, "key_env not configured")
            elif not os.getenv(key_env):
                self._append_missing(auth_items, seen, f"API key env {key_env} not set")

        if provider_type == "cli":
            binary_name = self._resolve_cli_binary_name(name, config)
            if not binary_name:
                self._append_missing(binary_items, seen, "binary not configured")
            elif shutil.which(binary_name) is None:
                self._append_missing(
                    binary_items, seen, f"binary '{binary_name}' not found on PATH"
                )

        framework = str(getattr(config, "framework", "") or "").lower()
        if framework == "llama_cpp":
            model_path = str(getattr(config, "model_path", "") or "")
            if not model_path:
                self._append_missing(
                    local_model_items, seen, "model_path not configured"
                )
            elif not Path(os.path.expanduser(model_path)).exists():
                self._append_missing(
                    local_model_items, seen, f"model file {model_path} not found"
                )
        elif framework == "transformers":
            model_name = str(getattr(config, "model_name", "") or "")
            if not model_name:
                self._append_missing(
                    local_model_items, seen, "model_name not configured"
                )
            elif self._looks_like_local_model_reference(model_name):
                expanded = os.path.expanduser(model_name)
                if not Path(expanded).exists():
                    self._append_missing(
                        local_model_items,
                        seen,
                        f"model file {model_name} not found",
                    )

        return ProviderReadiness(
            missing_items=dependency_items
            + auth_items
            + binary_items
            + local_model_items
            + other_items
        )

    def _get_dependency_status(self, config) -> Dict[str, Any]:
        """Inspect provider import/dependency status without instantiating it."""
        class_path = getattr(config, "class_path", "")
        if not class_path:
            return {
                "valid": False,
                "level": ValidationLevel.ERROR,
                "message": "No class path specified",
                "metadata": {"status": "missing_class_path"},
            }

        try:
            module_path, cls_name = class_path.rsplit(".", 1)
        except ValueError:
            return {
                "valid": False,
                "level": ValidationLevel.ERROR,
                "message": "Invalid class path format",
                "metadata": {"status": "invalid_class_path"},
            }

        cached = self.dependency_cache.get(class_path)
        if cached is not None:
            return cached

        try:
            module = importlib.import_module(module_path)
            _ = getattr(module, cls_name)
            status = {
                "valid": True,
                "level": ValidationLevel.INFO,
                "message": "All dependencies available",
                "metadata": {
                    "status": "available",
                    "provider_module": module_path,
                    "class_name": cls_name,
                },
            }
        except ImportError as e:
            missing_name = getattr(e, "name", "") or ""
            is_provider_module_missing = missing_name in {
                module_path,
                module_path.split(".")[0],
            }
            level = (
                ValidationLevel.ERROR
                if is_provider_module_missing
                else ValidationLevel.WARNING
            )
            status = {
                "valid": False,
                "level": level,
                "message": f"Missing dependencies: {str(e)}",
                "suggestion": self._get_dependency_suggestion(str(e)),
                "metadata": {
                    "status": (
                        "missing_provider_module"
                        if is_provider_module_missing
                        else "missing_dependency"
                    ),
                    "missing_module": missing_name,
                    "provider_module": module_path,
                    "class_name": cls_name,
                },
            }
        except AttributeError:
            status = {
                "valid": False,
                "level": ValidationLevel.ERROR,
                "message": f"Class {cls_name} not found in {module_path}",
                "suggestion": "Check class name and module path",
                "metadata": {
                    "status": "missing_class",
                    "provider_module": module_path,
                    "class_name": cls_name,
                },
            }

        self.dependency_cache[class_path] = status
        return status

    def _normalize_dependency_issue(self, result: ValidationResult) -> Optional[str]:
        """Convert dependency validation failures into stable readiness text."""
        if result.valid or result.level == ValidationLevel.INFO:
            return None

        metadata = result.metadata or {}
        status = metadata.get("status")
        missing_module = metadata.get("missing_module")
        provider_module = metadata.get("provider_module")
        class_name = metadata.get("class_name")

        if status == "missing_dependency" and missing_module:
            return f"provider dependency {missing_module} not installed"
        if status == "missing_provider_module" and provider_module:
            return f"provider module {provider_module} not installed"
        if status == "missing_class" and class_name:
            return f"provider class {class_name} not found"
        if status == "missing_class_path":
            return "class_path not configured"
        if status == "invalid_class_path":
            return "invalid class_path format"

        return result.message

    def _resolve_cli_binary_name(self, name: str, config) -> str:
        """Resolve the effective CLI binary name using runtime precedence."""
        if name == "codex_cli":
            return os.getenv("FORGE_CODEX_BIN", "") or str(
                getattr(config, "binary", "") or ""
            )
        if name == "claude_code":
            return os.getenv("FORGE_CLAUDE_BIN", "") or str(
                getattr(config, "binary", "") or ""
            )
        return str(getattr(config, "binary", "") or "")

    def _looks_like_local_model_reference(self, model_name: str) -> bool:
        """Heuristic to distinguish local model paths from remote model IDs."""
        expanded = os.path.expanduser(model_name)
        if Path(expanded).exists():
            return True

        if model_name.startswith(("/", "./", "../", "~")):
            return True
        if model_name.startswith("models/"):
            return True
        if "\\" in model_name or re.match(r"^[A-Za-z]:[\\\\/]", model_name):
            return True

        return False

    def _append_missing(
        self, items: List[str], seen: set[str], item: Optional[str]
    ) -> None:
        """Append a missing-item label once while preserving order."""
        if not item or item in seen:
            return
        seen.add(item)
        items.append(item)

    def _validate_cli_config(self, name: str, config) -> Optional[ValidationResult]:
        """Validate CLI-provider-specific settings."""
        if str(getattr(config, "type", "")).lower() != "cli":
            return None

        binary = getattr(config, "binary", None)
        if not binary:
            return ValidationResult(
                valid=False,
                level=ValidationLevel.WARNING,
                validation_type=ValidationType.COMPATIBILITY,
                message="CLI provider has no binary configured",
                component=name,
                field="binary",
                suggestion="Set the provider binary path or rely on FORGE_CODEX_BIN / FORGE_CLAUDE_BIN.",
            )

        if shutil.which(str(binary)) is None:
            return ValidationResult(
                valid=False,
                level=ValidationLevel.WARNING,
                validation_type=ValidationType.COMPATIBILITY,
                message=f"CLI binary '{binary}' was not found on PATH",
                component=name,
                field="binary",
                suggestion="Install the CLI or point ProviderCfg.binary / FORGE_*_BIN at the executable.",
            )

        return ValidationResult(
            valid=True,
            level=ValidationLevel.INFO,
            validation_type=ValidationType.COMPATIBILITY,
            message=f"CLI binary '{binary}' resolved on PATH",
            component=name,
            field="binary",
        )

    def _validate_model_config(
        self, provider_name: str, model_key: str, model_config: Dict[str, Any]
    ) -> Optional[ValidationResult]:
        """Validate model-specific configuration."""
        issues = []

        # Common parameter validations
        for param, value in model_config.items():
            if param == "temperature" and isinstance(value, (int, float)):
                if not (0.0 <= value <= 2.0):
                    issues.append(f"temperature {value} outside valid range (0.0-2.0)")
            elif param == "max_tokens" and isinstance(value, int):
                if value <= 0 or value > 100000:
                    issues.append(
                        f"max_tokens {value} outside reasonable range (1-100000)"
                    )

        if issues:
            return ValidationResult(
                valid=False,
                level=ValidationLevel.WARNING,
                validation_type=ValidationType.SCHEMA,
                message=f"Model config issues in {model_key}: {'; '.join(issues)}",
                component=provider_name,
                field=model_key,
                suggestion="Check parameter ranges and types",
            )

        return None

    def _validate_security_config(
        self, name: str, config
    ) -> Optional[ValidationResult]:
        """Validate configuration for security issues."""
        issues = []

        # Check environment variable security
        key_env = getattr(config, "key_env", None)
        if key_env:
            env_value = os.getenv(key_env)
            if not env_value:
                issues.append(f"API key environment variable {key_env} not set")
            elif len(env_value) < 10:
                issues.append(f"API key in {key_env} appears too short")

        if issues:
            level = (
                ValidationLevel.CRITICAL
                if "not set" in str(issues)
                else ValidationLevel.WARNING
            )
            return ValidationResult(
                valid=level != ValidationLevel.CRITICAL,
                level=level,
                validation_type=ValidationType.SECURITY,
                message=f"Security issues: {'; '.join(issues)}",
                component=name,
                suggestion="Review API key configuration and security practices",
            )

        return None

    def _validate_parameter(
        self, context: str, param_name: str, param_value: Any
    ) -> Optional[ValidationResult]:
        """Validate individual parameter with detailed error reporting."""
        # Temperature validation
        if param_name == "temperature":
            if not isinstance(param_value, (int, float)):
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message=f"Invalid temperature type: {type(param_value).__name__} (expected float)",
                    component=context,
                    field=param_name,
                    suggestion="Temperature should be a float between 0.0 and 2.0",
                )
            elif not (0.0 <= param_value <= 2.0):
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message=f"Temperature {param_value} outside valid range [0.0, 2.0]",
                    component=context,
                    field=param_name,
                    suggestion="Temperature should be between 0.0 and 2.0",
                )

        # Max tokens validation
        elif param_name == "max_tokens":
            if not isinstance(param_value, int):
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message=f"Invalid max_tokens type: {type(param_value).__name__} (expected int)",
                    component=context,
                    field=param_name,
                    suggestion="max_tokens should be a positive integer",
                )
            elif param_value <= 0:
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message=f"max_tokens {param_value} must be positive",
                    component=context,
                    field=param_name,
                    suggestion="max_tokens should be a positive integer",
                )

        elif param_name == "access":
            if str(param_value) not in {"read", "write", "danger"}:
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message=f"Invalid access level: {param_value}",
                    component=context,
                    field=param_name,
                    suggestion="Use one of: read, write, danger",
                )

        elif param_name == "effort":
            if not isinstance(param_value, str):
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message=f"Invalid effort type: {type(param_value).__name__} (expected str)",
                    component=context,
                    field=param_name,
                    suggestion="Use a string effort level such as low/medium/high.",
                )

        elif param_name in {"timeout_sec", "max_turns"}:
            if not isinstance(param_value, int) or param_value <= 0:
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message=f"{param_name} must be a positive integer",
                    component=context,
                    field=param_name,
                    suggestion=f"Set {param_name} to a positive integer.",
                )

        elif param_name == "max_budget_usd":
            if not isinstance(param_value, (int, float)) or float(param_value) <= 0:
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message="max_budget_usd must be a positive number",
                    component=context,
                    field=param_name,
                    suggestion="Set max_budget_usd to a positive number of dollars.",
                )

        elif param_name in {"extra_args", "add_dirs"}:
            if not isinstance(param_value, list) or not all(
                isinstance(item, str) for item in param_value
            ):
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message=f"{param_name} must be a list of strings",
                    component=context,
                    field=param_name,
                    suggestion=f"Provide {param_name} as a YAML list of strings.",
                )

        elif param_name in {"skip_git_repo_check", "disable_bare"}:
            if not isinstance(param_value, bool):
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message=f"{param_name} must be a boolean",
                    component=context,
                    field=param_name,
                    suggestion=f"Set {param_name} to true or false.",
                )

        elif param_name in {
            "allowed_tools",
            "tools",
            "permission_mode",
            "approval_mode",
            "model",
        }:
            if not isinstance(param_value, str):
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message=f"{param_name} must be a string",
                    component=context,
                    field=param_name,
                    suggestion=f"Set {param_name} to a string value.",
                )

        elif param_name == "env":
            if not isinstance(param_value, dict) or not all(
                isinstance(k, str) for k in param_value.keys()
            ):
                return ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.RUNTIME,
                    message="env must be a mapping of string keys",
                    component=context,
                    field=param_name,
                    suggestion="Set env as a key/value mapping.",
                )

        # Check for unknown parameters
        elif param_name not in [
            "temperature",
            "max_tokens",
            "top_p",
            "top_k",
            "frequency_penalty",
            "presence_penalty",
            "access",
            "effort",
            "timeout_sec",
            "extra_args",
            "skip_git_repo_check",
            "disable_bare",
            "max_turns",
            "max_budget_usd",
            "add_dirs",
            "allowed_tools",
            "tools",
            "permission_mode",
            "approval_mode",
            "model",
            "env",
        ]:
            return ValidationResult(
                valid=False,
                level=ValidationLevel.WARNING,
                validation_type=ValidationType.RUNTIME,
                message=f"Unknown parameter: {param_name}",
                component=context,
                field=param_name,
                suggestion="Check parameter name spelling and documentation",
            )

        return None

    def _get_dependency_suggestion(self, error_message: str) -> str:
        """Get helpful suggestion based on dependency error."""
        suggestions = {
            "langchain_openai": 'poetry install --extras "openai"',
            "langchain_anthropic": 'poetry install --extras "anthropic"',
            "transformers": 'poetry install --extras "transformers"',
            "llama_cpp": 'poetry install --extras "llama-cpp"',
            "openai": 'poetry install --extras "openai"',
            "anthropic": 'poetry install --extras "anthropic"',
        }

        for package, suggestion in suggestions.items():
            if package in error_message:
                return suggestion

        return "Install missing dependencies with Poetry or check import paths"


# Global validator instance
_validator = ConfigurationValidator()


def get_config_validator() -> ConfigurationValidator:
    """Get the global configuration validator instance."""
    return _validator


def validate_config(providers: Dict[str, Any]) -> ValidationReport:
    """Convenience function to validate full configuration."""
    report = ValidationReport()

    for name, config in providers.items():
        provider_report = _validator.validate_provider_config(name, config)
        report.results.extend(provider_report.results)
        for level in ValidationLevel:
            report._stats[level] += provider_report._stats[level]

    return report
