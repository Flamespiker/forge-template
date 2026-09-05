# FORGE — Open Items Backlog: Planning for Next Session(s) (v10)

**Prepared:** 2026-09-05 (Claude.ai)
**Supersedes:** v9 (2026-09-01) — held pending Item #57's resolution per v9's own note; #57
resolved via supersession (Fiddy5's Vercel+Supabase replatform, not a code fix) this session,
clearing the gate. This version consolidates straight through to #61 in one jump, not a
v10-then-v11 sequence, per that same held decision.
**Section order changed from v9:** "Real Bugs" now sits after Design/Policy Decisions and
before Bookkeeping, per the placement decided in v88. Suggested Sequencing is renumbered fresh
below, not preserved around removed/resolved lines.
**Scope note:** this doc tracks FORGE's own engine-level items only, per this session's
scoping decision — items #55–#58 (Fiddy5-specific Azure bugs) are indexed below only as
one-line superseded pointers; their full narrative now lives with Fiddy5's own project once
that's stood up, not here.

---

## Design / Policy Decisions — need Mike's call, not a spec

### Item #38 — Single-repo model unsupported, undocumented
Unchanged since v7 — still open, still not urgent.

### Item #39 — GitHub required-reviewers protection needs a paid plan on private repos
Unchanged since v7 — doc fix + the real-stakes follow-up check (does any live repo's
`production` environment actually have protection active today?) both still open. **Newly
relevant:** this session found `mike-digital-platform`'s `main` has zero branch protection at
all (see Item #60) — worth resolving both together rather than treating #39's paid-plan
question and #60's "no protection exists yet" separately.

### Item #41 — `forge-template` conflates "Mike's live instance" and "public template source"
Unchanged since v9 — still open, still no urgency, still worth a deliberate call before too
many external users start from the public template.

### New: Deploy Agent Multi-Platform Support — major initiative, spec'd not built
`Deploy-Agent-Multi-Platform-Spec-v2.md` — generalizes Deploy from Azure-Container-Apps-only
into a `DeployPlatform` adapter abstraction (shape-classified: container / serverless-function
/ BaaS), covering Azure, Google Cloud Run, AWS (two sub-adapters), and Vercel+Supabase.
Core-layer per `04_Governance-v2.md`; should go through the RFC process before merging to
`core/`. Five-phase rollout, Phase 1 (Google Cloud Run) the next real build candidate — see
Suggested Sequencing below. Also the natural home for Item #58's generalized insight (Deploy
never provisions app-level databases) — each adapter's contract includes DB provisioning, not
a standalone backlog item anymore.

---

## Real Bugs — open, not yet fixed at the code level

### Item #44 — `run_cost_estimate()` reads `tasks.md` from `main`, not the design branch
404s if `design-approved` is applied before the design PR merges — the exact label order
Document 6/the Orchestration Guide describes as correct. Worked around live via merge-then-
retry; not fixed at the code level. Unchanged since discovery (2026-09-03).

### Item #47 — Blank intake "Request ID" silently resolves to `request_id="unknown"`
No warning surfaced anywhere; no supported code path to correct it after the fact once
`resolve_request_id()` has picked up the wrong marker. Proposed fix (not built): reject a
blank Request ID outright at Stage 0, or at minimum a loud warning banner on Intake Agent's
first comment. Unchanged since discovery (2026-09-04).

### Item #51 — `create_ado_items.py` has zero idempotency protection
Every re-trigger of `02-design.yml` creates a full duplicate Epic→Features→User-Stories tree.
Real fix needs a check against `docs/<request-id>/ado-work-items.json` for already-populated
real ADO IDs, or a query against ADO for an existing matching Epic. Unchanged since discovery
(2026-09-05). **Note:** this is exactly the failure mode Item #61's deferred 02-design.yml
verification is avoiding re-triggering — the two items compound each other's risk until #51
is actually fixed.

### Item #53 — QA's retry-limit guard doesn't block a 4th attempt
Attempt-3 report text says "no further retries" but the label applied (`qa-loop-back`) doesn't
match the guard's actual check (`qc-retry-limit-reached`, which only applies at `attempt > 3`).
Confirmed live: a 4th attempt runs and can pass. Needs either the message softened or the
threshold changed to match stated intent. Unchanged since discovery (2026-09-05).

### Item #59 (new) — `04-qa.yml` has Supabase-specific env vars hardcoded into a shared file
Added to fix a real Fiddy5 QA build failure (placeholder `NEXT_PUBLIC_SUPABASE_URL`/
`NEXT_PUBLIC_SUPABASE_ANON_KEY`), but landed in core, not scoped to Fiddy5 — every future app's
QA run inherits these regardless of stack. Real fix needs an app-declared manifest of required
build-time env vars, same shape as the multi-platform spec's adapter-declares-requirements
pattern. Open.

### Item #60 (new) — `mike-digital-platform`'s `main` has zero branch protection
Confirmed via 404 twice during this session's PR #3 merge. Not consequential while Deploy
Agent had no real wiring to this repo; now that it does, worth a required-status-check rule.
Blocked on a small wiring question first: `qa-approved`/`security-approved` are tracking-issue
labels today, not GitHub PR status checks, so "required status check" needs that translated
before the rule can reference them. Open.

---

## Bookkeeping — no spec needed, just do directly

### Item #40 — Doc-completeness batch (5 small gaps from 8.4 walkthrough)
Unchanged since v7 — still open.

### Item #42 — Node.js 20 deprecation warning on `actions/checkout@v4`/`actions/setup-python@v5`
Unchanged since v7 — still low priority, still open.

### Item #62 (new) — Documentation audit remediation
First surfaced in `FORGE-context_v88.md`, never previously entered into this backlog file.
Stale docs needing re-upload to project knowledge: `06_Orchestration` (multiple versions
behind live), `FORGE_Build_Plan` (Phase 8 closure not reflected), product spec (missing an
Item #43 feature bullet), architecture doc + Customization Ref (both have live "post-review
addition" text with no version bump — flagged as a systemic risk: matching filename/version
alone isn't a safe staleness check). Missing entirely: `03_FORGE_Tooling_v8.md`. Orphaned (zero
live references): `FORGE-commercial-alternatives-and-justification.md`, `doc2-change-brief.md`,
the standalone `ADR-0011.md` copy. Hygiene: `docs/FORGE-Open-Items-Backlog-v6/v7/v8.md` still
sitting at `docs/` root instead of `docs/Archives/`, per CLAUDE.md's own archival convention.
Clubbable — batch into one documentation-focused session rather than piecemeal.

---

## Accepted ongoing process — decided, no fix planned

### PR self-approval / branch-protection deadlock on `forge-template`
Unchanged since v7 — keep the manual workaround (temporarily drop required reviewer count to
0, merge, restore to 1).

---

## Deliberately left as-is — not being pursued

### Item #7 — Archive-prefix mismatch (REQ-2026-02, once)
Unchanged since v7.

---

## Accepted ongoing risk — tracked, no fix planned

### Item #11 — `next@14.2.35` CVE findings have no 14.x backport
Unchanged since v7. **Reinforced this session** — Items #52/#54's new npm-audit scanner
independently found the same category live on Fiddy5 (21 CVEs, no 14.x backport, published
after 14.2.35 shipped) — same accepted-risk category, not a new finding requiring separate
tracking.

---

## Resolved since v1 (2026-08-24) — historical record, not action items

Full narratives live in CLAUDE.md's Open Items / Known Gaps section and the relevant spec
docs — this stays a one-line-each index so this doc doesn't need re-deriving from scratch.

| Item | One-line resolution | Date |
|---|---|---|
| #1 | Deploy Agent had no app-secrets wiring mechanism | 2026-08-31 |
| #2–#31 | See Backlog v5/v9 for the full historical index — unchanged, not reproduced here | — |
| #32 | `create_ado_items.py` created a duplicate Epic per Enhancement instead of linking to the existing one | 2026-08-31 |
| #33 | Tracking issue left open despite pipeline completing | 2026-08-31 |
| #34 | Stage 3 had no cost visibility before/after a real Managed Agents run | 2026-08-31 |
| #35 | 9 workflows hardcoded `forge-demo-apps`/`spike99`/`Flamespiker` instead of reading config | 2026-09-01 |
| #36 | `team/config.yaml` had three mutually incompatible documented schemas | 2026-09-01 |
| #37 | Investigated, not "fixed" — live `ado:` values confirmed intentional; revealed Item #41 | 2026-09-01 |
| #43 | No way to declare pipeline depth at intake — new Intake field, 4-tier contiguous-prefix selector, live-verified 3x | 2026-09-03 |
| #45 | Platform-swap target repo created but never seeded — real Stage 1 failure | 2026-09-04 |
| #46 | `_MAX_TOKENS` truncation (Requirements, then Design) — root-fixed via unconditional streaming in the shared agent wrapper | 2026-09-04 |
| #48 | Stage 3 coordinator ended its turn without packaging — recovered via follow-up message, no cost lost; surfaced and fixed a real `list_session_output_files()` pagination-limit bug along the way | 2026-09-04 |
| #49 | Platform swap shipped with none of the cross-repo dispatch workflows — QA/Security/Deploy would never have fired; reconstructed and committed reference copies into `forge-template` itself so this can't recur unrecoverably | 2026-09-04 |
| #50 | Dependabot 403 on the swapped target — two manual permission steps, resolved; immediately surfaced Item #52 | 2026-09-05 |
| #52 | Security Agent's Dependabot check structurally can't see a Greenfield PR's own dependencies pre-merge — built `npm audit`/`dotnet list package` as a free substitute | 2026-09-05 |
| #54 | The new npm-audit scanner (#52's own fix) silently treated a missing lockfile as a clean scan — fixed via on-the-fly lockfile generation + explicit error-shape check | 2026-09-05 |
| #55 | Frontend lockfile never committed for a genuinely new frontend — two-layer fix (Deploy Agent self-heal-and-commit + Implementation-stage prompt/packaging fixes) built and live-verified for 3 of 4 test scenarios; Test 2 (real Stage 3 run) deliberately deferred, cost/time reasons | 2026-09-04/05 |
| #56 | Google sign-in / household-creation gap on Fiddy5's original Azure deployment | **superseded** by the Vercel+Supabase replatform 2026-09-05 — moot once the .NET backend was retired; full narrative moves with Fiddy5's own project |
| #57 (original) | `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_API_BASE_URL` name mismatch on Fiddy5's Azure deployment | **superseded** by the replatform, same as #56 |
| #58 | No database ever provisioned for a Greenfield app on any platform — systemic gap | **superseded for Fiddy5** by the replatform (Supabase's own Postgres); **generalized form lives on** as a required capability in every Deploy Platform Adapter's contract, per the multi-platform spec — not tracked as a standalone item anymore |
| #61 (new) | Enhancement-detection step hard-failed on any ad hoc issue that never went through Intake — fixed with an `--optional` download flag, live-verified for 03-implementation.yml/04-qa.yml/05-security.yml. **Caveat, not fully closed:** 02-design.yml's identical fix is applied but deliberately not live-fired (would risk a real duplicate ADO tree per Item #51, and a real costed Design run for an already-built app); 06-deploy.yml's fix similarly applied but only syntax/diff-validated, not live-fired (would risk a real Azure deploy attempt). Both deferred to the next request that naturally reaches that stage, same shape as Item #55's Test 2. | 2026-09-05 |

---

## Suggested sequencing

Fresh numbering — does not preserve v9's sequence around resolved/removed lines.

1. **Deploy Agent Multi-Platform Spec, Phase 1** — build the `google-cloud-run` adapter.
   Lowest-risk second adapter (same container contract as Azure), proves the adapter interface
   itself before the bigger BaaS-shape work.
2. **Items #44, #47, #51, #53** — four real, unfixed pipeline bugs, all found live over the
   past few days, all still open. None urgent individually, but each will keep recurring on
   every future request that happens to hit its trigger condition. Worth a batched fix pass
   rather than picking them off one at a time as they bite again.
3. **Item #60** — branch protection on `mike-digital-platform`, once the labels-to-status-
   checks wiring question is resolved. Quick once unblocked.
4. **Item #59** — will matter concretely the moment a second Greenfield app builds a different
   frontend stack; worth having the app-declared-manifest fix ready before that happens rather
   than after.
5. **Items #38, #39, #41** — design/policy decisions, no urgency, revisit whenever convenient.
6. **Item #62** — documentation audit remediation, batchable into one session.
7. **Items #40, #42** — low-priority bookkeeping, clubbable with #62.
8. **Items #7, #11** — leave as-is, unchanged, no action.
