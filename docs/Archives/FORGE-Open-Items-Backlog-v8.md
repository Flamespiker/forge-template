# FORGE — Open Items Backlog: Planning for Next Session(s)

**Prepared:** 2026-09-01 (Claude.ai)
**Supersedes:** v7 (2026-09-01, same day) — Items #35, #36, #37 all resolved
and live-verified this session against the real setup. One new item (#41)
surfaced as a direct consequence of #37's investigation. **8.4 still not
closed** — the real-setup fix is proven, but the fresh-clone scratch retest
(proving a *new* OM gets a green run too) is still outstanding.

**Headline finding from this pass:** The connectivity-check 404 from the 8.4
investigation is gone, confirmed via a real live run
(`https://github.com/Flamespiker/forge-template/actions/runs/33547029934`) —
both `verify` and `managed-agents-check` jobs green, values flowing end to
end through the new `${{ vars.* }}` indirection rather than being
hardcoded-differently. Along the way, answering Item #37 properly (not
guessing) surfaced a real architectural fact worth its own decision: **this
repo is confirmed `is_template: true`** — it serves as both Mike's live FORGE
instance *and* the public template source simultaneously, so its `ado:`
block's real live values (`spike99`/`FORGE-Build`) get copied verbatim into
every new "Use this template" instantiation. That's now Item #41, a design
decision, not something resolved silently.

---

## Design / Policy Decisions — need Mike's call, not a spec

### Item #38 — Single-repo model unsupported, undocumented
Unchanged from v7 — still open, still not urgent.

### Item #39 — GitHub required-reviewers protection needs a paid plan on private repos
Unchanged from v7 — doc fix + the real-stakes follow-up check (does
`forge-demo-apps`'s `production` environment actually have protection active
today?) both still open.

### Item #41 (new) — `forge-template` conflates "Mike's live instance" and "public template source"
Confirmed this session: `forge-template` is `is_template: true`, and a real
`gh repo create --template ...` test (during the #37 investigation) proved
`team/config.yaml` — including its live `spike99`/`FORGE-Build` `ado:` block
values — gets copied verbatim into every new instantiation. This isn't
hypothetical; it's the actual current behavior of the actual public repo.
**Decision needed:** is this acceptable (a new OM is expected to overwrite
`config.yaml` anyway as their first setup step, so inheriting real-but-wrong
starter values is just a slightly confusing default), or does the dual role
need untangling — e.g. a `config.yaml.example` template file kept separate
from the real live `config.yaml`, with the latter gitignored or otherwise
excluded from what "Use this template" copies? No urgency — nothing is
broken today — but worth a deliberate call rather than leaving Mike's own
org/project name as the silent default for anyone who ever uses the public
template.

---

## Bookkeeping — no spec needed, just do directly

### Item #40 — Doc-completeness batch (5 small gaps from 8.4 walkthrough)
Unchanged from v7 — still open: Build Plan reference undefined in README's
table, ACR creation steps undocumented, no doc'd way to confirm Anthropic
key is active, README Step 5's misleading Container App sizing placement,
ADO PAT creation UI mechanics undocumented. Also still open: deciding where
`phase8-4-gaps.md` (verbatim gap log) should permanently live.

### Item #42 (new, minor) — Node.js 20 deprecation warning on `actions/checkout@v4`/`actions/setup-python@v5`
Surfaced as an unrelated annotation during this session's verification run,
out of scope for the #35 task itself. Low priority — GitHub Actions
deprecation warnings, not a functional break yet — but worth bumping action
versions sometime before it becomes a hard failure.

---

## Accepted ongoing process — decided, no fix planned

### PR self-approval / branch-protection deadlock — decided 2026-08-31, keep the manual workaround
Unchanged from v7.

---

## Deliberately left as-is — not being pursued

### Item #7 — Archive-prefix mismatch (REQ-2026-02, once)
Unchanged from v7.

---

## Accepted ongoing risk — tracked, no fix planned

### Item #11 — 21 `next@14.2.35` CVE findings have no 14.x backport
Unchanged from v7.

---

## Resolved since v1 (2026-08-24) — historical record, not action items

Full narratives live in CLAUDE.md's Open Items / Known Gaps section and the
relevant `docs/FORGE-Item*-Spec.md` files — this is a one-line-each index so
this doc doesn't need re-deriving from scratch again next time.

| Item | One-line resolution | Date | Commit(s)/PR(s) |
|---|---|---|---|
| #1 | Deploy Agent had no app-secrets wiring mechanism, and no way to discover in advance that a given app needs a given secret | fully resolved 2026-08-31 | 2026-08-31 | `29073cd`, `6d1511c`, `a21b4a9`/`forge-demo-apps#35` |
| #2–#6, #8–#31 | See Backlog v5 for the full historical index — unchanged, not reproduced here | — | — |
| #32 | `create_ado_items.py` created a new parallel Epic for every Enhancement instead of linking to the existing service's real Epic | RESOLVED 2026-08-31 | 2026-08-31 | `bbbe3d0`, `759cc58`, `c4b3d0c` |
| #33 | `forge-template#10` left open despite the pipeline completing and deploying | RESOLVED 2026-08-31 | 2026-08-31 | — |
| #34 | Stage 3 (Implementation Coordinator) had no cost visibility before or after a real Managed Agents run | RESOLVED 2026-08-31 — see v6 for full writeup | 2026-08-31 | `1aee048`, `363067b` + 5 build commits; forge-demo-apps `#39`, `#41` |
| — | 06_Orchestration_v7.md missing `AZURE_STAGING_CREDENTIALS` | RESOLVED 2026-09-01 | 2026-09-01 | `56361cd` + separate doc-only commit |
| — | Phase 2.9 (Managed Agents access check) had no repeatable, discoverable mechanism for a new OM | RESOLVED 2026-09-01 — new `managed-agents-check` job, full parity with 2.8 | 2026-09-01 | `56361cd` |
| #35 | `verify-setup.yml` (and 8 other stage workflows, two layers deep) hardcoded `forge-demo-apps`/`spike99`/`Flamespiker` instead of reading config — new OM got a real 404 on a fresh clone | **RESOLVED 2026-09-01** — repo Variables (`FORGE_TARGET_REPO`, `FORGE_GITHUB_OWNER`, `FORGE_ADO_ORG_URL`) added; Layer 1 (env blocks, 9 workflows) and Layer 2 (App-token/checkout steps, 5 workflows) both fixed to reference `${{ vars.* }}`; `qa_agent.py`/`security_agent.py` silent-fallback defaults changed to fail loud. Live-verified: real run green, 404 gone. | 2026-09-01 | `d40b761`, `5b8ace6`, `71424df` |
| #36 | `team/config.yaml` had three mutually incompatible schemas across README, OM Guide, and the real shipped file — neither doc's example keys existed in the real file at all | **RESOLVED 2026-09-01** — trimmed to the two live-read blocks (nested `ado:` + `container_apps.staging`), dead keys removed, both docs corrected to match real schema exactly; OM Guide's fictional "repo path" intake alternative flagged (only `issue-attachment` exists in code) | 2026-09-01 | `53b3fd5`, `baddc8c` |
| #37 | `team/config.yaml`'s `ado:` block shipped real live values (`spike99`/`FORGE-Build`), not placeholders | **Investigated, not "fixed" as originally framed** — confirmed these are correct, intentional values for the live deployment; trimming dead keys around them (in #36) was the right action. Revealed the real issue is architectural (dual live-instance/template-source role) — see new Item #41. | 2026-09-01 | `53b3fd5` |

---

## Suggested sequencing

1. **8.4 close-out (immediate next step)** — run the fresh-clone scratch
   retest (repo Variables set for a throwaway target repo, same
   isolated-resource-group pattern as the original 8.4 walkthrough) to
   prove a genuinely new OM gets a green `verify-setup.yml` run too, not
   just the real live setup. Once green, check off 8.4 and unblock 8.5
   (`v1.0.0` tag).
2. **Item #41** — design decision on the template/live-instance role
   conflation. No urgency, but worth deciding before too many external
   users start from the public template.
3. **#38, #39** — unchanged from v7, still open design calls.
4. **#40, #42** — clubbable, low-priority bookkeeping. Do whenever
   convenient, could combine with #41's fix if that ends up being
   doc-only.
5. **Items #7, #11** — leave as-is, unchanged.
6. **Configurable Pipeline Depth** — still unblocked, still un-numbered,
   still no urgency. Unchanged from v7.
7. **Cost baseline recalibration** — unchanged from v7, still not urgent.
