"""
Poetry-only setup helper for Forge.

This script checks for commonly used modules and can invoke Poetry to
install the core dependencies and optional extras declared in pyproject.toml.

Usage (from repo root):
  poetry run python scripts/setup_tools.py
  poetry run python scripts/setup_tools.py --extras llama-cpp --yes --skip-env
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Optional


def _module_installed(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:
        return False


def check_requirements():
    """Check if required packages are installed (by import test)."""
    print("Checking required packages...")

    # Core modules (match import names)
    essential_modules = ["pydantic", "yaml", "dotenv"]

    # Optional extras mapped to import checks
    extras_modules = {
        # Provider ecosystems
        "openai": ["langchain_openai"],
        "anthropic": ["langchain_anthropic"],
        "transformers": ["transformers", "torch", "accelerate"],
        "llama-cpp": ["llama_cpp"],
        # Other extras
        "langgraph": [
            "langgraph",
            "langgraph.checkpoint.sqlite",
            "langgraph.checkpoint.sqlite.aio",
        ],
        "api": ["fastapi", "uvicorn"],
        "cli": ["typer", "rich"],
        "rl": ["skrl"],
    }

    missing_essential = []
    for mod in essential_modules:
        if _module_installed(mod):
            print(f"✓ {mod} available")
        else:
            print(f"✗ {mod} missing")
            missing_essential.append(mod)

    missing_extras = {}
    for extra, modules in extras_modules.items():
        print(f"\nChecking '{extra}' extra:")
        missing = [m for m in modules if not _module_installed(m)]
        if missing:
            for m in missing:
                print(f"✗ {m} missing")
            missing_extras[extra] = missing
        else:
            for m in modules:
                print(f"✓ {m} available")

    return missing_essential, missing_extras


def install_with_poetry(extras=None):
    """Invoke 'poetry install' optionally with extras.

    extras: list[str] of extras to include (e.g., ["openai", "anthropic"]).
    """
    extras = extras or []
    if not _poetry_available():
        print(
            "✗ Poetry is not installed or not on PATH. Please install Poetry: https://python-poetry.org/docs/#installation"
        )
        return False

    cmd = ["poetry", "install"]
    for e in extras:
        cmd += ["--extras", e]

    print("\nRunning:", " ".join(cmd))
    try:
        subprocess.check_call(cmd)
        print("✓ Poetry install completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Poetry install failed: {e}")
        return False


def _poetry_available() -> bool:
    try:
        subprocess.check_call(
            ["poetry", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def setup_env_file():
    """Create or update .env file."""
    env_path = Path(".env")

    if env_path.exists():
        print("\n.env file exists. Checking for required variables...")
        with open(env_path, "r") as f:
            content = f.read()

        # Check for required variables
        has_openai = "OPENAI_API_KEY" in content
        has_anthropic = "ANTHROPIC_API_KEY" in content

        updates = []
        if not has_openai:
            updates.append("OPENAI_API_KEY=your_key_here")
        if not has_anthropic:
            updates.append("ANTHROPIC_API_KEY=your_key_here")

        if updates:
            print("Adding missing environment variables...")
            with open(env_path, "a") as f:
                f.write("\n" + "\n".join(updates) + "\n")
    else:
        print("\nCreating .env file...")
        with open(env_path, "w") as f:
            f.write("OPENAI_API_KEY=your_key_here\nANTHROPIC_API_KEY=your_key_here\n")

    print("✓ .env file prepared (you'll need to add your actual API keys)")


def _confirm(prompt: str, *, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    return input(prompt).strip().lower() == "y"


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forge setup tool (Poetry).")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only report missing modules; do not install anything.",
    )
    parser.add_argument(
        "--extras",
        action="append",
        default=[],
        help="Poetry extras to install (repeatable), e.g. --extras llama-cpp --extras transformers.",
    )
    parser.add_argument(
        "--all-missing",
        action="store_true",
        help="Install all missing extras detected by import checks.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive: assume 'yes' for install prompts.",
    )
    parser.add_argument(
        "--skip-env",
        action="store_true",
        help="Skip creating/updating `.env`.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None):
    """Main function."""
    print("=== Forge Setup Tool (Poetry) ===")

    args = _parse_args(argv)

    # Check requirements
    missing_essential, missing_extras = check_requirements()

    if args.check_only:
        print("\n=== Check Only Complete ===")
        return

    requested_extras = [e.strip() for e in args.extras if e.strip()]
    if args.all_missing:
        requested_extras = sorted(set(requested_extras + list(missing_extras.keys())))

    if requested_extras:
        print("\nRequested extras:", ", ".join(requested_extras))
        ok = install_with_poetry(extras=requested_extras)
        if not ok:
            return

    # Offer Poetry install for essentials
    if missing_essential:
        print("\nEssential modules are missing. Install core dependencies with Poetry.")
        if _confirm("Run 'poetry install'? (y/n): ", assume_yes=bool(args.yes)):
            install_with_poetry()

    # Offer Poetry install for extras
    if missing_extras:
        needed = list(missing_extras.keys())
        print("\nOptional features detected as missing:")
        print("  Extras:", ", ".join(needed))
        if _confirm(
            "Install these extras with Poetry now? (y/n): ",
            assume_yes=bool(args.yes),
        ):
            install_with_poetry(extras=needed)
        else:
            print("\nYou can install specific extras later, for example:")
            print("  poetry install --extras openai")
            print("  poetry install --extras anthropic")
            print("  poetry install --extras transformers")
            print("  poetry install --extras llama-cpp")
            print("  poetry install --extras api")
            print("  poetry install --extras cli")
            print("  poetry install --extras rl")
            print("  poetry install --extras all  # everything")

    # Set up .env file
    if args.skip_env:
        print("\nSkipping .env setup (per --skip-env).")
    else:
        setup_env_file()

    print("\n=== Setup Complete ===")
    print("Run 'python test_setup.py' to test your installation.")


if __name__ == "__main__":
    main()
