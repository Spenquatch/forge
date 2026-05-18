#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

PLAN_MD="${1:-}"
PLAN_JSON="${2:-}"
OUT_DIR="${3:-$REPO_ROOT/.forge-harness-runs-live/planning-provider-proof}"
CODEX_BIN="${FORGE_CODEX_BIN:-codex}"

if [[ -z "$PLAN_MD" || -z "$PLAN_JSON" ]]; then
  echo "usage: $(basename "$0") <PLAN.md> <plan.json> [out_dir]" >&2
  exit 2
fi

if [[ ! -f "$PLAN_MD" ]]; then
  echo "PLAN.md not found: $PLAN_MD" >&2
  exit 2
fi

if [[ ! -f "$PLAN_JSON" ]]; then
  echo "plan.json not found: $PLAN_JSON" >&2
  exit 2
fi

if ! command -v "$CODEX_BIN" >/dev/null 2>&1; then
  echo "Codex CLI not found. Install codex or set FORGE_CODEX_BIN." >&2
  exit 2
fi

mkdir -p "$OUT_DIR"
cp "$PLAN_MD" "$OUT_DIR/input.PLAN.md"
cp "$PLAN_JSON" "$OUT_DIR/input.plan.json"

PROMPT_PATH="$OUT_DIR/review_prompt.md"
OUTPUT_PATH="$OUT_DIR/provider_review.md"
STDOUT_PATH="$OUT_DIR/provider_review.stdout.log"
META_PATH="$OUT_DIR/proof_command.txt"

cat > "$PROMPT_PATH" <<PROMPT
Review the deterministic planning artifacts below as a provider-backed challenge pass.

Artifacts:
- PLAN.md: $OUT_DIR/input.PLAN.md
- plan.json: $OUT_DIR/input.plan.json

Rules:
- Treat the deterministic plan structure as authoritative.
- Do not rewrite, rename, or invent canonical seam_id, workstream_id, or slice_id values.
- You may challenge grounding, completeness, prioritization, or operator clarity.
- If you mention a canonical ID, quote it exactly as written in the artifacts.

Return markdown with exactly these sections:
1. Verdict
2. Credibility strengths
3. Credibility risks
4. Open questions
5. Structural ID check
PROMPT

printf '%s\n' "$CODEX_BIN exec -C $REPO_ROOT --dangerously-bypass-approvals-and-sandbox --color never -o $OUTPUT_PATH - < $PROMPT_PATH" > "$META_PATH"
"$CODEX_BIN" exec -C "$REPO_ROOT" --dangerously-bypass-approvals-and-sandbox --color never -o "$OUTPUT_PATH" - < "$PROMPT_PATH" | tee "$STDOUT_PATH"

echo "provider_review=$OUTPUT_PATH"
echo "stdout_log=$STDOUT_PATH"
echo "prompt=$PROMPT_PATH"
