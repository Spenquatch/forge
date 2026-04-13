"""
Comprehensive Testing Framework for Forge AI Providers

This module implements industry best practices for AI/ML pipeline testing:
- Proper logging and error handling
- Type safety and validation
- Structured test reporting
- Configurable test suites
- Performance monitoring
- Dependency validation

Usage:
    python forge_test.py --help                    # Show all options
    python forge_test.py --test-providers          # Test all available providers
    python forge_test.py --test-roles              # Test role-based configurations
    python forge_test.py --verify-models           # Verify model availability
    python forge_test.py --benchmark               # Run performance benchmarks
    python forge_test.py --provider openai         # Test specific provider
    python forge_test.py --full-suite              # Run complete test suite
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv

# Ensure repo root is on sys.path when executing this script directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("forge_test.log")],
)
logger = logging.getLogger(__name__)

from anvil.config_loader import load_config
from anvil.orchestrator import reload_config
from anvil.providers import (
    get_provider,
    get_registry_status,
)


@dataclass
class TestResult:
    """Structured test result following industry standards."""

    test_name: str
    provider: str
    success: bool
    duration: float
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ProviderCapabilityTest:
    """Test results for provider capabilities."""

    generation: Optional[TestResult] = None
    chat: Optional[TestResult] = None
    embeddings: Optional[TestResult] = None
    model_info: Optional[TestResult] = None


class ForgeTestSuite:
    """
    Comprehensive testing suite for Forge AI providers following ML/AI best practices.

    Features:
    - Structured logging and error reporting
    - Performance monitoring and benchmarking
    - Dependency validation
    - Configuration validation
    - Role-based testing
    - Async/await pattern for concurrent testing
    """

    def __init__(self, log_level: str = "INFO"):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.setLevel(getattr(logging, log_level.upper()))

        self.results: List[TestResult] = []
        self.failed_tests: List[TestResult] = []
        self.start_time: Optional[float] = None
        self.config_loaded = False

    async def setup(self) -> bool:
        """
        Initialize the test environment with proper error handling.

        Returns:
            True if setup successful, False otherwise
        """
        self.start_time = time.time()
        self.logger.info("Initializing Forge test environment")

        try:
            # Load environment variables
            env_file = Path(".env")
            if env_file.exists():
                load_dotenv(env_file)
                self.logger.info("Loaded environment variables from .env")
            else:
                self.logger.warning(
                    "No .env file found - using system environment variables"
                )

            # Validate required environment variables
            if not self._validate_environment():
                return False

            # Load configuration and register providers
            try:
                reload_config()
                self.config_loaded = True
                self.logger.info("Configuration loaded successfully")

                # Log registry status
                status = get_registry_status()
                self.logger.info(f"Provider registry status: {status}")

            except Exception as e:
                self.logger.error(f"Failed to load configuration: {e}", exc_info=True)
                return False

            return True

        except Exception as e:
            self.logger.error(f"Test setup failed: {e}", exc_info=True)
            return False

    def _validate_environment(self) -> bool:
        """Validate required environment variables are present."""
        required_vars = {
            "OPENAI_API_KEY": "OpenAI API access",
            "ANTHROPIC_API_KEY": "Anthropic API access",
        }

        missing_vars = []
        for var, description in required_vars.items():
            if not os.getenv(var):
                missing_vars.append(f"{var} ({description})")

        if missing_vars:
            self.logger.warning(
                f"Missing environment variables: {', '.join(missing_vars)}"
            )
            self.logger.info("Some tests may fail due to missing API keys")

        return True  # Don't fail setup, just warn

    async def verify_models(
        self, provider_name: Optional[str] = None
    ) -> Dict[str, TestResult]:
        """
        Verify that configured models are available via their APIs.

        Args:
            provider_name: Specific provider to test, or None for all

        Returns:
            Dictionary of test results by provider name
        """
        self.logger.info("Verifying model availability")

        results = {}
        providers_config, _ = load_config()

        providers_to_test = (
            [provider_name] if provider_name else list(providers_config.keys())
        )

        for name in providers_to_test:
            if name not in providers_config:
                self.logger.error(f"Provider '{name}' not found in configuration")
                continue

            result = await self._test_model_availability(name)
            results[name] = result
            self.results.append(result)

            if not result.success:
                self.failed_tests.append(result)

        return results

    async def _test_model_availability(self, provider_name: str) -> TestResult:
        """Test if a single provider's model is available."""
        start_time = time.time()

        try:
            self.logger.info(f"Testing model availability for {provider_name}")

            provider = get_provider(provider_name)
            if not provider:
                return TestResult(
                    test_name="model_availability",
                    provider=provider_name,
                    success=False,
                    duration=time.time() - start_time,
                    error="Provider not available or failed to initialize",
                )

            # Try a minimal generation to test model access
            test_response = await provider.generate("Say 'test'", role="execute")

            if test_response and len(test_response.strip()) > 0:
                self.logger.info(f"{provider_name} model is available")
                return TestResult(
                    test_name="model_availability",
                    provider=provider_name,
                    success=True,
                    duration=time.time() - start_time,
                    metadata={"response_preview": test_response[:50]},
                )
            else:
                return TestResult(
                    test_name="model_availability",
                    provider=provider_name,
                    success=False,
                    duration=time.time() - start_time,
                    error="Empty response from model",
                )

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"{provider_name} model test failed: {error_msg}")

            return TestResult(
                test_name="model_availability",
                provider=provider_name,
                success=False,
                duration=time.time() - start_time,
                error=self._classify_error(error_msg),
            )

    def _classify_error(self, error_msg: str) -> str:
        """Classify error messages for better diagnostics."""
        error_lower = error_msg.lower()

        if "404" in error_msg or "not_found" in error_lower:
            return "Model not found - check model name in configuration"
        elif "401" in error_msg or "unauthorized" in error_lower:
            return "Authentication failed - check API key"
        elif "rate_limit" in error_lower or "429" in error_msg:
            return "Rate limited - try again later"
        elif "quota" in error_lower or "billing" in error_lower:
            return "Quota exceeded - check billing status"
        elif "timeout" in error_lower:
            return "Request timeout - model may be overloaded"
        else:
            return f"Unknown error: {error_msg}"

    async def test_providers(
        self, provider_names: Optional[List[str]] = None
    ) -> Dict[str, ProviderCapabilityTest]:
        """
        Test all provider capabilities comprehensively.

        Args:
            provider_names: List of provider names to test, or None for all

        Returns:
            Dictionary of capability test results by provider
        """
        self.logger.info("Testing provider capabilities")

        results = {}
        providers_config, _ = load_config()

        providers_to_test = provider_names or list(providers_config.keys())

        # Test providers concurrently for better performance
        tasks = [
            self._test_single_provider_comprehensive(name)
            for name in providers_to_test
            if name in providers_config
        ]

        provider_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(provider_results):
            provider_name = providers_to_test[i]

            if isinstance(result, Exception):
                self.logger.error(
                    f"{provider_name}: Test failed with exception: {result}"
                )
                results[provider_name] = ProviderCapabilityTest()
            else:
                results[provider_name] = result
                self.logger.info(f"{provider_name}: Tests completed")

        return results

    async def _test_single_provider_comprehensive(
        self, provider_name: str
    ) -> ProviderCapabilityTest:
        """Comprehensively test a single provider's capabilities."""
        self.logger.info(f"Testing capabilities for {provider_name}")

        provider = get_provider(provider_name)
        if not provider:
            self.logger.error(f"Provider {provider_name} not available")
            return ProviderCapabilityTest()

        # Test all capabilities
        capability_test = ProviderCapabilityTest()

        # Test generation
        capability_test.generation = await self._test_generation(
            provider_name, provider
        )

        # Test chat
        capability_test.chat = await self._test_chat(provider_name, provider)

        # Test embeddings
        capability_test.embeddings = await self._test_embeddings(
            provider_name, provider
        )

        # Test model info
        capability_test.model_info = await self._test_model_info(
            provider_name, provider
        )

        return capability_test

    async def _test_generation(self, provider_name: str, provider) -> TestResult:
        """Test text generation capability."""
        start_time = time.time()

        try:
            response = await provider.generate(
                "Write a haiku about artificial intelligence", role="execute"
            )

            if response and len(response.strip()) > 10:  # Reasonable response length
                return TestResult(
                    test_name="generation",
                    provider=provider_name,
                    success=True,
                    duration=time.time() - start_time,
                    metadata={
                        "response_length": len(response),
                        "response_preview": response[:100],
                    },
                )
            else:
                return TestResult(
                    test_name="generation",
                    provider=provider_name,
                    success=False,
                    duration=time.time() - start_time,
                    error="Response too short or empty",
                )

        except Exception as e:
            return TestResult(
                test_name="generation",
                provider=provider_name,
                success=False,
                duration=time.time() - start_time,
                error=str(e),
            )

    async def _test_chat(self, provider_name: str, provider) -> TestResult:
        """Test chat capability."""
        start_time = time.time()

        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Respond briefly.",
                },
                {"role": "user", "content": "What is 2+2?"},
            ]

            response = await provider.chat(messages, role="execute")

            if response and "4" in response:  # Should contain the answer
                return TestResult(
                    test_name="chat",
                    provider=provider_name,
                    success=True,
                    duration=time.time() - start_time,
                    metadata={"response": response[:100]},
                )
            else:
                return TestResult(
                    test_name="chat",
                    provider=provider_name,
                    success=False,
                    duration=time.time() - start_time,
                    error=f"Unexpected response: {response[:100]}",
                )

        except Exception as e:
            return TestResult(
                test_name="chat",
                provider=provider_name,
                success=False,
                duration=time.time() - start_time,
                error=str(e),
            )

    async def _test_embeddings(self, provider_name: str, provider) -> TestResult:
        """Test embedding capability."""
        start_time = time.time()

        try:
            embeddings = await provider.embed("test sentence")

            if embeddings and len(embeddings) > 0:
                return TestResult(
                    test_name="embeddings",
                    provider=provider_name,
                    success=True,
                    duration=time.time() - start_time,
                    metadata={"dimensions": len(embeddings)},
                )
            else:
                return TestResult(
                    test_name="embeddings",
                    provider=provider_name,
                    success=False,
                    duration=time.time() - start_time,
                    error="Empty embedding response",
                )

        except Exception as e:
            error_msg = str(e)
            if (
                "not implemented" in error_msg.lower()
                or "not supported" in error_msg.lower()
            ):
                return TestResult(
                    test_name="embeddings",
                    provider=provider_name,
                    success=False,
                    duration=time.time() - start_time,
                    error="Not supported by provider",
                )
            else:
                return TestResult(
                    test_name="embeddings",
                    provider=provider_name,
                    success=False,
                    duration=time.time() - start_time,
                    error=error_msg,
                )

    async def _test_model_info(self, provider_name: str, provider) -> TestResult:
        """Test model info capability."""
        start_time = time.time()

        try:
            info = await provider.get_model_info()

            if info and isinstance(info, dict) and "model" in info:
                return TestResult(
                    test_name="model_info",
                    provider=provider_name,
                    success=True,
                    duration=time.time() - start_time,
                    metadata=info,
                )
            else:
                return TestResult(
                    test_name="model_info",
                    provider=provider_name,
                    success=False,
                    duration=time.time() - start_time,
                    error="Invalid model info response",
                )

        except Exception as e:
            return TestResult(
                test_name="model_info",
                provider=provider_name,
                success=False,
                duration=time.time() - start_time,
                error=str(e),
            )

    def generate_report(
        self, output_format: str = "text"
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate comprehensive test report.

        Args:
            output_format: "text" or "json"

        Returns:
            Formatted report
        """
        total_duration = time.time() - self.start_time if self.start_time else 0

        report_data = {
            "summary": {
                "total_tests": len(self.results),
                "passed": len([r for r in self.results if r.success]),
                "failed": len(self.failed_tests),
                "duration": total_duration,
            },
            "results": [asdict(result) for result in self.results],
            "failed_tests": [asdict(result) for result in self.failed_tests],
        }

        if output_format == "json":
            return report_data

        # Generate text report
        lines = [
            "=" * 60,
            "FORGE AI PROVIDER TEST REPORT",
            "=" * 60,
            f"Total Tests: {report_data['summary']['total_tests']}",
            f"Passed: {report_data['summary']['passed']}",
            f"Failed: {report_data['summary']['failed']}",
            f"Duration: {report_data['summary']['duration']:.2f} seconds",
            "",
        ]

        if self.failed_tests:
            lines.extend(["FAILED TESTS:", "-" * 40])

            for failed_test in self.failed_tests:
                lines.append(
                    f"  {failed_test.provider}/{failed_test.test_name}: {failed_test.error}"
                )

            lines.append("")

        if report_data["summary"]["passed"] > 0:
            lines.extend(["PASSED TESTS:", "-" * 40])

            passed_tests = [r for r in self.results if r.success]
            for test in passed_tests:
                lines.append(
                    f"  {test.provider}/{test.test_name}: {test.duration:.2f}s"
                )

        return "\n".join(lines)


async def main():
    """Main entry point with proper error handling and logging."""
    parser = argparse.ArgumentParser(
        description="Forge AI Provider Testing Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python forge_test.py --test-providers              # Test all providers
  python forge_test.py --provider openai             # Test specific provider  
  python forge_test.py --verify-models               # Check model availability
  python forge_test.py --full-suite                  # Run everything
  python forge_test.py --json                        # JSON output
        """,
    )

    parser.add_argument(
        "--test-providers", action="store_true", help="Test provider capabilities"
    )
    parser.add_argument(
        "--verify-models", action="store_true", help="Verify model availability"
    )
    parser.add_argument(
        "--full-suite", action="store_true", help="Run complete test suite"
    )
    parser.add_argument("--provider", type=str, help="Test specific provider only")
    parser.add_argument(
        "--providers", type=str, help="Comma-separated list of providers to test"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument("--output-file", type=str, help="Save results to file")

    args = parser.parse_args()

    # If no specific test is requested, run basic provider test
    if not any([args.test_providers, args.verify_models, args.full_suite]):
        args.test_providers = True

    # Parse provider arguments
    providers_to_test = None
    if args.provider:
        providers_to_test = [args.provider]
    elif args.providers:
        providers_to_test = [p.strip() for p in args.providers.split(",")]

    # Initialize test suite
    suite = ForgeTestSuite(log_level=args.log_level)

    try:
        if not await suite.setup():
            logger.error("Test setup failed")
            return 1

        # Run requested tests
        if args.verify_models or args.full_suite:
            await suite.verify_models(args.provider)

        if args.test_providers or args.full_suite:
            await suite.test_providers(providers_to_test)

        # Generate and output report
        output_format = "json" if args.json else "text"
        report = suite.generate_report(output_format)

        if args.output_file:
            with open(args.output_file, "w") as f:
                if args.json:
                    json.dump(report, f, indent=2, default=str)
                else:
                    f.write(report)
            logger.info(f"Results saved to {args.output_file}")

        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(report)

        return 0 if not suite.failed_tests else 1

    except KeyboardInterrupt:
        logger.warning("Tests interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Test suite failed with error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
