# FORGE — Extend QA (Stage 4) and Security (Stage 5) for Enhancement Targets (Item #25): Spec for Claude Code

**Prepared:** 2026-08-28 (Claude.ai)
**For:** Claude Code CLI session against `forge-template` (`qa_agent.py`, `security_agent.py`,
`04-qa.yml`, `05-security.yml`), with live verification against `forge-demo-apps` and
tracking issue `forge-template#10`.
**Context:** Item #25 in CLAUDE.md's Open Items list — confirmed live 2026-08-28 on
`forge-demo-apps#32` (REQ-2026-04, existing service REQ-2026-03). Item #24 (Stage 3)
now correctly resolves an Enhancement request's real target directory
(`services/<existing_service>/`) instead of the new request's own ID. Stage 4 (QA) and
Stage 5 (Security) were never updated to match — both still unconditionally scan
`services/<request_id>/`, which doesn't exist for an Enhancement. Confirmed live:
QA silently false-positive-passed (reported both suites "not applicable" and applied
`qa-approved` with zero real test coverage); Security crashed with an unhandled
`FileNotFoundError` inside `_run_semgrep()`, no `security-approved`, no clean failure
signal. This is a genuine hole in the project's ADR-0011 fail-loud pattern: QA's
missing-directory case is masquerading as a legitimate not-applicable case, and
Security's crash is the *right* outcome (blocked) reached the *wrong* way (an
uninformative traceback instead of a clean, ADR-0011-compliant failure comment).

**Standing conventions to follow (per CLAUDE.md / context doc):**
- Verify every current file/behavior live before writing code — this spec's read of
  `qa_agent.py`, `security_agent.py`, `04-qa.yml`, `05-security.yml` is from CLAUDE.md's
  notes and may have drifted.
- Windows environment: `shutil.which()` for subprocess calls, `encoding="utf-8"` on
  subprocess readers, no bash heredocs.
- Any new failure path follows the ADR-0011 comment-then-reraise contract — no bare
  unhandled exceptions, no silent skips.
- Report every design fork back to Mike rather than resolving silently — see §3.
- Commit each piece in §2 **separately**, verified against real `git diff HEAD`.
- Do not touch Items #1, #7, #9, #10, #11, #12, #26 — out of scope here (see §4).
- **Do not touch `implementation_coordinator.py`'s own already-working, already-live-
  verified Enhancement-resolution logic** unless Mike explicitly picks the optional
  refactor fork in §3.2 — it works today and Item #24 is closed.

---

## 1. Investigate first (do this before designing anything)

1. **Current `qa_agent.py`** — read in full. Confirm exactly where
   `services/<request_id>/` gets built (backend test-dir resolution
   `_resolve_backend_test_dir()`, frontend `_frontend_test_script_exists()`, and
   anywhere else the path is constructed), and confirm the current `not_applicable`
   logic really does resolve a *missing entire service directory* to the same outcome
   as a *present-but-test-less* directory — this is the load-bearing assumption behind
   §2.2 below. Also confirm whether `--repo-path` checkout already has
   `services/REQ-2026-04/` genuinely absent (not just untested) on the live PR #32
   checkout, to be sure the reproduction matches CLAUDE.md's description exactly.
2. **Current `security_agent.py`** — read in full. Confirm the exact call site and
   stack trace shape of the live `FileNotFoundError` inside `_run_semgrep()`
   (CLAUDE.md quotes the message but confirm the surrounding code — is Gitleaks's
   path-scoped run affected identically, or does only Semgrep crash first and mask a
   second latent problem in Gitleaks?). Also confirm the Dependabot path filter
   (`dependency.manifest_path` starting with `services/<request_id>/`) — this wasn't
   part of the observed crash (Semgrep failed first) but would silently mis-filter
   against the wrong path if reached; confirm live whether it's reachable before
   Semgrep's crash aborts the run or whether `ScanResult.ran=False`-per-tool means it
   runs independently regardless.
3. **`04-qa.yml` and `05-security.yml`** — read both in full. Confirm neither currently
   has an Enhancement-detection step (unlike `03-implementation.yml`, which now does),
   and confirm exactly what CLI flags each currently passes to `qa_agent.py`/
   `security_agent.py`. Confirm both already receive `--issue-number` (CLAUDE.md's
   entry-point signatures suggest yes) — needed for §2.1's spreadsheet re-download
   approach to work without a new wiring change.
4. **`03-implementation.yml`'s "Determine Enhancement status" step** — read its exact
   shape (the `workflow_glue.py download-issue-attachment` invocation, the `file_io.py`
   parsing call, the `GITHUB_OUTPUT` write) so §2.1 can mirror it precisely rather than
   re-deriving something similar-but-different.
5. **Tracking issue `forge-template#10`'s live comment history** — confirm the exact
   text of the "Related service: services/REQ-2026-03/" line Stage 3 posted (per
   Item #24 §2.3), to evaluate §3.1's design fork concretely rather than in the
   abstract.
6. **A current live Greenfield feature PR** (any recent one, e.g. REQ-2026-01/02/03's
   own historical PRs) — confirm today's QA/Security behavior against a Greenfield
   request is genuinely unaffected by anything in this spec, as a baseline to diff
   against after the fix.

Report findings from this section back before proceeding if anything contradicts the
assumptions below — in particular, if #2's Gitleaks/Dependabot investigation surfaces
that either is *also* live-broken (not just latently at risk), that's worth flagging
explicitly rather than silently folding into the same fix.

---

## 2. Scope

### 2.1 Enhancement-target resolution for QA and Security

**Goal:** both stages know, before running any scan, whether this is an Enhancement
request and — if so — which existing `services/<n>/` folder is the real target,
exactly the same concept Stage 3 already has.

**Proposed approach (mirrors Item #24 §2.1's already-working, already-live-verified
pattern — reuse over reinvention):**
- Add a "Determine Enhancement status" step to `04-qa.yml` and `05-security.yml`,
  structurally identical to `03-implementation.yml`'s own step: re-download the intake
  spreadsheet via `workflow_glue.py download-issue-attachment` (using the
  `--issue-number` both workflows already receive), parse `request_type` and the
  "If Enhancement — Existing Service Name" Overview field via the existing
  `file_io.py` parsing.
- Pass the resolved value to `qa_agent.py` and `security_agent.py` as a new optional
  `--existing-service` flag, exactly mirroring `implementation_coordinator.py`'s
  existing CLI shape from Item #24.
- Inside each script: introduce one small shared helper —
  `core/agents/utils/enhancement_target.py`, a single function
  `resolve_service_root(request_id: str, existing_service: str | None) -> str`
  returning `services/<existing_service>/` if set, else `services/<request_id>/` —
  used by both `qa_agent.py` and `security_agent.py` in place of each script's own
  inline path construction. This avoids the three-independent-copies problem CLAUDE.md
  already flagged (Ingestion Agent, Stage 3, and now QA/Security each building this
  path their own way).

**Considered and not chosen as the default (flag to Mike per §3.1):** parsing the
already-posted "Related service: services/<existing_service>/" line from the tracking
issue comment or PR body instead of re-downloading the spreadsheet — see §3.1.

### 2.2 QA: distinguish "wrong/missing directory" from genuine "not applicable"

**Goal:** a service directory that doesn't exist at all must fail loud (Layer 2 raise,
ADR-0011 comment-then-reraise), never resolve to the same `not_applicable` outcome as a
service that genuinely has no test project.

- Before any backend/frontend test-dir resolution runs, check once whether
  `services/<resolved_target>/` exists at all under `--repo-path` (a plain directory
  existence check against the real checkout, not a GitHub API call — QA already has
  the local checkout).
- **If the top-level service directory is missing entirely:** raise a new
  `EnhancementTargetNotFoundError` (or equivalent, matching the naming convention
  already established for `EnhancementServiceNotFoundError` in Ingestion Agent),
  wrapped in the same log-comment-reraise block pattern used for Item #24's Layer 2
  fix — post a failure comment identifying the resolved target path and the request/
  issue number, then re-raise. No `qa-approved`, no `qa-loop-back` — this is a distinct
  failure mode from a test failure and should read as one in the posted comment (e.g.
  "QA could not run: expected service directory `services/<target>/` does not exist in
  this checkout" — not a test-failure-shaped message).
- **If the directory exists but genuinely has no test project** (today's existing
  `_frontend_test_script_exists()` / `_resolve_backend_test_dir()` behavior): unchanged
  — `not_applicable` remains a real, legitimate third outcome exactly as Phase 5's
  pre-flight Fix 3 established. This fix narrows *when* `not_applicable` applies; it
  doesn't remove it.
- Confirm this doesn't change retry-attempt counting semantics — a Layer 2 raise here
  should behave like Stage 3's own Layer 2 raise (a real failure, not a counted QA
  attempt against `_MAX_RETRIES`), since the request never actually ran against real
  code.

### 2.3 Security: fail loud instead of crashing

**Goal:** the same missing-directory condition that currently produces an unhandled
`FileNotFoundError` traceback must instead produce a clean, informative,
ADR-0011-compliant failure — check-run `failure`, no `security-approved`, a real
posted comment explaining what happened, not a generic step-failure surfaced from a
raw Python exception.

- Before entering the three-scanner loop (Semgrep, Gitleaks, Dependabot), check once
  whether `services/<resolved_target>/` exists under `--repo-path` (same check as
  §2.2, reusing the same shared helper if a directory-existence check function is
  factored out — otherwise a small local duplicate is fine, this one's cheap).
- **If missing:** skip the scan loop entirely, post a failure comment via the existing
  ADR-0011 pattern (matching the language/shape of §2.2's QA comment for consistency),
  create the check run with conclusion `failure` and a title reflecting "blocked —
  target directory not found" (a fourth branch alongside the existing three-way
  "blocked" / "incomplete — scanner failure" / "passed" title logic), apply no label.
  This should read as a distinct, named condition from `any_tool_failed` — a scanner
  that never got the chance to run because its target doesn't exist is a different
  fact than a scanner that ran and crashed.
- **Dependabot filter fix (real latent bug, confirmed or ruled out in §1.2):** if
  §1.2's investigation confirms the manifest-path filter is reachable independent of
  Semgrep's crash, update `_run_dependabot_check()`'s filter to use the resolved
  target (`services/<resolved_target>/`) instead of `services/<request_id>/` — same
  category of fix as §2.1, just applied to Security's third scanner. If §1.2 finds
  it's unreachable in practice because the pre-scan directory check now short-circuits
  the whole loop, note that explicitly rather than making an unreachable code change.

### 2.4 Greenfield behavior unaffected

**Goal:** confirm (don't just assume) both fixes are a no-op for every existing
Greenfield request.

- When `--existing-service` is absent, `resolve_service_root()` returns
  `services/<request_id>/` exactly as today, the directory-existence check passes for
  any real Greenfield PR (the directory exists because Stage 3 built it), and both
  scripts fall through to their unchanged existing logic. No behavior change for the
  common case.

---

## 3. Design forks explicitly surfaced (Mike's call, not Claude Code's)

### 3.1 Resolution mechanism: re-download spreadsheet vs. parse the posted "Related service" line

**Recommended default: re-download the intake spreadsheet** (§2.1's proposed approach),
consistent with the project's own established precedent of not trusting weak signals —
CLAUDE.md explicitly documents that `request_id` resolution was deliberately moved
*away from* parsing a branch name or comment text and *toward* an authoritative-source
lookup, for exactly this reason (a prefix-strip once produced a wrong `request_id`
silently). Parsing the "Related service: services/<existing_service>/" line Stage 3
already posts to the tracking issue or PR body is real, currently-available data and
would save two API calls (`download-issue-attachment` + parse) per QA/Security run —
but it inherits the same fragility class the project already moved away from once:
it depends on comment-text formatting staying stable, and it silently has no value at
all if a human ever opens an ad hoc Enhancement PR directly (Item #15's exact
precedent — ad hoc PRs already need a manually-added tracking-issue line; this would be
a second manually-added line with the same failure mode). Worth re-raising only if the
spreadsheet re-download proves unreliable in §1's live investigation, or if Mike
weighs the extra API-call cost differently than this recommendation assumes.

### 3.2 Optional cleanup: should Stage 3 also migrate to the new shared helper?

`implementation_coordinator.py` already has its own inline, working,
live-verified `service_root` resolution logic from Item #24. §2.1 proposes a new
shared `resolve_service_root()` helper for QA/Security to prevent a *third* independent
copy. **Not proposed as required work here** — Stage 3's existing logic is not broken
and touching working, already-verified code carries real risk for zero functional
benefit. Flagging as an option only: if Mike wants full consistency (one helper, three
callers) this is a small, low-risk follow-up, but it's explicitly not part of this
spec's scope unless Mike asks for it.

### 3.3 QA's Layer 2 raise and the retry-attempt counter

§2.2 proposes that a missing-directory raise should **not** count against QA's
`_MAX_RETRIES = 3` budget, on the reasoning that the request never actually ran
against real code (same category as Stage 3's own Layer 2 raise, which isn't a
counted "attempt" either). Flagging this explicitly rather than assuming it — if Mike
would rather this *does* count (e.g. to surface repeated Enhancement-targeting
failures as their own retry-exhaustion signal), that's a one-line change but changes
the failure semantics Mike should confirm rather than Claude Code picking silently.

---

## 4. Out of scope

- **Item #26 (no human gate before Deploy)** — completely separate architectural
  question; this spec does not touch `06-deploy.yml`'s trigger logic at all. Note for
  live verification in §5: because #26 is unresolved, a genuinely successful QA+Security
  re-run against PR #32 **will** auto-trigger a real Deploy the instant both labels land
  — see §5's explicit callout before running that step.
- `implementation_coordinator.py` — untouched unless Mike picks §3.2.
- Items #1, #7, #9, #10, #11, #12 — untouched, unrelated.
- Re-litigating Item #24 itself — it's done, live-verified, not part of this spec's
  surface area.

---

## 5. Live verification

**Use tracking issue `forge-template#10` / `forge-demo-apps#32` as the verification
vehicle** — it's the real, live evidence of the gap this spec closes, already sitting
in exactly the right state (`qa-approved` only, no `security-approved`).

1. Confirm issue #10 and PR #32's live label state matches what was left at session
   close (2026-08-28 verification: `qa-approved` only) before touching anything.
2. **Before re-dispatching QA/Security for real: explicitly confirm with Mike that
   triggering a real, successful QA+Security pass against PR #32 is acceptable, given
   that Item #26 means a real Deploy will fire automatically the instant both labels
   land** — this is a live, billable Azure Container App deployment of REQ-2026-04's
   actual enhancement, the same category of event as Incident #1 earlier in the
   Item #24 session, except this time deliberate rather than accidental. Do not proceed
   past this point without that explicit confirmation.
3. Once confirmed: manually replay the `feature-pr-opened` `repository_dispatch` (or
   equivalent existing manual-retry mechanism already used for QA retries) against
   PR #32 to re-run both QA and Security with the fix in place.
4. Confirm QA now resolves `services/REQ-2026-03/` as the real target, runs real
   `dotnet test`/`npm test` against the actual changed files (not `not_applicable`),
   and applies `qa-approved` for a genuine reason this time — or reports genuine test
   failures if the real enhancement code has any, which is itself a valid outcome to
   report back rather than something to route around.
5. Confirm Security now resolves the same real target, runs all three scanners for
   real without crashing, and applies `security-approved` (or a genuine Critical
   finding, again a valid real outcome) — confirm no unhandled traceback anywhere in
   the job log.
6. Confirm, via the real GitHub API label state (not assumption), whether Deploy fired
   as a consequence — expected per Item #26's current unfixed state — and report the
   resulting Container App/deployment status back explicitly.
7. Confirm a genuinely new or existing Greenfield PR's QA/Security run is completely
   unaffected — no `--existing-service` flag sent, identical behavior to before this
   fix, using §1.6's baseline for comparison.
8. Report all live evidence (job log excerpts, label states, PR/comment links, Deploy
   outcome) back explicitly — same "real executed evidence before closing" bar as
   every other item.

Do **not** treat a passing `--dry-run` as sufficient for §2.2/§2.3's core fix — like
Item #24's §2.2, there's no cheap substitute for a real checkout-backed QA/Security run
against the actual PR #32 state.

---

## 6. Sequencing

1. §1 investigation — all six points, reported back before any code is written.
2. §3.1's fork resolved by Mike (or defaulted per the recommendation) before §2.1 is
   written, since it determines §2.1's actual implementation shape.
3. §2.1 (Enhancement-target resolution, shared helper) — foundational; §2.2 and §2.3
   both depend on `--existing-service` existing and being correctly resolved in both
   workflows.
4. §2.2 (QA fail-loud fix) and §2.3 (Security fail-loud fix) — can proceed in either
   order or in parallel, both depend only on §2.1.
5. §2.4 — confirm as a check, not a separate code change.
6. §5 live verification via tracking issue #10 / PR #32 — **gated on Mike's explicit
   go-ahead per §5 step 2**, given the real-Deploy consequence.
7. `CLAUDE.md` close-out: mark Item #25 resolved with the real fix narrative and live
   evidence, same format as Item #24's entry.

---

## Next chat after this one (Claude.ai)

Once Claude Code reports back with live-verification evidence, fold the outcome into a
fresh context doc, close Item #25 in CLAUDE.md, and reconcile `FORGE-Open-Items-
Backlog-v1.md`'s stale numbering (its old "#23" = CLAUDE.md's current #24; #25/#26 need
adding to that doc too — still outstanding per v70's "On the horizon"). Item #26 (human
gate before Deploy) remains open as a genuine Document 6 architecture question for Mike,
separate from this spec.
