# Best Draft: recommend_automation_improvements

> [!WARNING]
> This run did not reach a fully accepted verdict. This file may contain a best-effort or partial deliverable.

## Summary

CI/CD audit for Codex & Claude Code release automation surfaces one correctness bug in the Codex watcher and one reliability risk around branch drift between watchers and staging-only update workflows.

## Recommendations

### 1. Codex release watch never dispatches the newest upstream release (confirmed_issue, high)

**Rationale:** `codex-cli-release-watch.yml` selects `candidate = (stable[1] ?? stable[0])` and then refuses to dispatch whenever that candidate is not newer than `latest_validated`. When the repository has already validated the previous release (stable[1]), the candidate equals `latest_validated`, so the workflow exits even though `latestStable` is ahead. This leaves automation permanently one release behind and blocks new Codex versions from entering the snapshot pipeline.

**Suggested change:** Set `candidate` to the newest stable tag (fallback to the newest available entry when only one exists) and dispatch when `latestStable` is newer than `latest_validated`. A simple fix is to drop the stable-minus-one logic, compare `latestStable` directly against `latest_validated`, and hand that version into `codex-cli-update-snapshot.yml`.

**Evidence:**
- .github/workflows/codex-cli-release-watch.yml

**Confidence:** 0.9

### 2. Release watch workflows read validation pointers from the wrong branch (risk, medium)

**Rationale:** Both release-watch jobs check out the workflow ref (for scheduled runs this is the default branch, likely `main`) and read `cli_manifests/*/latest_validated.txt`. However, the downstream update workflows always operate on `staging` (see explicit `checkout ref: staging` comments). If staging advances before main, the watchers continue seeing the old `latest_validated` pointer and will repeatedly trigger redundant snapshot runs for versions already processed on staging.

**Suggested change:** In both release-watch workflows, check out `staging` (or explicitly read `latest_validated` from that branch via `ref: staging` or `git fetch`) so that the watcher’s state matches the automation branch. Alternatively, keep the default checkout but read the file via `git show staging:cli_manifests/.../latest_validated.txt` before deciding to dispatch.

**Evidence:**
- .github/workflows/codex-cli-release-watch.yml
- .github/workflows/claude-code-release-watch.yml
- .github/workflows/codex-cli-update-snapshot.yml
- .github/workflows/claude-code-update-snapshot.yml

**Confidence:** 0.7
