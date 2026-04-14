# Final Answer: recommend_automation_improvements

## Summary

Codex’s watcher currently hard-codes `candidate=stable[1]`, so every new upstream release is skipped until a second one arrives; both watchers still dispatch the expensive snapshot workflows nightly even when a matching automation PR is already stabilizing; the macOS/Windows legs are intentionally optional per RULES.json but the workflows never annotate when `union.complete=false`, so maintainers don’t see that they are merging partial coverage; and the Codex snapshot flow treats PR creation as best-effort while Claude Code fails the entire run on the same error, yielding inconsistent automation guarantees.

## Recommendations

### 1. Codex release watch permanently skips the newest upstream release (confirmed_issue, high)

**Rationale:** The watcher sorts releases descending, sets `candidate = (stable[1] ?? stable[0])`, and then exits whenever `candidate === latest_validated`. Once a release (e.g., 0.77.0) is validated, it slides into `stable[1]`, so every subsequent cron run sees `candidate` equal to `latest_validated` and never dispatches the new `stable[0]` release (0.78.0). This repeats forever, meaning automation never trials the newest upstream release unless two releases drop simultaneously.

**Suggested change:** Update the candidate-selection block to prefer `stable[0]` whenever it is newer than `latest_validated`, and only fall back to `stable[1]` if the latest release is already validated or explicitly skipped. Add a regression unit (e.g., in the github-script summary) that feeds a mocked `stable` array and proves a single-release update now triggers `createWorkflowDispatch`.

**Evidence:**
- .github/workflows/codex-cli-release-watch.yml:45-107

**Confidence:** 0.9

### 2. Release watchers keep firing while an automation PR for the same version is open (risk, medium)

**Rationale:** Neither watcher checks for an existing automation branch/PR before calling `actions.createWorkflowDispatch`, so the nightly cron will re-run the full three-target snapshot pipeline (prepare + three runners + union/report/validate) even when `automation/codex-cli-${version}` or `automation/claude-code-${version}` already exists and is under review. `peter-evans/create-pull-request@v6` is idempotent on those branch names, so we don’t get duplicate PRs, but we do spend redundant CI minutes and storage every night until the human merges the PR.

**Suggested change:** Inside each watcher script, query for an open PR or branch matching `automation/{tool}-${version}` (via `github.rest.pulls.list` or `github.rest.repos.getBranch`) and skip dispatch when one exists; alternatively, persist the last dispatched version in a repo issue or artifact and stop when it matches. Emit a summary entry when the dispatch is skipped so maintainers know why the cron run was cheap.

**Evidence:**
- .github/workflows/codex-cli-release-watch.yml:45-107
- .github/workflows/claude-code-release-watch.yml:34-70
- .github/workflows/codex-cli-update-snapshot.yml:539-549
- .github/workflows/claude-code-update-snapshot.yml:339-352

**Confidence:** 0.78

### 3. Partial multi-platform unions are allowed but never surfaced to reviewers (risk, medium)

**Rationale:** The union jobs intentionally mark the macOS and Windows downloads as `continue-on-error: true`, and RULES.json explicitly sets `allow_promote_when_incomplete: true` with `when_non_required_targets_missing: "emit_union_complete_false"`. However, no step reads `cli_manifests/*/versions/${VERSION}.json` or the union metadata to tell reviewers that `union.complete=false` and which targets are missing. As a result, PRs can merge with silent macOS/Windows gaps, defeating the policy’s intent of conscious partial promotion.

**Suggested change:** After the union/report step in both workflows, run `jq` over the generated union metadata (e.g., `cli_manifests/**/versions/${VERSION}.json`) to capture `union.complete` and `union.missing_targets`, expose them as job outputs, and append a clear section to the PR body/work-queue summary whenever non-required targets are missing. Optionally fail the workflow if a maintainer requests full parity via an input flag. This keeps the existing lenient policy but ensures partial coverage is explicit.

**Evidence:**
- .github/workflows/codex-cli-update-snapshot.yml:261-339
- .github/workflows/claude-code-update-snapshot.yml:231-300
- cli_manifests/codex/RULES.json:104-154
- cli_manifests/claude_code/RULES.json:120-170

**Confidence:** 0.75

### 4. PR creation error policy is inconsistent between Codex and Claude Code (risk, low)

**Rationale:** Codex’s workflow marks the `peter-evans/create-pull-request@v6` step `continue-on-error: true`, so the run succeeds even if GitHub rejects the PR (token scopes, branch protection, etc.), while Claude Code treats the same step as a hard gate. That asymmetry means Codex automation can silently drop updates whereas Claude Code will alert on the same fault.

**Suggested change:** Pick a single policy for automation PR creation (best-effort with an explicit summary note or fail-fast) and apply it to both workflows so release engineers get consistent signals. If best-effort is desired, emit a `core.summary` warning when the PR isn’t created; if fail-fast is desired, remove `continue-on-error` from Codex and ensure the error bubbles up.

**Evidence:**
- .github/workflows/codex-cli-update-snapshot.yml:539-549
- .github/workflows/claude-code-update-snapshot.yml:339-352

**Confidence:** 0.7
