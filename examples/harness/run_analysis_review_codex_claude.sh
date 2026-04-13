#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=${1:?usage: ./examples/harness/run_analysis_review_codex_claude.sh /path/to/repo}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)

python -m anvil.cli harness-run \
  --task "$ROOT_DIR/examples/harness/tasks/recommend_automation_improvements.yaml" \
  --strategy "$ROOT_DIR/examples/harness/strategies/analysis_review_codex_claude.yaml" \
  --workspace "$REPO_DIR" \
  --out-root "$ROOT_DIR/.forge-harness-runs"
