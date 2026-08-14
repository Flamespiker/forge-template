# FORGE — `request_id` Derivation & `resolve_feature_pr()` Staleness — Fix Spec

**Author:** Claude.ai (spec authorship) — implementation via Claude Code CLI per standing convention
**Date:** 2026-08-13
**Status:** Ready for implementation
**Scope:** Two structural bugs carried forward from the Phase 5 close-out (`FORGE-Phase5-Closeout.md` §8), flagged there as "possibly the same root cause, not confirmed." That question is now resolved — see Investigation below.

---

## 0. Investigation: are these the same bug?

**No.** Read both code paths directly against `main` on `Flamespiker/forge-template` (2026-08-13) rather than relying on prior summaries. They are structurally unrelated:

| | `request_id` derivation bug | `resolve_feature_pr()` staleness |
|---|---|---|
| **File** | `.github/workflows/04-qa.yml`, `.github/workflows/05-security.yml` | `core/agents/workflow_glue.py` |
| **Mechanism** | Bash string-prefix-strip on the dispatched branch name | Python scan of tracking-issue comments for a marker string |
| **Input** | `HEAD_REF` from the `repository_dispatch` payload | GitHub issue comment history |
| **Failure mode** | Silently derives a wrong `request_id` if the branch name doesn't cleanly map to a real `services/<request_id>/` directory | Silently returns the *original* Stage 3 PR forever, ignoring any newer open feature PR |
| **Consumer** | `qa_agent.py`/`security_agent.py` (via `--request-id`) | `06-deploy.yml` (via `resolve-feature-pr` subcommand) |

They share only a *pattern* — fragile identifier resolution with no validation against live state — not a code path or a fix. They're addressed as two independent fixes below, both small.

---

## Fix 1: `request_id` derivation (`04-qa.yml`, `05-security.yml`)

### Root cause (confirmed against live file content)

Both workflows currently do:

```bash
request_id="${HEAD_REF#feature/}"
```

This is a bare prefix-strip with no check that the result names a directory that actually exists. Confirmed downstream impact in `qa_agent.py` (`run_qa_agent()`, ~line 543): if `request_id` is wrong, `service_root = Path(repo_path) / "services" / request_id` points nowhere, `_resolve_backend_test_dir()` returns `None` with only a logged warning, no frontend test script is found either — both suites become `not_applicable`, `suite_run_failed` stays `False`, and `tests_pass` evaluates `True`. Result: **`qa-approved` gets applied to a request whose tests never ran**, silently. This is the exact bug class already proven to have fired once (the original `#5`-vs-qualified-format incident referenced in `CLAUDE.md`), and nothing has changed since to prevent a recurrence on any future `feature/*` branch whose suffix doesn't match its `services/` directory name.

`notify-forge.yml` (confirmed via prior verified summary in `CLAUDE.md` — `forge-demo-apps` is private, not independently re-fetchable this session) filters dispatch strictly to `feature/*` branches, so this bug is scoped to genuine feature PRs only — the four `fix/*` ad hoc branches never reach this code path at all (separate issue — branch-naming decision, out of scope here).

### Fix design

Both workflows already resolve the tracking issue number before running the agent (`steps.issue.outputs.issue_number`, via `workflow_glue resolve-tracking-issue`). Add one more glue step immediately after it, using the **existing, already-proven** `resolve-request-id` subcommand (marker-based — reads the `forge:agent-comment ... request_id=<id>` comment every stage writes, same mechanism every stage from `01-requirements.yml` onward already trusts):

```yaml
- name: Resolve request id
  if: steps.guard.outputs.proceed == 'true'
  id: request_id
  run: |
    python -m core.agents.workflow_glue resolve-request-id --issue-number "${{ steps.issue.outputs.issue_number }}"
```

Then replace both existing consumers of the bash-derived `request_id` with `${{ steps.request_id.outputs.request_id }}`:

1. **"Install frontend dependencies" step** — replace `request_id="${HEAD_REF#feature/}"` with the step output.
2. **"Run QA Agent" / "Run Security Agent" step** — same replacement for the `--request-id` argument.

`HEAD_REF` itself stays in the env block (still needed nowhere else in these two files after this change, but no reason to remove it — out of scope, don't touch what isn't broken).

This eliminates branch-name parsing as a source of truth entirely. No new failure mode is introduced: if `resolve-request-id` can't find a marker, it already raises `ValueError` and the workflow fails loudly (via the existing `except Exception: sys.exit(1)` in `workflow_glue.main()`) — a hard failure is strictly better than the current silent false-positive.

### Files touched
- `.github/workflows/04-qa.yml`
- `.github/workflows/05-security.yml`

No changes needed to `workflow_glue.py`, `qa_agent.py`, or `security_agent.py` — `resolve-request-id` already exists and already does the right thing; this fix is purely "call it instead of re-deriving badly."

### Acceptance criteria
- Both workflows resolve `request_id` via the glue subcommand, not `HEAD_REF` parsing.
- A local/dry-run check confirms the new step's output matches the value the original Stage 3 marker comment carries, for a real issue (e.g. re-run against `REQ-2026-02`'s tracking issue, read-only — no need to actually re-trigger QA/Security).
- Existing guard-clause and skip-on-closed-PR behavior unchanged (this fix only touches what happens once `proceed == 'true'`).
- No change to `qa_agent.py`/`security_agent.py` signatures — they still take `--request-id` as a plain string argument.

---

## Fix 2: `resolve_feature_pr()` staleness (`workflow_glue.py`)

### Root cause (confirmed against live file content)

```python
def resolve_feature_pr(issue_number: int) -> tuple[int, str]:
    for comment in get_issue_comments(issue_number):
        if _IMPLEMENTATION_STAGE_MARKER not in comment["body"]:
            continue
        match = _PR_URL_RE.search(comment["body"])
        ...
        return pr_number, pr["head"]["sha"]
```

This returns the **first** `stage=implementation` comment it finds — i.e., always the original Stage 3 PR, regardless of whether a newer feature PR has since been opened on the same tracking issue (e.g., a post-implementation follow-up like the R-001 descope pattern). `06-deploy.yml` uses this to decide *what to actually build and deploy* — pointing it at a stale, possibly-already-merged-and-superseded PR risks deploying the wrong commit silently.

### Fix design

Stop reading comment history for this. Ask GitHub directly for the PR that's actually open right now, using the branch-naming convention Stage 3 itself guarantees — confirmed in `implementation_coordinator.py`:

```python
branch_name = f"feature/{request_id}"
```

**New `github_helper.py` function** (no equivalent currently exists — confirmed via function inventory):

```python
def list_open_prs_by_head(branch_name: str) -> list[dict]:
    """
    List open PRs in the target monorepo (forge-demo-apps) whose head branch
    matches branch_name exactly. Uses the GitHub App installation token --
    same cross-repo auth context as get_pr(). Needed by resolve_feature_pr()
    to find the *currently* open feature PR, rather than trusting a
    potentially-stale comment reference.
    """
    owner = os.environ["FORGE_GITHUB_OWNER"]
    token = get_installation_token()
    url = f"{_repo_url()}/pulls"
    params = {"state": "open", "head": f"{owner}:{branch_name}"}
    response = requests.get(url, headers=_auth_headers(token), params=params, timeout=15)
    response.raise_for_status()
    prs: list[dict] = response.json()
    logger.info("Found %d open PR(s) with head '%s'", len(prs), branch_name)
    return prs
```

**Rewritten `resolve_feature_pr()`** in `workflow_glue.py`:

```python
def resolve_feature_pr(issue_number: int) -> tuple[int, str]:
    """
    Returns (pr_number, head_sha) for the *currently open* feature PR tied
    to this tracking issue. Resolves request_id via the same marker-based
    resolve_request_id() every other stage trusts (stable for the life of
    the issue), then looks up the live, currently-open PR on
    feature/<request_id> directly via the GitHub API -- no longer anchored
    to a potentially-stale Implementation Coordinator comment.
    """
    request_id = resolve_request_id(issue_number)
    branch_name = f"feature/{request_id}"
    prs = list_open_prs_by_head(branch_name)

    if not prs:
        raise ValueError(
            f"No open PR found on branch '{branch_name}' for issue #{issue_number} -- "
            "has Stage 3 run yet, or has the feature PR already been merged/closed "
            "without a new one being opened?"
        )
    if len(prs) > 1:
        raise ValueError(
            f"Found {len(prs)} open PRs on branch '{branch_name}' for issue "
            f"#{issue_number} -- expected exactly one. Refusing to guess which "
            "one to deploy."
        )
    pr = prs[0]
    return pr["number"], pr["head"]["sha"]
```

Note: this makes `resolve_feature_pr()` no longer depend on the Implementation Coordinator's comment at all — the `_IMPLEMENTATION_STAGE_MARKER`/`_PR_URL_RE` constants become dead code for this function specifically. **Do not delete them** without checking whether anything else in the file still uses them (they appeared purpose-built for this function based on the module docstring — confirm via a grep before removing, this spec doesn't assume either way).

### Files touched
- `core/agents/utils/github_helper.py` — add `list_open_prs_by_head()`
- `core/agents/workflow_glue.py` — rewrite `resolve_feature_pr()`, no signature change (still returns `tuple[int, str]`, still called identically from `06-deploy.yml`)

No changes needed to `06-deploy.yml` itself — it calls `workflow_glue resolve-feature-pr --issue-number N` and reads `pr_number`/`head_sha` outputs exactly as before; the fix is entirely internal to how those values get resolved.

### Acceptance criteria
- `list_open_prs_by_head()` verified against a real currently-open PR (or a deliberately-constructed read-only test) — confirm it returns exactly one result for a known-open `feature/<request_id>` branch and zero for a merged/closed one, via live `az`-style verification (in this case, real GitHub API calls, not mocks) per project convention.
- `resolve_feature_pr()` verified against at least one real historical case where the old code would have returned stale data (e.g., simulate the R-001 follow-up scenario: an issue with two `stage=implementation` comments across two different feature PRs, confirm the new code returns the currently-open one, not the first one).
- Zero-PRs and multiple-PRs cases both raise loudly with a clear message — no silent fallback to "pick the first one" or similar.
- `06-deploy.yml`'s existing behavior for the normal single-PR case is unchanged end-to-end (re-verify against a real or realistic dispatch, matching the rigor of the Deploy Agent wiring spec's live verification).

---

## Explicitly out of scope

- **Branch-naming convention for ad hoc `fix/*` PRs** — separate, already-logged decision (4 admin-merge occurrences), unrelated to either fix above. Do not conflate; a dedicated session already exists for this.
- **`resolve_tracking_issue()`** (the reverse lookup, PR → issue) — not touched; no known bug in it.
- **Deploy Agent cross-service wiring** (`deploy_agent.py`) — separately fixed and verified in chat 45; unrelated files.
- **Whether Stage 3 should even reuse the same `feature/<request_id>` branch name for a follow-up implementation run** — this spec assumes the existing convention (confirmed in `implementation_coordinator.py`) holds; if a future case needs a *second* concurrent feature PR per request, that's a bigger design question outside this spec's scope, and Fix 2's "exactly one PR" guard will correctly refuse to guess rather than silently misbehaving.

---

## Handoff notes for Claude Code CLI

Per standing convention: pre-flight-verify live file state (line numbers, current `HEAD_REF`/`request_id` usages) before editing — this spec's line references are descriptive, not authoritative, the way the Deploy Agent spec's stale `utils/` path taught us to expect. Separate commits per fix (Fix 1: two workflow YAML files together, since they're the identical change in parallel files; Fix 2: `github_helper.py` + `workflow_glue.py` together, since the new function only exists to serve the rewritten caller). Local/dry-run verification before anything touches real GitHub API state against a live tracking issue or PR.
