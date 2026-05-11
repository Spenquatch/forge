#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=${1:?usage: ./examples/harness/run_analysis_review_codex_claude.sh /path/to/repo [strategy-path]}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
# Defaults to the bounded adjudicate example.
# Canonical trust entrypoints are the attestation-first analysis_review_trust_*.yaml files.
# For example: examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml
# Use analysis_review_trust_legacy_*.yaml only for explicit legacy_full_review compatibility checks.
STRATEGY_PATH=${2:-$ROOT_DIR/examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml}

poetry run python -m anvil.cli harness-run \
  --task "$ROOT_DIR/examples/harness/tasks/recommend_automation_improvements.yaml" \
  --strategy "$STRATEGY_PATH" \
  --workspace "$REPO_DIR" \
  --out-root "$ROOT_DIR/.forge-harness-runs"
