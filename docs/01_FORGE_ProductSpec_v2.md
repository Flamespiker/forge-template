# FORGE Product Specification

**Document 1 of 9 — Feature Set, Personas, Non-Functional Requirements, Success Criteria**

---

## 1. Purpose of This Document

This specification defines *what* FORGE does, for *whom*, and *how success is measured*. It assumes the reader has read the **FORGE Introduction** (Document 0) and understands the core pattern: deterministic orchestration paired with bounded agent execution, with a human gate before every consequential step.

Where the Introduction explains why FORGE exists, this document enumerates the features, users, and quality bars an implementation must meet. The **Architecture Document** (Document 2) will define how each feature is technically realized.

---

## 2. User Personas

FORGE has six personas. Some map to a single person on a small team; on larger teams, multiple people may share a persona.

### 2.1 Business Analyst (BA)
Owns the intake spreadsheet. Describes the business need — audience, purpose, problem being solved — without needing to know FORGE's internals. Answers the Intake Agent's clarifying questions and reviews the resulting requirements draft before anything becomes an ADO work item.

**Needs from FORGE:** a spreadsheet template that's easy to fill out without training; clarifying questions that are focused (5–7, one follow-up round max) rather than exhausting; a requirements draft written in language they can actually evaluate, not engineering jargon.

### 2.2 Orchestration Manager
The developer or tech lead who owns a team's FORGE instance (see Document 0). Configures the team layer, manages agent personas and skills, and is the point of contact when the pipeline stalls or misbehaves.

**Needs from FORGE:** clear visibility into pipeline state at every stage; a documented boundary between what they can customize and what's locked in the core layer; the ability to pull core updates from the template repo without breaking their customizations.

### 2.3 Technical Approver (Design & Code)
Typically a senior developer or tech lead. Reviews the technical design and API contracts before implementation starts, and reviews the implementation diff before it merges.

**Needs from FORGE:** a design document and API contract that are complete enough to approve or reject with confidence; a diff view with agent-flagged issues already surfaced, not buried.

### 2.4 QA Reviewer
Reviews the test report and bug list produced after implementation. Signs off before the pipeline proceeds to security review, or sends work back to implementation via the loop-back path.

**Needs from FORGE:** a test report that clearly separates passed, failed, and skipped; enough context on each failure to triage without re-running everything manually.

### 2.5 Security Reviewer
Reviews severity-tagged findings from SAST, secrets detection, and OWASP checks. The pipeline blocks automatically on any Critical finding; the reviewer's sign-off is required regardless of severity mix.

**Needs from FORGE:** findings presented inline on the PR, tagged by severity, with enough detail to distinguish real issues from false positives.

### 2.6 Release Approver
Gives the final one-click sign-off before deployment. May be the same person as the Technical Approver on small teams, or a separate release manager on larger ones.

**Needs from FORGE:** confirmation that every prior gate has actually been passed, not just attempted; a clear rollback path if something goes wrong post-deploy.

---

## 3. Feature Set

Organized by pipeline stage, matching the stage table in the context document.

### 3.0a — Codebase Ingestion *(enhancement workflow only)*
- Reads an existing repository's structure, architecture, and conventions before any requirements work begins.
- Produces an existing-architecture summary used to ground the Requirements and Design agents in what's actually there, rather than proposing a design as if starting from scratch.
- Not a human-gated stage — its output feeds the Requirements stage, which is gated.

### 3.0b — Intake & Clarification
- BA completes the standard Excel intake spreadsheet, including the overview/context tab (audience, purpose, problem being solved).
- Intake Agent reads the completed spreadsheet and asks a focused round of clarifying questions (5–7 max, one follow-up round if genuinely needed).
- Produces a record of answered context questions that becomes the input to Requirements.

### 3.1 — Requirements
- Requirements Agent produces `requirements.md` and a draft set of ADO work items (Epics → Features → User Stories).
- **Human gate:** a person reviews and approves the draft before anything is actually created in ADO. Nothing is created speculatively.
- Establishes the first link in the traceability chain: spreadsheet row → ADO User Story.

### 3.2 — Spec & Design
- Design Agent produces `design.md`, `openapi.yaml`, and `tasks.md` from the approved requirements.
- **Human gate:** a person reviews the architecture and API contracts and approves the design PR before implementation starts.

### 3.3 — Implementation
- The Implementation Coordinator orchestrates Backend Agent (.NET), Frontend Agent (React/Next.js), and Test Writer Agent in parallel on a shared sandbox filesystem, from the approved design and task breakdown.
- The Coordinator synthesizes the subagents' output, commits the complete implementation to a feature branch, and opens a draft PR.
- **Human gate:** a person reviews the implementation diff; agents pre-flag known issues rather than leaving reviewers to find everything cold.

### 3.4 — QA
- QA Agent runs the test suite against the implementation, producing a test report and filing bug tickets for failures.
- Supports a loop-back path to Implementation when failures require code changes, without restarting the whole pipeline.
- **Human gate:** QA sign-off required before proceeding to (or clearing, if run in parallel with) Security.

### 3.5 — Security
- Security Agent runs SAST, secrets detection, and OWASP checks, typically in parallel with QA.
- Findings are posted as severity-tagged inline PR comments. Any Critical finding blocks the pipeline automatically.
- **Human gate:** security sign-off required regardless of finding severity.

### 3.6 — Deploy
- Deploy Agent containerizes the application and pushes it through staging to production on Azure Container Apps.
- **Human gate:** one-click GitHub Environment approval — the only irreversible action in the pipeline, and the only stage where no further review happens afterward.

### 3.7 — Cross-Cutting Features (apply across all stages)
- **Full traceability:** every artifact is linked back through spreadsheet row → ADO User Story → GitHub branch → PR → deployment, so any deployed change can be traced to the original business request.
- **State tracking:** deterministic orchestration keeps a record of what stage a request is in and what gate it's waiting on, independent of any single agent run.
- **Template repo distribution:** teams clone FORGE as a GitHub template, and can pull core-layer updates over time without losing team-layer customizations.
- **Two-layer configuration:** a clear, documented split between what's locked (core) and what's adaptable (team) — detailed fully in the Customization Reference (Document 7).

---

## 4. Non-Functional Requirements

### 4.1 Traceability & Auditability
Every artifact produced at every stage must be attributable to the requirement that triggered it, and every gate approval must be recorded with who approved it and when. This is what makes the "trail that shows why decisions were made" (Document 0) real rather than aspirational.

### 4.2 Human Control
No agent may advance the pipeline past a defined gate on its own judgment. This is a hard requirement, not a tunable setting — it is core-layer, not team-layer.

### 4.3 Security Posture
Security gates (SAST, secrets detection, OWASP checks) are embedded in the workflow and block automatically on Critical findings. Per the context doc, the posture is **practical, not built for a heavy regulatory environment** — appropriate to where Legal Aid Alberta operates today, not a compliance framework for a more heavily regulated context. Client data sensitivity is called out explicitly in the AI Foundations Guide (Document 5) rather than enforced through additional technical controls in v1.

### 4.4 Consistency Across Teams
Because the core layer is locked and shared, any two teams' FORGE instances must produce comparable artifacts (same work item structure, same naming conventions, same branching strategy, same intake format), even though their tech stack specifics and agent personas may differ.

### 4.5 Maintainability
Teams must be able to pull core-layer updates from the template repository without losing team-layer customizations. This depends on the two-layer separation being enforced structurally, not just by convention.

### 4.6 Reliability of Orchestration
The deterministic parts of the pipeline (branch creation, PR management, state transitions) must behave identically every run. Variability belongs entirely inside bounded agent execution, never in the orchestration layer around it.

### 4.7 Usability for Non-Engineers
The BA-facing surface (the intake spreadsheet and the clarifying-question round) must require no FORGE-specific training. This is the one part of the pipeline used by someone outside engineering, and it should read that way.

---

## 5. Success Criteria

Per the context doc's scope and demo plan, success is measured across three proof points:

1. **App 1 (greenfield):** A small new application moves through the entire pipeline — intake through deployment — with every human gate functioning as designed, and a complete, unbroken traceability chain from the original spreadsheet row to the deployed application.
2. **App 2 (greenfield):** A second, independent application proves the pipeline is repeatable, not a one-off that only worked because of hands-on tuning during App 1.
3. **Enhancement (App 1 or App 2):** A targeted enhancement proves the Stage 0 codebase ingestion workflow — the agent correctly reads and respects existing architecture and conventions rather than proposing a design as if starting fresh.

Additional success indicators:

- No agent advances the pipeline past a human gate without explicit approval, across all three proof points.
- A second team could, in principle, clone the template repository and stand up their own instance using only the documented core/team boundary — without needing to ask the Orchestration Manager of the original team how it actually works.
- Core-layer updates can be pulled into an already-customized team instance without manual reconciliation of the locked pieces (security gates, work item structure, naming conventions, branching strategy, deployment standards, intake format).

---

## 6. Out of Scope (v1)

To keep this specification honest about its limits:

- FORGE does not perform requirements gathering itself — it structures and accelerates what happens after a BA has gathered them (Document 0).
- FORGE is not designed as a compliance framework for a heavily regulated environment; its security approach is scoped to LAA's current context.
- Multi-team shared skills libraries, exact ADO field mapping, and RFC process mechanics are open questions carried from the context log and are addressed in later documents (Governance Model, Customization Reference), not here.

---

## 7. Where This Fits

This document defines *what* and *for whom*. The next document — the **Architecture Document** — defines *how*: agent topology, pipeline stage mechanics, ADO integration detail, GitHub structure, and the container strategy that makes the two-layer model real.
