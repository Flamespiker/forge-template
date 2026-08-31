# FORGE — Session Context v80

**Session date:** 2026-08-31 (Claude.ai)
**Carries forward from:** v79, unchanged except where noted below.

---

## What changed this session

### 1. Item #25 — narrative gap corrected (resolved)

CLAUDE.md's Item #25 write-up described the stale-code re-dispatch incident
as a single event; live GitHub Actions API evidence confirmed it actually
happened twice on 2026-08-28 (03:55 and 22:27 runs), identical failure
signature both times (QA false-passing, Security crashing with a raw
`FileNotFoundError`). CLAUDE.md corrected to describe both occurrences in
full detail; two notes in `docs/FORGE-pipeline-cost-log.md` that had
flagged this as an open discrepancy were reworded to point at the fix
instead of describing it as unresolved.

**Commit:** `8d97bfc`.

### 2. Item #1 — fully resolved (both Option 3 and Option 1 now live)

Option 3 (reactive post-deploy crash-loop flag) was already live-verified
as of 2026-08-31 per v79's successor state — this session closed the other
half.

**Option 1 (pre-merge secrets-declaration flag), per Mike's three explicit
choices:**
- Detection signal: **declaration-only** — flags if `design.md`'s
  `## Required Secrets` section is missing, does not cross-check against
  code (a code cross-check has a structural blind spot for
  framework-consumed secrets like NextAuth's `NEXTAUTH_SECRET`/
  `NEXTAUTH_URL`, confirmed via investigation — they never appear in
  application source at all).
- Location: **Stage 3** (`implementation_coordinator.py`), not Stage 6 —
  earliest point `design.md` and final generated code coexist, flags before
  merge rather than after deploy.
- Authorship: **`design_agent.py` generates the section unconditionally**
  at Stage 2, every time, even "None identified" — makes the section's
  absence an unambiguous signal.

**Built and verified:**
- `29073cd` — `design_agent.py` prompt requirement (Greenfield + Enhancement
  both covered by the shared prompt).
- `6d1511c` — `implementation_coordinator.py`:
  `_detect_missing_secrets_declaration()` +
  `_build_secrets_declaration_flag()`, threaded through
  `_commit_and_open_pr()` via two distinct parameters
  (`missing_secrets_declaration: bool`,
  `secrets_check_fetch_error: str | None`) so a genuine fetch failure never
  collapses into the same wording as a confirmed-missing section. Reuses
  the one existing tracking-issue comment mechanism — no new comment type,
  no new posting infrastructure.
- `a21b4a9` — backfilled `## Required Secrets` into all three real
  `design.md` files (REQ-2026-01/02/03) using this session's own confirmed
  variable names. Opened as `forge-demo-apps#35`, merged via
  `39b99800c06af828183c154e4733437137b8787c`.

**Real-money verification:** `design_agent.py --dry-run` still makes a real
Messages API call (only skips GitHub side effects) — this cost real money
to confirm ($0.405 total across two attempts; see Item #31 below for why
the first attempt bought nothing). Second attempt confirmed the section
renders correctly, including the model correctly applying the
framework-internal distinction to `NEXTAUTH_SECRET`/`NEXTAUTH_URL`
unprompted-by-example.

**§4.5/§4.6 verification:** no flag against a real backfilled service; flag
fires and is non-blocking against a stripped `design.md` (verified via a
monkeypatched unit test — zero live side effects, zero further cost);
confirmed genuinely inert downstream — zero references anywhere in
QA/Security/Deploy agent code or any workflow, and structurally, other
stages' comment-marker matching only keys off `stage=<name>`, never parses
comment body content.

**A real deadlock surfaced and resolved along the way:** merging
`forge-demo-apps#35` hit GitHub's hard self-approval block (same account
opened and would have reviewed the PR) — `enforce_admins: true` (Item #10)
meant no admin bypass either. Resolved once, with Mike's explicit
authorization: `required_approving_review_count` temporarily dropped to 0,
merged, immediately restored to 1 — independently re-verified via a fresh
API read (not the PATCH echo), twice. **This will recur on any future PR
opened under Mike's own account** — flagged as an open process question in
the Open Items Backlog, not resolved permanently this session (see "On the
horizon" below).

**Commits:** `8a7ac46` (CLAUDE.md Item #1 closeout + new Item #31),
`131729a` (Open Items Backlog v2 update). Both pushed to `origin/main`.

### 3. NEW — Item #31 logged: `design_agent.py`'s JSON-parse fragility

Surfaced during Item #1's §4.4 verification, unrelated to the Required
Secrets feature itself: `_parse_model_json()` has zero resilience to a
malformed large JSON-mode response. A real, costed Messages API call
produced a ~12,973-token response that failed `json.loads()` with a
`JSONDecodeError`; `run_design_agent()` re-raises without ever persisting
the raw `output_text` anywhere, so the $0.20 spend bought zero diagnostic
signal. A second identical-prompt retry (using a throwaway capture script,
not the committed code) succeeded — n=2 with 1 failure suggests
intermittent model-output flakiness on long JSON-mode responses, not a
deterministic trigger from the new prompt content, but isn't enough to
confirm root cause either way. **Not yet fixed.** Suggested scope: persist
raw `output_text` on parse failure at minimum, possibly a bounded
retry-on-`JSONDecodeError`, or a more lenient parser.

---

## Open items — updated status

- **Item #1:** **now fully resolved** (this session). Both Option 3 and
  Option 1 live-verified. Remove from "open" going forward. Note:
  `req-2026-01-email-worker` itself is still crash-looping — that's a
  separate, still-open app-level fact, not a gap in this item's mechanism.
- **Item #12:** resolved (v79). Unchanged.
- **Item #25:** **now resolved** (this session). Remove from "open" going
  forward.
- **NEW — Item #31:** `design_agent.py` JSON-parse fragility on large
  responses. Open, not yet fixed. Small, well-scoped, real-bug-adjacent —
  moved into the backlog's "Real Bugs" section (no longer empty).
- **Cost Estimator spec:** unchanged, not yet started.
- **`req-2026-01-email-worker` crash-loop:** unchanged, still pre-existing
  and unfixed. (Item #1's discovery mechanism now exists for the *next*
  case like this — it doesn't retroactively fix this one.)
- **Phase 7 end-to-end Enhancement Workflow validation run:** unchanged
  from v79 — still worth a dedicated fresh-intake pass.
- **NEW — process question (not urgent):** the self-approval /
  `enforce_admins` deadlock hit during PR #35's merge will recur on any
  future PR opened under Mike's own account. Flagged in the Open Items
  Backlog with three options laid out (permanently drop the review
  requirement, route ad hoc PRs through the `forge-pipeline` App identity
  instead, or keep doing the temporary-disable dance each time) — no
  decision made this session.

## Azure infrastructure

Nothing started this session — all work was code/doc commits, GitHub API
calls, and two costed (but non-Azure) Anthropic API calls for §4.4
verification. No shutdown prompt needed. Postgres (`forge-req2026-03-pg`)
was not touched.

---

## On the horizon (unchanged from v79, plus new items above)

- Cost Estimator spec — five open design forks, not yet started
- A dedicated Phase 7 validation run from a genuinely fresh intake
- Item #31 — `design_agent.py` JSON-parse fragility (new this session)
- The self-approval/`enforce_admins` deadlock — permanent decision still
  needed (new this session)
- Ongoing Open Items Backlog discipline
