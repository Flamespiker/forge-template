# FORGE — Open Items Backlog: Planning for Next Session(s)

**Prepared:** 2026-08-24 (Claude.ai)
**Purpose:** A working breakdown of all 10 items still open as of context doc v64, sorted by what kind of work each actually needs, so the next session (Claude.ai spec + Claude Code implementation, or a Mike decision alone) can move efficiently instead of re-deriving this each time.

**This is not itself a set of implementation specs** — items in the "Design/Policy Decisions" section need Mike's judgment before any spec makes sense; items in "Real Bugs" need their own dedicated spec (one at a time, same pattern as the pipeline-hardening spec) once picked; items in "Bookkeeping" are low-effort enough to just do directly without a formal spec cycle.

---

## Design / Policy Decisions — need Mike's call, not a spec

These shouldn't get a Claude Code spec written until Mike has actually decided the direction — writing a spec first would mean guessing at a decision that isn't Claude's to make.

### Item #1 — Deploy Agent has no way to learn an app needs a given secret
The wiring *primitive* (`_wire_keyvault_secret()`) exists and works — the missing piece is how Deploy Agent would ever know, on its own, that a given app needs a given secret in the first place. Every wiring so far has been a manual, one-off CLI invocation. Real options worth Mike weighing:
- A machine-readable declaration convention (e.g. a `secrets.yaml` per service, or a section in `design.md` with a fixed schema Deploy Agent parses)
- Accept this as permanently manual — the primitive exists, tribal knowledge handles the "which secret" question, and that's fine given how infrequently new secrets get introduced
- Something in between (a lightweight convention checked by `_detect_design_gaps()`-style flagging, never blocking)

**Question for Mike:** is this worth solving generally, or is manual-per-secret an acceptable permanent state given how rarely it comes up?

### Item #9 — Ad hoc `fix/*` branches need `--admin` merge (4 occurrences)
`security-check` is currently unsatisfiable on ad hoc fix PRs for structural reasons tied to how the branch-protection rule is scoped. Four admin-merges have happened as a workaround. Options:
- Fix the branch-protection/security-check interaction so ad hoc fix PRs pass normally
- Accept `--admin` merge as standing, expected procedure for this PR shape

**Question for Mike:** is 4 occurrences (and presumably more to come) worth the engineering cost of fixing the underlying rule interaction, or is this an acceptable standing exception?

### Item #10 — `enforce_admins` on `forge-demo-apps` main is `false`
Should arguably be `true` (closing the loophole that lets Item #9's admin-merges happen at all, among other things) — but flipping it back on would also remove the very escape hatch Item #9 currently relies on. These two items are coupled; resolving one changes the other.

**Question for Mike:** decide #9 and #10 together — if #9 gets a real fix, #10 flipping back to `true` becomes safe. If #9 stays as accepted standing procedure, #10 needs to stay `false` to keep that procedure working.

---

## Real Bugs — well-scoped, good spec-and-fix candidates

These are genuine, understood problems that just haven't been picked up yet. Any one of these is a reasonable next spec cycle, same pattern as the pipeline-hardening work.

### Item #6 — `wait_for_all_threads_idle()` can't distinguish "finished" from "every thread hit a fatal session error"
A real bug in Stage 3's Managed Agents coordination logic — worth understanding the current polling/status-check implementation live before scoping a fix (verify current behavior, don't assume from the item's one-line description). Likely fix shape: distinguish a genuine "all subagents completed their work" state from "all subagents errored out and are technically no longer running" — probably needs a per-thread status field checked in addition to the aggregate idle check.

### Item #8 — Implementation Coordinator sometimes generates unrequested `.github/workflows/*.yml` scope creep
Root cause never diagnosed. Before writing a fix spec, this needs an actual investigation pass: pull a real instance of this happening (check past Implementation Coordinator sessions/PRs for an example), and figure out why the subagents are touching workflow files they weren't asked to touch. Could be a prompt-scoping issue (the coordinator's instructions not narrowly enough scoped to `services/<request-id>/`), a subagent overreach, or something in how the sandbox filesystem is shared across the three subagents. Needs diagnosis before it needs a fix.

### Item #20 — REQ-2026-01's `lib/app-insights.ts:70` Application Insights type conflict
Now correctly caught and blocked by QA (Fix 3) rather than silently passing — but the underlying bug is unfixed and REQ-2026-01 stays live, so this needs real resolution. Two candidate fix directions, need investigation before picking one:
- **Dedupe the dependency tree** — confirm whether `npm dedupe`, an explicit `overrides` entry in `package.json` forcing one consistent `@microsoft/applicationinsights-core-js` version across both the top-level and the nested nested-under-`applicationinsights-analytics-js` copy, resolves the type conflict cleanly.
- **Type-cast workaround** — if the duplicate-resolution approach doesn't fully resolve (e.g. if the two AI SDK sub-packages genuinely require incompatible core versions), a scoped type assertion at the `extensions: [_reactPlugin]` call site may be the pragmatic fallback. Less clean, but real dependency conflicts between different versions of the same vendor's own sub-packages sometimes don't have a clean dedupe resolution.

**Recommended starting point for a spec:** try the dedupe/overrides approach first (cleaner, addresses root cause), fall back to a scoped type-cast only if that doesn't work — worth writing the spec to say exactly that rather than picking one blind.

### Item #7 — Archive-prefix mismatch (REQ-2026-02, once)
Deliberately left alone per its own note — root cause unconfirmed, only happened once, and REQ-2026-02's infra is decommissioned anyway so this specific instance can't recur on that app. **Recommend leaving this exactly as-is** unless it happens again on a still-live app — not worth investigating a one-off with no reproduction path.

---

## Bookkeeping — no spec needed, just do directly

### Item #12 — Cost log needs REQ-2026-03 figures backfilled
`docs/FORGE-pipeline-cost-log.md` is missing REQ-2026-03's actual Stage 1/3/4/5/6 cost figures (pulled from the Managed Agents session cost endpoint the same way REQ-2026-02's figures were captured, per the existing pattern). Low effort, no design decision needed — just needs someone to actually pull the numbers and fill in the table. Good candidate to fold into whatever session picks up Item #6 or #8, rather than its own dedicated session.

### Item #15 — Ad hoc PRs need the tracking-issue body line added manually if not opened by a stage agent
Known gap, manual workaround already exists and works (edit the PR body to add the `Related FORGE tracking issue: owner/repo#N` line). Not worth a code fix unless this starts happening often enough to be annoying — currently just something to remember when a human opens an ad hoc PR directly rather than through a stage agent.

---

## Suggested sequencing

1. **Item #20** first — REQ-2026-01 genuinely can't build right now, and it's the most concrete, best-understood item on this list (unlike #6/#8, which need diagnosis before a fix can even be scoped).
2. **Items #1, #9, #10** — send back to Mike as a batch of decisions before any of them gets a spec. #9 and #10 are coupled and should be decided together.
3. **Items #6, #8** — need their own diagnosis-first sessions (not blind fix specs) whenever there's time to invest in them; either order is fine, neither blocks the other.
4. **Item #12** — fold into whichever of #6/#8 gets picked up next, no separate session needed.
5. **Items #7, #15** — leave as-is; revisit only if either recurs or becomes actively annoying.
