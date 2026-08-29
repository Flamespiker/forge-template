# FORGE — Extend Deploy (Stage 6) for Enhancement Targets, and Resolve Unit-Naming/Resource-Identity (Item #28): Spec for Claude Code

**Prepared:** 2026-08-29 (Claude.ai)
**For:** Claude Code CLI session against `forge-template` (`deploy_agent.py`,
`06-deploy.yml`, `core/agents/utils/enhancement_target.py`), with live verification
against `forge-demo-apps` and tracking issue `forge-template#10` /
`forge-demo-apps#32`.
**Context:** Item #28 in CLAUDE.md's Open Items list — confirmed live 2026-08-28
during Item #25's verification pass. A real dispatch against `forge-template#10`/
`forge-demo-apps#32` (REQ-2026-04, an Enhancement request whose existing service is
REQ-2026-03) raised `ValueError: No deployable units detected`. A diagnosis pass (this
session, prior to this spec) established the root cause: `deploy_agent.py`'s
`_detect_units()` builds `services/<request_id>/` unconditionally, with no
`existing_service` concept at all — a third independent copy of the exact bug Items
#24 (Stage 3) and #25 (QA/Security) already fixed, this time in the one stage that
also owns a live, named Azure resource. That last part is what makes this spec more
than a mechanical port: fixing directory resolution alone, the same way #24/#25 were
fixed, would leave Deploy's **unit naming** still keyed on the new `request_id` —
building a container from REQ-2026-03's real code and deploying it under brand-new
`req-2026-04-*` Container Apps, never touching REQ-2026-03's actual live resources.
§3.2 below is the fork this surfaces that #24/#25 never had to resolve.

**Standing conventions to follow (per CLAUDE.md / context doc):**
- Verify against the live file, not this spec — `grep`/`view` the real current
  `deploy_agent.py`, `06-deploy.yml`, and `core/agents/utils/enhancement_target.py`
  before writing anything. This spec's understanding of line numbers and exact
  function shapes comes from the diagnosis pass and CLAUDE.md's notes, both of which
  may have drifted.
- Reuse over reinvention: `core/agents/utils/enhancement_target.py`'s
  `resolve_service_root(request_id, existing_service)` already exists (built for Item
  #25) — this is now the third caller, not a new copy. Do not write a fourth
  independent version of this logic.
- Windows environment: `shutil.which()` for subprocess calls, `encoding="utf-8"` on
  subprocess readers, no bash heredocs.
- Any new failure path follows the ADR-0011 comment-then-reraise contract.
- Report every design fork back to Mike rather than resolving silently — see §3,
  especially §3.2, which is a real architecture decision, not an implementation
  detail.
- Commit each piece in §2 **separately**, verified against real `git diff HEAD`.
- Confirm via GitHub API (not local git, not verbal confirmation) that any commit is
  actually on `origin/main` before dispatching anything label-driven — standing
  pre-dispatch checklist item.
- Do not touch Items #1, #7, #9, #10, #11, #26 — out of scope here (see §4).
- Do **not** touch `implementation_coordinator.py`, `qa_agent.py`, or
  `security_agent.py`'s already-working, already-live-verified resolution logic —
  Items #24/#25 are closed.

---

## 1. Investigate first (do this before designing anything)

1. **Current `deploy_agent.py`** — read in full. Confirm the diagnosis pass's read of
   `_detect_units()` (service_root built from `request_id` alone),
   `_detect_backend_units()`/`_detect_frontend_unit()` (each building `name` as
   `f"{request_id.lower()}-{slug}"`), and `_finalize_unit_name()` (called again in the
   main loop, overwriting `name` — confirm this is the *same* `request_id`, not
   something already resolved differently by the time naming happens). Confirm exactly
   where cross-service FQDN prediction (`_get_env_default_domain`,
   `backend_fqdn`/`frontend_fqdn`) reads `unit.name`, since §2.3 depends on this being
   the only place naming feeds into wiring.
2. **Current `06-deploy.yml`** — read in full. Confirm it currently passes only
   `--request-id` (via `workflow_glue.py resolve-request-id`), confirm whether
   `--issue-number` is already available to this workflow (needed for the spreadsheet
   re-download path in §2.1 to work without new wiring), and confirm the exact shape
   of `resolve_feature_pr()`'s existing call (already used for `head_sha`/`pr_number`)
   to evaluate whether the PR object it returns is cheap to also parse for the
   "Related service" line (§3.1's alternative).
3. **`core/agents/utils/enhancement_target.py`** — read in full. Confirm
   `resolve_service_root()`'s exact signature and return shape (matches the diagnosis
   pass's understanding: `services/<existing_service>/` if set, else
   `services/<request_id>/`) and confirm it has no request-type-specific assumptions
   that would break when called from Deploy's different trigger context (`issues:
   labeled` on the tracking issue, not a PR-linked `repository_dispatch`).
4. **`03-implementation.yml`'s "Determine Enhancement status" step** — read its exact
   shape again (same step §2.1 of the #25 spec mirrored into QA/Security) so this
   spec's addition to `06-deploy.yml` is a precise third copy of the same step, not a
   near-miss reimplementation.
5. **Live Azure state for REQ-2026-03's existing Container Apps** — `az containerapp
   list` (or equivalent) against the real staging environment. Confirm the exact
   current live names (expected: `req-2026-03-on-call-rost-5bb949` and
   `req-2026-03-frontend`, per CLAUDE.md's Item #2/naming-fix history) and confirm
   whether re-running `_finalize_unit_name()` with `existing_service="REQ-2026-03"`
   substituted for `request_id` in the naming formula would reproduce those exact
   names byte-for-byte, or would produce a *different* name (e.g. because the
   sha256-hash suffix is computed over the untruncated full name, which changes if the
   id used to build it changes) — this determines whether §3.2's "update in place"
   option is actually achievable without a one-time manual rename/migration, or
   whether it would itself create a second set of resources on first run. **This is
   the single most important thing to confirm before §2.2 is designed** — if the hash
   doesn't reproduce the live name, "update in place" needs a documented one-time
   reconciliation step, not just a code change.
6. **Tracking issue `forge-template#10` / `forge-demo-apps#32`'s live state** —
   confirm current label state (`qa-approved` + `security-approved`, per Item #25's
   closeout) and confirm the original failed Deploy run's exact logged error and
   timestamp, to use as the reproduction baseline in §5.
7. **A current live Greenfield Container App deploy** (e.g. REQ-2026-03's own original
   Greenfield run, or REQ-2026-01) — confirm today's Deploy behavior for a Greenfield
   request is genuinely unaffected by anything in this spec, as a baseline to diff
   against after the fix.

Report findings from this section back before proceeding — in particular §1.5's
result directly determines whether §3.2 can default to "update in place" as written,
or whether Mike needs to pick a different option because the naming scheme can't
reproduce the live names deterministically.

---

## 2. Scope

### 2.1 Enhancement-target resolution for Deploy

**Goal:** Deploy knows, before calling `_detect_units()`, whether this is an
Enhancement request and — if so — which existing `services/<n>/` folder is the real
target, reusing the exact mechanism already built and live-verified for Items #24/#25.

**Proposed approach (third call site of the existing helper, not a new pattern):**
- Add a "Determine Enhancement status" step to `06-deploy.yml`, structurally identical
  to the one already in `03-implementation.yml`/`04-qa.yml`/`05-security.yml`:
  re-download the intake spreadsheet via `workflow_glue.py download-issue-attachment`
  (Deploy already has `ISSUE_NUMBER` directly from `github.event.issue.number` — no
  extra resolution hop needed, unlike QA/Security), parse `request_type` and the
  existing-service field via `file_io.py`.
- Pass the resolved value to `deploy_agent.py` as a new `--existing-service` flag,
  matching the CLI shape already established on `implementation_coordinator.py`,
  `qa_agent.py`, and `security_agent.py`.
- Inside `deploy_agent.py`: call the existing `resolve_service_root(request_id,
  existing_service)` helper from `core/agents/utils/enhancement_target.py` — do not
  reimplement the path-construction logic a fourth time.

**Considered and not chosen as the default (flag to Mike per §3.1):** parsing the
already-posted "Related service: services/<existing_service>/" line from the PR body
that `resolve_feature_pr()` already fetches, instead of re-downloading the
spreadsheet. Mike already picked spreadsheet re-download as the default for Item #25
on the same reasoning (authoritative lookup over weak-signal text parsing) — §3.1
below carries that same recommendation forward for consistency, not because Deploy's
situation is different.

### 2.2 Unit naming and resource identity for an Enhancement deploy

**Goal:** an Enhancement deploy targets the *same* live Container Apps the existing
service already runs under — not a new, parallel set of resources under the new
request's id.

This is the part with no precedent in #24/#25 (see §3.2 for the full design
discussion; this subsection describes the mechanical shape once Mike's call is made).

- `_detect_backend_units()` / `_detect_frontend_unit()`'s `name=` construction and the
  main loop's `_finalize_unit_name()` call currently both use `request_id` as the
  naming key. Introduce a separate `naming_id` value — `existing_service` if set, else
  `request_id` — and use `naming_id` everywhere naming currently uses `request_id`,
  while `resolve_service_root()`'s resolved directory (§2.1) continues to govern where
  code is read from. These are two uses of "an id" that happen to be the same value
  today (Greenfield) and must diverge correctly for an Enhancement.
- Confirm (per §1.5) that recomputing `_finalize_unit_name(naming_id="REQ-2026-03",
  slug)` reproduces the live `req-2026-03-on-call-rost-5bb949` /
  `req-2026-03-frontend` names exactly. If it does not, this subsection needs a
  documented one-time step (not silent code) to reconcile — see §3.2's fallback.

### 2.3 Cross-service FQDN prediction follows the same naming key

**Goal:** the frontend's build-time `NEXT_PUBLIC_API_BASE_URL`/`FRONTEND_ORIGIN`/
`NEXTAUTH_URL` point at the real, already-live backend — not a newly-predicted URL
under the wrong id.

- `_get_env_default_domain()` / `backend_fqdn`/`frontend_fqdn` derivation currently
  reads `unit.name`. Once §2.2 lands, `unit.name` is already correct (built from
  `naming_id`), so this should require no separate code change — confirm this by
  reading the actual call site (§1.1), not by assuming it's automatically fixed.

### 2.4 Ad hoc fix PR gap — flag only, no fix in this spec

The diagnosis pass noted that if §3.1 ever moves to the PR-body-parsing resolution
path, an ad hoc fix PR (not opened by `implementation_coordinator.py`) would silently
degrade to Greenfield behavior — the same class of gap Item #15/#17 already solved
once for the tracking-issue-line convention. Since §3.1 recommends staying on
spreadsheet re-download (which has no such gap — it reads the original intake data,
not anything PR-shaped), this is not live risk under the recommended default. Flagging
it here only so it's not silently forgotten if §3.1's fork is ever revisited.

### 2.5 Greenfield behavior unaffected

**Goal:** confirm, don't assume, that both fixes are a no-op for every existing
Greenfield deploy.

- When `--existing-service` is absent: `resolve_service_root()` returns
  `services/<request_id>/` exactly as today, `naming_id` falls back to `request_id`
  exactly as today, and `_finalize_unit_name()` produces byte-identical names to
  today's for every currently-live app (REQ-2026-01's two units, REQ-2026-03's two
  units) — confirm this explicitly rather than inferring it from the code reading
  correctly.

---

## 3. Design forks explicitly surfaced (Mike's call, not Claude Code's)

### 3.1 Resolution mechanism: re-download spreadsheet vs. parse the posted "Related service" line

**Recommended default: re-download the intake spreadsheet**, consistent with Mike's
already-confirmed default for the identical fork in Item #25. Deploy's situation
doesn't change the tradeoff Mike already weighed then: the PR-body line is real,
currently-available data and marginally cheaper (Deploy already fetches the PR object
via `resolve_feature_pr()`), but it inherits the same fragility class the project
already moved away from once (comment-text-format dependency, silent no-value for ad
hoc PRs per §2.4). Re-raising only if Mike wants to reconsider the Item #25 precedent
specifically for Deploy, or if §1.2's investigation surfaces something about Deploy's
trigger timing that makes the spreadsheet re-download meaningfully less reliable here
than it is for QA/Security.

### 3.2 Unit naming / resource identity: update the existing live Container Apps in place, or create new ones under the new request's id?

**This is the real fork this spec introduces — genuinely new territory, not a port of
#24/#25's pattern, because Deploy is the only stage of the four that owns a
persistent, named external resource.**

**Recommended default: update the existing `req-<existing_service>-*` Container Apps
in place** (the naming-key change described in §2.2), reasoning: an Enhancement
request is, by FORGE's own definition, a change to an *existing* live service, not a
new one. A user hitting REQ-2026-03's live URL expects to see REQ-2026-04's changes
there — not to discover a second, parallel `req-2026-04-*` app that nothing points to
and REQ-2026-03's real app never updated. The current (broken) behavior does the
latter silently the moment the directory-resolution bug alone gets fixed without also
fixing naming, which is exactly the trap flagged in the diagnosis pass.

**Real tradeoff to weigh, not just implementation risk:** "update in place" means a
failed or partially-failed Enhancement deploy touches the same live Container App a
real, current REQ-2026-03 user is depending on — there's no separate
never-deployed-before resource insulating the blast radius the way a brand-new app
would. FORGE's staging environment has historically absorbed this kind of risk for
Greenfield deploys already (a failed unit doesn't leave old traffic broken, because
Container Apps' revision model keeps the last-healthy revision serving until a new one
is confirmed) — confirm in §1 whether that same revision-safety property holds
identically for an Enhancement's update-in-place deploy, or whether anything about
this fix changes that guarantee.

**Alternative not recommended, flagged for completeness:** deploy under
`req-<request_id>-*` (today's actual behavior, if only the directory bug were fixed)
and treat it as a separate, parallel staging slot, requiring a manual promotion/cutover
step to actually update the real live app. This avoids touching a live resource
automatically, but means Deploy's success no longer means "the Enhancement is live" —
it would mean "a parallel copy exists, someone still needs to cut over," which is a
meaningfully different (and currently undocumented) operational model. Not proposed as
the default because nothing in FORGE today implements or expects a cutover step, but
worth naming explicitly since it's the direct alternative to the recommendation above.

**Depends on §1.5:** if the naming scheme can't deterministically reproduce
REQ-2026-03's live app names from `existing_service` alone (hash-suffix mismatch),
"update in place" needs an explicit one-time reconciliation (a documented manual
rename, or a small one-off migration script) before this fix can work as designed —
Mike should decide whether that reconciliation is acceptable to do once now, given
only two live apps exist today (REQ-2026-01, REQ-2026-03).

### 3.3 Does this fix apply to staging only, or production too?

Not addressed by this spec's scope — FORGE has never deployed anything to production
yet (per CLAUDE.md, Phase 5's app never went past staging). Flagging only so the fix
isn't accidentally written with a staging-only assumption baked in if a production
path is added later; §2's proposed changes are environment-agnostic as written (they
don't branch on staging vs. production anywhere), so this should be a non-issue, but
worth Mike's explicit sign-off given how central "which live resource gets touched" is
to §3.2.

---

## 4. Out of scope

- **Item #26 (no human gate before Deploy)** — separate architectural question. This
  spec does not touch `06-deploy.yml`'s trigger condition (`labeled` on both
  `qa-approved`/`security-approved`) at all — only what happens *inside* the Deploy
  Agent once triggered. Note for §5: because #26 is still unresolved, re-verifying
  this fix against issue #10/PR #32 means a real Deploy will fire the moment conditions
  are met — same live-consequence category as Item #25's own verification.
- **Item #1** (Deploy Agent secret-declaration convention) — untouched, unrelated.
- **Item #7** (REQ-2026-02 archive-prefix mismatch) — untouched, deliberate leave-as-is.
- `implementation_coordinator.py`, `qa_agent.py`, `security_agent.py` — untouched;
  Items #24/#25 are closed and this spec only adds a third/fourth caller to their
  shared helper, never modifies their own resolution logic.
- Re-litigating Items #24/#25 themselves.

---

## 5. Live verification

**Use tracking issue `forge-template#10` / `forge-demo-apps#32` as the verification
vehicle** — it's the exact real request that surfaced this bug, already
`qa-approved` + `security-approved` per Item #25's closeout, sitting one Deploy
attempt away from either succeeding for real or failing the same way again.

1. Confirm issue #10 / PR #32's live label state and the exact original Deploy failure
   (§1.6) before touching anything.
2. **Before re-dispatching Deploy for real: explicitly confirm with Mike that
   triggering a real Deploy against PR #32 is acceptable**, given §3.2's chosen
   option means this run will either update REQ-2026-03's actual live Container Apps
   in place (if "update in place" is confirmed) or create new `req-2026-04-*`
   resources (if the alternative is chosen) — a live, billable Azure change either
   way. Do not proceed past this point without that explicit confirmation.
3. Once confirmed: manually replay whatever mechanism currently re-triggers Deploy
   (re-applying the labels, or an equivalent manual redispatch already used elsewhere
   in this pipeline) against issue #10.
4. Confirm Deploy now resolves `services/REQ-2026-03/` as the real target (not
   `services/REQ-2026-04/`), successfully detects both units, and builds/pushes real
   images from REQ-2026-03's actual current code (including REQ-2026-04's
   enhancement).
5. Confirm the resulting Container App name(s) match §3.2's chosen outcome exactly —
   either the pre-existing `req-2026-03-*` names (update-in-place) or new
   `req-2026-04-*` names (alternative) — verified via `az containerapp show`, not
   assumed from the job log.
6. If update-in-place: confirm via `az containerapp show
   --query properties.template.containers[0].image` that the live image's source
   commit is genuinely the new one (same "verbally confirmed deployed ≠ actually
   deployed" discipline CLAUDE.md already flags for prior deploys), and confirm the
   app is reachable in a real browser showing the Enhancement's actual change — not
   just a green pipeline run.
7. Confirm cross-service wiring (FQDN) still resolves the frontend to the correct real
   backend, not a stale or wrong URL.
8. Confirm a genuinely Greenfield deploy (any recent or new one) is completely
   unaffected — no `--existing-service` flag sent, identical unit names, no behavior
   change from before this fix, using §1.7's baseline for comparison.
9. Report all live evidence (job log excerpts, `az containerapp show` output, browser
   confirmation, image SHA comparison) back explicitly — same "real executed evidence
   before closing" bar as every other item.

Do **not** treat a passing `--dry-run` as sufficient for §2.2/§2.3 — like Items
#24/#25, there's no substitute for a real, non-dry-run Deploy against the actual
REQ-2026-04 PR #32 state, especially given §3.2's live-resource stakes.

---

## 6. Sequencing

1. §1 investigation — all seven points, reported back before any code is written.
   §1.5 in particular gates §3.2's feasibility as written.
2. §3.1's fork resolved by Mike (or defaulted per the recommendation) before §2.1 is
   written.
3. §3.2's fork resolved by Mike — this is the one that cannot be defaulted silently
   even though a recommendation is given, since it's a real architecture decision with
   live-resource consequences, not an implementation detail like §3.1.
4. §2.1 (Enhancement-target resolution via the existing shared helper) — foundational.
5. §2.2 (unit naming / resource identity) — depends on §3.2's decision and §1.5's
   confirmation; if §1.5 finds a hash-reproduction mismatch, resolve the one-time
   reconciliation (per §3.2's fallback note) before or alongside this step.
6. §2.3 — confirm as a check, likely no code change needed.
7. §2.5 — confirm as a check, not a separate code change.
8. §5 live verification via tracking issue #10 / PR #32 — **gated on Mike's explicit
   go-ahead per §5 step 2**, given the real-resource consequence.
9. `CLAUDE.md` close-out: mark Item #28 resolved with the real fix narrative and live
   evidence, same format as Items #24/#25's entries.

---

## Next chat after this one (Claude.ai)

Once Claude Code reports back with live-verification evidence, fold the outcome into a
fresh context doc, close Item #28 in CLAUDE.md, and update `FORGE-Open-Items-
Backlog-v1.md` to add #28 (still outstanding per v73's "newly added as open" note).
Item #26 (human gate before Deploy) remains open as its own dedicated fresh-chat
architecture decision, unrelated to this spec beyond the shared observation that its
absence continues to mean every successful QA+Security pass auto-triggers a real
Deploy.
