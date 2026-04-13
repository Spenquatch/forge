#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=${1:?usage: ./examples/harness/run_pfr_codex_claude.sh /path/to/repo}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)

python -m anvil.cli harness-run \
  --task "$ROOT_DIR/examples/harness/tasks/fix_auth_bug.yaml" \
  --strategy "$ROOT_DIR/examples/harness/strategies/pfr_codex_claude.yaml" \
  --workspace "$REPO_DIR" \
  --out-root "$ROOT_DIR/.forge-harness-runs"
