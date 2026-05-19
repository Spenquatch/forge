#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

WORKSPACE="${1:-${GSD_BROWSER_WORKSPACE:-}}"
OUT_ROOT="${2:-$REPO_ROOT/.forge-harness-runs-live/gsd-browser-session-lifecycle}"
TASK_PATH="$SCRIPT_DIR/gsd_browser_session_lifecycle_planning.template.yaml"
STRATEGY_PATH="examples/harness/strategies/deterministic_feature_planning_v1.yaml"

if [[ -z "$WORKSPACE" ]]; then
  echo "usage: $(basename "$0") <gsd-browser-workspace> [out_root]" >&2
  echo "or set GSD_BROWSER_WORKSPACE=/path/to/gsd-browser" >&2
  exit 2
fi

if [[ ! -d "$WORKSPACE" ]]; then
  echo "workspace not found: $WORKSPACE" >&2
  exit 2
fi

cd "$REPO_ROOT"

poetry run python -m anvil.cli harness-run \
  --task "$TASK_PATH" \
  --strategy "$STRATEGY_PATH" \
  --workspace "$WORKSPACE" \
  --out-root "$OUT_ROOT" \
  --json
