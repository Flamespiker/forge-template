# FORGE — Open Items Backlog: Planning for Next Session(s)

**Prepared:** 2026-09-01 (Claude.ai)
**Supersedes:** v6 (2026-08-31) — Phase 8.4 (fresh-clone walkthrough of setup
steps 2.1–2.9) ran this session and surfaced 12 real doc/code gaps. Six are
new numbered items below (#35–#40); the rest are folded into #40 as a
clubbable doc-fix batch. **8.4 itself is not yet closed** — it's blocked on
#35 and #36, see "Suggested sequencing."

**Headline finding from this pass:** The Managed Agents parity work (new
`managed-agents-check` job in `verify-setup.yml`) is fully real and works
cold, on a genuinely fresh clone, from public docs alone — that part of 8.4
passed clean. But the connectivity check — the thing 8.4 was specifically
built to validate — **cannot currently pass for anyone except the exact real
setup**, because `verify-setup.yml` hardcodes `forge-demo-apps`/`spike99`
instead of reading `team/config.yaml` (#35), compounded by `config.yaml`
itself having three mutually incompatible schemas across README, the OM
Guide, and the real shipped file (#36). This is a live defect in the shipped
template, not a fresh-clone artifact — confirmed by a real 404 during the
walkthrough. Full verbatim gap log from the session: `phase8-4-gaps.md`
(scratch, not yet landed anywhere permanent — worth deciding where this
lives, see #40).

---

## Design / Policy Decisions — need Mike's call, not a spec

### Item #38 — Single-repo model unsupported, undocumented
All three setup docs (README, OM Guide, Customization Ref) assume the
two-repo model (FORGE repo vs. target monorepo) and never address what a new
OM should do with only one repo available. During 8.4's walkthrough, Claude
Code CLI had to make a judgment call (used one scratch repo for both roles)
with no doc guidance either way.
**Decision needed:** is single-repo a real supported configuration worth
documenting, or is two-repo a hard requirement worth stating explicitly as
such (so a new OM doesn't waste time trying to make one repo work)? Either
answer is a small doc fix once decided — the open question is which one.

### Item #39 — GitHub required-reviewers protection needs a paid plan on private repos
Neither doc mentions that GitHub's required-reviewers protection rule needs
Team/Enterprise billing for private repos (public repos get it free). Hit a
real 422 creating `forge-8-4-scratch`'s `production` environment protection
rule during 8.4; per Mike's call, left it unprotected in the scratch test
rather than change repo visibility to work around it.
**Two things bundled here, need Mike's call on priority/order:**
1. Doc fix — note the plan restriction so a new OM isn't confused by the 422.
2. **Follow-up check (real stakes):** this gap means `forge-demo-apps`'s own
   `production` environment may not actually have required-reviewer
   protection active today, silently. Worth an investigation-first check
   against the real repo before assuming it's fine.

---

## Real Bugs — well-scoped, good spec-and-fix candidates

### Item #35 (major) — `verify-setup.yml` hardcodes repo/org instead of reading `team/config.yaml`
Confirmed live during 8.4: the connectivity-check job hardcodes
`forge-demo-apps` and `spike99` directly in code rather than reading
`team/config.yaml`. Ran the real workflow against the 8.4 scratch setup —
`managed-agents-check` passed fully; `verify` (connectivity) failed
immediately with a real 404 (`GET .../forge-demo-apps/installation`) because
the scratch App was correctly scoped to the scratch repo, not
`forge-demo-apps`. **A new OM cannot get a green `verify-setup.yml` run
following only the public docs.** This is the item directly blocking 8.4's
close-out. Likely needs #36 resolved first or alongside, since the fix here
is "read from config.yaml" and config.yaml's own schema is currently a mess.

### Item #36 (major) — Three incompatible `team/config.yaml` schemas
README's example, the OM Guide's example, and the real shipped file each use
different, mutually incompatible key schemas (e.g. README:
`target_repo`/`staging_env`; OM Guide: `ado.organization`/`monorepo.owner`;
real file: `ado_org`/`monorepo_name` plus a separate trailing `ado:` block).
**Neither doc's example keys exist in the real file at all** — a new OM
following either doc literally would edit fields that silently do nothing.
Needs a single canonical schema decided, then both docs corrected to match
the real file (or the real file corrected to match a newly-chosen canonical
shape — Mike's call on which direction, since #35's fix depends on knowing
the final shape).

### Item #37 — Template's `team/config.yaml` ships real live values, not placeholders
Not a doc-wording gap — a template hygiene issue. The real file's trailing
`ado:` block ships with live real values (`spike99`/`FORGE-Build`), inherited
by every new "Use this template" instantiation. Mechanical fix once #36
settles the schema: replace with placeholders. Low risk, no design call
needed — can be done directly alongside #36's fix.

---

## Bookkeeping — no spec needed, just do directly

### Item #40 — Doc-completeness batch (5 small gaps from 8.4 walkthrough)
Clubbable — same pattern as prior doc-fix batches. All low-risk, mechanical:
- **1.** OM Guide Step 6 references "Build Plan step 2.8/2.9" but "Build
  Plan" is never defined or linked in README's reference table — a new OM
  has no way to find this document.
- **5.** No doc explains how to actually create the ACR (SKU, naming,
  `az acr create`) — only how to read credentials from one that already
  exists. Live-confirmed: a fresh ACR has `adminUserEnabled: false`, so
  `ACR_USERNAME`/`ACR_PASSWORD` don't exist until the admin user is
  explicitly enabled — undocumented anywhere.
- **6.** No doc describes how to confirm the Anthropic key is "active."
  (Walkthrough improvised a live `POST /v1/messages` call as the check.)
- **7.** README Step 5 places Container App sizing (replicas/vCPU/memory)
  directly after the `az containerapp env create` command, implying it's
  part of environment creation. Confirmed via `--help`: no such flags exist
  on that command — sizing only applies to an actual Container App, created
  later. Misleading ordering, not a factual error.
- **9.** Same pattern as #5: no doc explains the ADO PAT creation UI
  mechanics (where in ADO, what scope to select).

Also: decide where `phase8-4-gaps.md` (the full verbatim gap log from this
session) should permanently live — currently sitting in a deleted scratch
repo's local checkout only, not landed anywhere durable.

---

## Accepted ongoing process — decided, no fix planned

### PR self-approval / branch-protection deadlock — decided 2026-08-31, keep the manual workaround
Unchanged from v6.

---

## Deliberately left as-is — not being pursued

### Item #7 — Archive-prefix mismatch (REQ-2026-02, once)
Unchanged from v6.

---

## Accepted ongoing risk — tracked, no fix planned

### Item #11 — 21 `next@14.2.35` CVE findings have no 14.x backport
Unchanged from v6.

---

## Resolved since v1 (2026-08-24) — historical record, not action items

Full narratives live in CLAUDE.md's Open Items / Known Gaps section and the
relevant `docs/FORGE-Item*-Spec.md` files — this is a one-line-each index so
this doc doesn't need re-deriving from scratch again next time.

| Item | One-line resolution | Date | Commit(s)/PR(s) |
|---|---|---|---|
| #1 | Deploy Agent had no app-secrets wiring mechanism, and no way to discover in advance that a given app needs a given secret | fully resolved 2026-08-31 — Option 3 and Option 1 both live-verified | 2026-08-31 | `29073cd`, `6d1511c`, `a21b4a9`/`forge-demo-apps#35` |
| #2–#6, #8–#31 | See Backlog v5 for the full historical index — unchanged, not reproduced here | — | — |
| #32 | `create_ado_items.py` created a new parallel Epic for every Enhancement instead of linking to the existing service's real Epic | RESOLVED 2026-08-31 | 2026-08-31 | `bbbe3d0`, `759cc58`, `c4b3d0c` |
| #33 | `forge-template#10` left open despite the pipeline completing and deploying | RESOLVED 2026-08-31 | 2026-08-31 | — |
| #34 | Stage 3 (Implementation Coordinator) had no cost visibility before or after a real Managed Agents run | **RESOLVED 2026-08-31** — see v6 for full writeup | 2026-08-31 | `1aee048`, `363067b` + 5 build commits; forge-demo-apps `#39`, `#41` |
| — | 06_Orchestration_v7.md missing `AZURE_STAGING_CREDENTIALS` (Step 4 table, Step 6 checklist, stale caution note) | RESOLVED 2026-09-01 | 2026-09-01 | `56361cd` (managed-agents-check parity commit) + separate doc-only commit |
| — | Phase 2.9 (Managed Agents access check) had no repeatable, discoverable mechanism for a new OM — was throwaway-only | RESOLVED 2026-09-01 — new `managed-agents-check` job added to `verify-setup.yml`, full parity with 2.8; two superseded gitignored scripts deleted | 2026-09-01 | `56361cd` |

---

## Suggested sequencing

1. **#35 + #36 together** — the two items actually blocking Phase 8.4's
   close-out. #36 (schema) likely needs deciding first since #35's fix
   ("read from config.yaml") depends on knowing the final canonical shape.
   Recommend investigation-first pass on both together next session.
2. **#37** — mechanical, do alongside #35/#36 once the schema's settled.
3. **#38, #39** — design decisions needed from Mike; not urgent, but #39's
   follow-up half (checking `forge-demo-apps` production's real protection
   status) has real stakes and shouldn't wait too long.
4. **#40** — clubbable doc-only batch, low risk, do whenever convenient.
5. **8.4 close-out** — re-run the fresh-clone walkthrough (or at minimum
   just the `verify-setup.yml` connectivity check on a fresh scratch clone)
   once #35/#36 land, to get a genuine green run before checking off 8.4
   and unblocking 8.5 (`v1.0.0` tag).
6. **Items #7, #11** — leave as-is, unchanged.
7. **Configurable Pipeline Depth** — still unblocked, still un-numbered,
   still no urgency. Unchanged from v6.
8. **Cost baseline recalibration** — unchanged from v6, still not urgent.
