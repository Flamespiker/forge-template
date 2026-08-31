# FORGE — Secrets-Declaration Flag (Item #1, Option 1): Spec for Claude Code

**Prepared:** 2026-08-31 (Claude.ai)
**For:** Claude Code CLI session against `forge-template` (changes to
`design_agent.py` and `implementation_coordinator.py`), plus doc backfill
against `forge-demo-apps`' `docs/<request-id>/design.md` for the three
already-live services.
**Context:** Item #1 in CLAUDE.md — the reactive half (Option 3, post-deploy
crash-loop flag) is built and live-verified (2026-08-31). This spec closes
the other half: a lightweight, flag-only, never-blocking check that a
service's required secrets are at least *declared* before implementation
ships, so the next `req-2026-01-email-worker`-shaped gap surfaces before
merge instead of after a live crash loop. **Mike chose the lightweight,
`_detect_design_gaps()`-style direction over both a fully machine-enforced
declaration schema and accepting the gap as permanently manual.**

**Investigation already done (Claude Code CLI, 2026-08-31, read-only —
do not re-investigate, build on it):**

- **Real variable names, confirmed per-service:** REQ-2026-01 EmailWorker
  (`ServiceBus:ConnectionString`, `ConnectionStrings:CaseViewDatabase`,
  `SendGrid:ApiKey`) and its sibling DocumentApi (shares
  `ServiceBus:ConnectionString`, plus `ConnectionStrings:DocumentDatabase`,
  `BlobStorage:ConnectionString`) both use .NET's `Configuration[...] ??
  throw` idiom with `:`→`__` section-to-env-var mangling. REQ-2026-02 D365
  (`D365_TENANT_ID`, `D365_CLIENT_ID`, `D365_CLIENT_SECRET`,
  `D365_ENVIRONMENT_URL`) uses flat, already-env-var-shaped keys. REQ-2026-03
  Azure AD (`AZURE_AD_CLIENT_ID`, `AZURE_AD_CLIENT_SECRET`,
  `AZURE_AD_TENANT_ID`) uses `process.env.X!`.
- **Structural blind spot, confirmed via `git grep`:** REQ-2026-03's
  `NEXTAUTH_SECRET`/`NEXTAUTH_URL` never appear in application source at
  all — they're consumed internally by the `next-auth` npm package. No
  static analysis of generated code can discover this class of secret; it
  can only come from a declaration. This is why Mike's "declaration-only"
  choice (§1 below) is the right fit, not a compromise — a cross-check
  against code would still miss this exact case, the one that actually
  caused a real production gap.
- **`design.md` is not a reliable source today:** REQ-2026-01 documents zero
  of its secrets. REQ-2026-02 names 1 of 4 (`D365_CLIENT_SECRET`, in prose,
  inside a risk/assumption list). REQ-2026-03 names the library but neither
  variable. No existing structured section exists anywhere to detect against
  — this spec creates one, it doesn't discover a hidden one.
- **Placeholder conventions vary per service** (`REPLACE_WITH_*` vs.
  `your-*-here` vs. `__AZURE_TENANT_ID__`-style wrapping vs. a real-looking
  local-dev default vs. an empty string) — confirms a code-side placeholder
  scan would need per-service tuning and still isn't the mechanism this spec
  uses, included here only so a future reader doesn't re-propose it as a
  quick win.
- **Stage timing, confirmed:** Stage 3 (`implementation_coordinator.py`)
  already holds `design_md` (fetched at line 637) and `files_to_commit`
  (the extracted `implementation.tar.gz`, path→content) simultaneously in
  memory, before `commit_files()` runs — the earliest point in the pipeline
  both artifacts coexist, and before any PR, QA, Security, or Deploy work
  happens. Stage 6's `_detect_design_gaps()` (existing precedent) runs at
  line 1067, *after* that unit's own build/push/deploy already executed —
  structurally the latest possible point, not the earliest.

---

## 1. Design forks — resolved this session (Mike's calls, reasoning below)

### 1.1 Detection signal

**Decision: declaration-only.** Flag if `design.md`'s "Required Secrets"
section is missing entirely — do **not** cross-check declared secrets
against code-detected patterns.

Reasoning: the NEXTAUTH finding proves a code-side cross-check has a
structural blind spot for framework-consumed secrets, and the three
divergent placeholder conventions mean even a best-effort code scan needs
per-service tuning with no guarantee of catching the next new case either.
A declaration-only check is honest about what it can promise: "did the
author write this section down," not "is this section accurate or
complete." That's a real, useful check on its own — the goal per Item #1's
own framing is closing "silent forever," not building a secrets-accuracy
verifier.

### 1.2 Where the check runs

**Decision: Stage 3 (`implementation_coordinator.py`), a new function
alongside the coordinator's existing logic — not Stage 6.**

Reasoning: Stage 3 is the earliest point both `design_md` and the final
generated code exist together, and flags before merge rather than after a
live deploy. Stage 6's `_detect_design_gaps()` is the named precedent for
*shape* (deterministic, flag-only, never-blocking dict/string scan) but not
for *location* — reusing its shape at an earlier stage is more useful than
reusing its exact file.

### 1.3 Who authors the declaration

**Decision: `design_agent.py` generates the "Required Secrets" section
automatically at Stage 2, every time — even when empty.**

Reasoning: making the section's *presence* unconditional (always written,
with an explicit "None identified" when the design agent finds nothing) is
what makes Stage 3's declaration-only check meaningful. If the section were
optional, "missing" would be ambiguous between "author forgot" and "author
decided there's nothing to declare" — an unconditional write removes that
ambiguity, and mirrors how a *human* author would be expected to explicitly
say "none" rather than leave a gap.

---

## 2. Scope

### 2.1 `design_agent.py` — Stage 2, new "Required Secrets" section

- Extend the design-generation prompt to require a `## Required Secrets`
  section in every `design.md` it produces, structured as a table: secret
  name (the actual env var or config key the app will read), purpose, and
  source (e.g., "Key Vault", "external service credential", "framework-
  internal — consumed by `<library>`, not referenced in app code").
- Instruct the agent to actively reason about this, not just describe
  what's already planned: known auth libraries (NextAuth, MSAL-style
  patterns), external service integrations named elsewhere in the design
  (Service Bus, SendGrid, D365-style APIs, Blob Storage), and database
  connection strings.
- If the agent identifies nothing, the section must still be written, with
  literal text `None identified` — never omitted.
- Applies to both Greenfield and Enhancement design generation paths.

### 2.2 `implementation_coordinator.py` — Stage 3, new flag check

- New function, e.g. `_detect_missing_secrets_declaration()`, called
  alongside the existing coordinator logic once `design_md` and
  `files_to_commit` are both available.
- Deterministic string check: does `design_md` contain a `## Required
  Secrets` header. If missing entirely, flag (never block/raise).
- **Investigate before implementing:** confirm how Stage 3 currently
  surfaces non-blocking flags (if it already posts a PR comment or
  tracking-issue comment akin to Deploy Agent's `_detect_design_gaps()`
  reporting, reuse that mechanism; if Stage 3 has no existing flag-surfacing
  path today, add the smallest addition that fits its existing PR/issue
  comment pattern — report back what's found before building new
  infrastructure).
- Wording should be explicit that this is a **completeness-of-declaration**
  check, not a secrets-accuracy or code-correctness check, so it isn't
  misread as validating the actual secrets are wired correctly.

### 2.3 Backfill `design.md` for the three known services

Using this session's own investigation findings (exact variable names
already confirmed above — no re-investigation needed), add a "Required
Secrets" section to the real `docs/<request-id>/design.md` for:
- **REQ-2026-01** (EmailWorker + DocumentApi): all 5 variables listed above.
- **REQ-2026-02** (D365): all 4 variables, replacing the single prose
  mention with a proper table entry.
- **REQ-2026-03** (NEXTAUTH + Azure AD): all 5 variables, including the two
  framework-internal NEXTAUTH ones explicitly marked as such.

This is a doc-only change (no live Azure resources touched) and prevents an
immediate, uninteresting flood of "missing declaration" flags against three
services that already work, the first time either gets touched by a future
Enhancement request.

---

## 3. Out of scope

- Cross-checking declared secrets against code-detected patterns (§1.1) —
  explicitly rejected this pass.
- Automated secret value provisioning, rotation, or the wiring itself —
  `_wire_keyvault_secret()` already solves wiring; this spec only adds
  discovery-side awareness.
- Backfilling `design.md` for any service beyond the three named in §2.3.
- Extending this check to QA/Security (Stage 4/5) — Stage 3 is sufficient
  per §1.2's reasoning; revisit only if Stage 3's flag proves to be getting
  missed or ignored in practice.
- Fixing `req-2026-01-email-worker`'s actual crash (still open, unrelated —
  this spec adds earlier detection for the *next* case, it doesn't fix the
  current one).

---

## 4. Live verification

1. Confirm Stage 3's existing flag-surfacing mechanism (or lack thereof)
   before writing `_detect_missing_secrets_declaration()` — report back.
2. Implement §2.1 (`design_agent.py`) and §2.2
   (`implementation_coordinator.py`).
3. Backfill §2.3 against `forge-demo-apps`' three real `design.md` files.
4. Test the Stage 2 change against a real (or dry-run, whichever is
   cheaper/lower-risk) design generation — confirm the section is written,
   including the "None identified" case if a test request has no secrets.
5. Test the Stage 3 check two ways: (a) against one of the freshly-backfilled
   services — confirm no flag; (b) against a `design.md` deliberately
   missing the section (or an older cached version, if available, predating
   this fix) — confirm the flag fires and is non-blocking (implementation
   still proceeds to commit).
6. Confirm via the actual posted comment/flag (not just a clean log) that
   nothing downstream reads or reacts to this flag as a gate.

---

## 5. Sequencing

1. §4.1 investigation, reported back.
2. §2.1/§2.2 implemented as separate commits.
3. §2.3 backfill, separate commit.
4. §4.4–4.6 verification.
5. `CLAUDE.md` Item #1 updated: both Option 3 (already done) and Option 1
   (this spec) reflected — Item #1 can move to fully resolved once both
   halves are live-verified, unless verification surfaces something that
   keeps a piece of it open.

---

## Next chat after this one (Claude.ai)

Once Claude Code CLI reports back on §4.1 and completes verification, fold
the outcome into a fresh context doc and close out Item #1 in both
CLAUDE.md and the Open Items Backlog — first time both halves of this item
will be genuinely closed rather than partially resolved.
