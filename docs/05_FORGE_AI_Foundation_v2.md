# FORGE AI Foundations Guide

**Track 1 Training — All Developers**  
**Version:** 1.1  
**Last Updated:** 2026-07-23

---

## Who This Guide Is For

This guide is for every developer who will work with or inside FORGE — whether you are reviewing agent output at a human gate, configuring a team-layer persona, or troubleshooting a failed pipeline run. You do not need to be an AI specialist. You do need a correct mental model of what AI agents are actually doing so that your review decisions are informed, not reflexive.

This is Track 1. It covers concepts. Track 2 (the Orchestration Manager Guide) covers hands-on setup and operation.

---

## Terminology Note

Two meanings of "session" show up once you start reading about FORGE and about Anthropic's tooling side by side. Keep them separate:

| Term | Meaning |
|------|---------|
| **Chat** or **chat thread** | A conversation with Claude — e.g. the project-writing chats used to produce FORGE's own documents |
| **Agent session** | A running Managed Agents API instance (`/v1/sessions/:id`) — the mechanism Stage 3 uses to run its coordinator and subagents |

This guide, and Document 6 (Orchestration Manager Guide), always say "agent session" when referring to the Managed Agents API concept, and reserve "chat" for ordinary conversational use of Claude.

---

## 1. What Large Language Models Are

A large language model (LLM) is a statistical model trained on enormous amounts of text. During training, it learns patterns — which words, phrases, and ideas tend to follow which others, across an enormous range of contexts. It does not store facts like a database. It learns relationships between concepts and uses those relationships to generate plausible continuations of whatever input it receives.

**Key things to understand:**

**LLMs are non-deterministic.** The same prompt can produce different outputs on different runs. This is by design — some randomness (called "temperature") produces more natural, varied responses. FORGE's deterministic layer (GitHub Actions workflows, state labels, branch naming) exists precisely because the agent layer is not deterministic.

**LLMs hallucinate.** When a model does not "know" something, it does not say "I don't know" — it generates a plausible-sounding answer that may be factually wrong. This is not a bug being fixed; it is a fundamental property of how these models work. It is one of the reasons every FORGE stage has a human review gate.

**LLMs do not have memory between calls.** Each agent invocation starts fresh. FORGE passes context forward as committed files (requirements.md, design.md, tasks.md) rather than relying on any agent to "remember" a prior conversation.

**LLMs reason by predicting, not by calculating.** They are exceptionally good at language tasks — summarizing, drafting, transforming structured content, writing code from a spec. They are unreliable for precise arithmetic, strict rule-following without guidance, and anything requiring guaranteed factual accuracy.

**Useful references:**
- [Intro to Claude](https://docs.anthropic.com/en/docs/intro-to-claude) — Claude's capabilities and design philosophy
- [Anthropic Glossary](https://docs.anthropic.com/en/docs/about-claude/glossary) — Definitions of key terms: tokens, context window, temperature, fine-tuning
- [Models Overview](https://docs.anthropic.com/en/docs/about-claude/models) — Claude model families and capability tiers

---

## 2. How Agents Work

An "agent" is not a different kind of model — it is a pattern for using a model. A single LLM call takes input and returns output. An agent extends that by giving the model tools it can invoke, an environment it can observe, and the ability to decide what to do next based on what it sees.

**The agentic loop:**

1. The model receives a prompt describing its task, the tools available to it, and any context passed in
2. It decides whether to use a tool or produce a final response
3. If it uses a tool (read a file, call an API, run a command), the tool result comes back and the loop continues
4. This repeats until the model produces a final output or a stop condition is reached

**What this means in FORGE:**

Each of FORGE's ten agents is a scoped agentic loop, invoked as a GitHub Actions job. The Requirements Agent reads the BA spreadsheet and produces requirements.md. The Design Agent reads requirements.md and produces design.md. Neither agent is running between invocations — they are stateless, single-purpose, and scoped to their stage.

**Where agents fail:**

- **Silent failures:** An agent may produce output that looks complete but is subtly wrong. There is no error — the model simply generated a plausible but incorrect artifact. Human review catches this.
- **Prompt injection:** Malicious or unexpected content in agent inputs (file contents, API responses) can redirect agent behavior. FORGE's agents operate on controlled inputs, but this risk is why agent-opened PRs are always reviewed before merge.
- **Context exhaustion:** If the input grows too large for the model's context window, earlier content is dropped. FORGE mitigates this by scoping each agent to a single stage with bounded inputs.

**Useful references:**
- [Tool Use with Claude](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview) — How tool calling works in the Claude API
- [Implement Tool Use](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use) — How tools are defined and executed in an agentic loop
- [Claude Agent SDK Overview](https://docs.anthropic.com/en/docs/claude-code/sdk) — The SDK FORGE's agents are built on
- [Mitigate Prompt Injections](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks) — Prompt injection risk in agentic systems

---

## 3. Agentic Orchestration Concepts

Orchestration is how multiple agents are sequenced, coordinated, and controlled. There are two broad approaches: deterministic and bounded.

**Deterministic orchestration** handles everything that must be predictable and auditable: state transitions, branch creation, PR opening, label management, ADO work item creation. In FORGE, this is GitHub Actions workflows. A workflow either runs its defined steps or it fails with a clear error — no model judgment involved.

**Bounded agent execution** handles everything that requires reasoning, generation, or interpretation: reading a requirements spreadsheet and producing structured user stories, writing implementation code from a design spec, analyzing test output and filing bug tickets. In FORGE, this is Claude Agent SDK calls. The model has latitude within a well-defined scope, but its outputs are committed to files that a human reviews before anything irreversible happens.

**Why the split matters:**

Letting an agent make irreversible decisions (merging code, creating production resources, updating ADO state) without a deterministic gate is where agentic systems go wrong. FORGE's design rule is simple: agents open PRs and produce artifacts; humans approve them. No agent merges its own PR. No stage begins until the prior gate is confirmed.

**Stateless by design:**

FORGE agents are stateless per stage. There is no shared agent memory across the pipeline. This is a deliberate architectural choice — it keeps each stage's behavior predictable, testable, and debuggable in isolation. If the Design Agent produces a bad design.md, the problem is contained to that stage. The fix is to rerun that stage with corrected inputs, not to untangle accumulated agent state.

**The Managed Agents exception (Stage 3):**

Stage 3 (Implementation) is a bounded exception to the standalone-agent pattern described above — not a departure from the stateless-per-stage principle. Instead of independent Claude Agent SDK calls, Stage 3 runs a single Anthropic Managed Agents session: one coordinator agent declares Backend, Frontend, and Test Writer as specialist subagents and runs them in parallel on a shared sandbox filesystem. The coordinator maintains state across its subagents *during that session* — this is precisely what lets it synthesize their outputs and resolve integration issues natively, instead of needing a separate integration-check job to catch conflicts after the fact.

This does not violate "stateless per stage." The stage still starts from committed files (design.md, openapi.yaml, tasks.md) and still ends by committing files (the feature branch) — nothing carries forward into Stage 4. State exists only inside the bounded Stage 3 window, then disappears when the session ends. See ADR-0010 in Document 4 (Governance) and Document 2 (Architecture) for the full architectural rationale.

**Useful references:**
- [Claude Agent SDK Overview](https://docs.anthropic.com/en/docs/claude-code/sdk) — Architecture of the SDK underlying FORGE's agents
- [Mitigate Prompt Injections](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks) — Adversarial inputs in agentic pipelines
- [Managed Agents Quickstart](https://platform.claude.com/docs/en/managed-agents/quickstart) — How agent sessions, environments, and agents are defined
- [Managed Agents Multi-agent Patterns](https://platform.claude.com/docs/en/managed-agents/multi-agent) — The coordinator/subagent pattern Stage 3 is built on

---

## 4. Prompt Engineering Basics

A prompt is the input the model receives — everything it has to work with when generating its output. Prompt engineering is the practice of structuring that input to produce reliable, high-quality output. You do not need to master it to work with FORGE, but you do need to understand it well enough to read agent prompts critically and recognize when a poor prompt is causing poor output.

**The core principles:**

**Be clear and specific.** Vague instructions produce vague outputs. FORGE's agent prompts specify the task, the format of the expected output, what the agent should not do, and how it should handle ambiguity. If agent output is consistently off in a predictable way, the prompt is usually the place to look first.

**Provide context, not assumptions.** The model only knows what is in the prompt. If a relevant constraint (a naming convention, a required field, a prohibited pattern) is not in the prompt, the model will not apply it. FORGE's core layer prompts encode hard constraints at the prompt level — not as hopes.

**Use examples.** A model given an example of the desired output format will follow it far more reliably than one given only a description of it. FORGE's schema-driven outputs (requirements.md structure, openapi.yaml format, ADO field mapping) work because the agent prompts include explicit format examples.

**Structure with XML tags.** Claude responds well to clearly delimited sections in prompts (e.g., `<task>`, `<constraints>`, `<output_format>`). FORGE's agent prompts use this pattern to separate the task definition from the context from the output specification.

**Know the limits.** Prompt engineering can improve reliability significantly, but it cannot make a model infallible. Complex reasoning chains, precise numeric constraints, and guaranteed rule adherence are all areas where prompts help but do not fully solve the problem — which is why human review gates exist.

**Useful references:**
- [Prompt Engineering Overview](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview) — Main entry point for Anthropic's prompting guidance
- [Be Clear and Direct](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — Core prompting principles
- [Claude 4 Best Practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices) — Current model-specific guidance for the models FORGE uses

---

## 5. Context Window Awareness

The context window is the total amount of text a model can "see" at once during a single invocation — its working memory. Everything the agent knows about the task must fit inside it: the system prompt, the task instructions, any files passed in, tool results, and the response the model is building.

**Why it matters in practice:**

- If inputs exceed the context window, content is dropped — typically the oldest content first. The model does not warn you; it simply works with what fits. An agent that silently loses the beginning of a requirements document will produce output that ignores those requirements.
- Even within the window, recall degrades as context grows. This is sometimes called "context rot" — the model's ability to accurately reference content from earlier in a long context is meaningfully worse than its ability to reference content near the end.
- Larger context windows are not a free solution. More tokens mean more cost and slower responses.

**How FORGE addresses this:**

FORGE agents are stateless and stage-scoped precisely to manage context. Each agent receives only the inputs relevant to its stage — not the entire conversation history or every artifact produced so far. The Requirements Agent gets the spreadsheet. The Design Agent gets requirements.md. The Backend Agent gets design.md and tasks.md. Nothing more. This keeps each invocation well within practical context limits and makes each agent's behavior reproducible.

**Useful references:**
- [Context Windows](https://docs.anthropic.com/en/docs/build-with-claude/context-windows) — Anthropic's explanation of context windows, context rot, and practical guidance

---

## 6. Responsible AI

AI tools are powerful enough to produce real harm when used carelessly. Responsible use means understanding the limitations, not over-relying on AI judgment, and maintaining genuine human oversight — not the appearance of it.

**Limitations to internalize:**

**Bias and blindspots.** LLMs reflect patterns in their training data. If the training data underrepresents certain approaches, domains, or user populations, the model's outputs will too. In a code generation context, this can surface as idiomatic but suboptimal solutions, missing accessibility considerations, or security patterns that are common in some stacks but not others. Reviewing agent-generated code critically — not just checking that it compiles — is how you catch this.

**Confidently wrong.** LLMs do not signal uncertainty reliably. An agent can produce a design.md that looks authoritative and well-structured while containing architectural decisions that are wrong for your context. The model does not know what it does not know. The Technical Approver at the design gate exists because of this.

**Over-reliance risk.** The most dangerous failure mode in AI-assisted workflows is the rubber-stamp — a human reviewer who approves agent output without genuinely reviewing it because the output looks good. FORGE's gates are only as effective as the attention the reviewer brings to them. Approving a PR because "the agent wrote it" is not a review.

**The correct posture:**

Treat agent output as a very capable first draft produced by a contributor who is knowledgeable but not infallible, who does not know your codebase as well as you do, and who cannot be held accountable for mistakes. Your job at each gate is to be the last line of defense, not a formality.

**Useful references:**
- [Anthropic's Responsible Scaling Policy](https://www.anthropic.com/responsible-scaling-policy) — How Anthropic evaluates and manages risk as model capability grows
- [Computer Use Tool Documentation](https://docs.anthropic.com/en/docs/agents-and-tools/computer-use) — Anthropic's own principles for high-stakes agentic actions, illustrating responsible AI in practice

---

## 7. Client Data Sensitivity

Legal Aid Alberta handles legally privileged and sensitive client information. This carries obligations that do not disappear because a process is AI-assisted.

**FORGE v1 does not process client data.** The pipeline operates on business requirements, code, and infrastructure configuration — none of which should contain client-identifying information, case details, or privileged communications. This is a design boundary, not an incidental one.

**Why this matters for developers:**

The risk is not that FORGE itself will mishandle client data — it is that developers, while configuring agents or troubleshooting a pipeline run, might inadvertently include client data in a prompt, a test fixture, or an example they paste into a clarification question. This would send that data to the Anthropic API, outside LAA's control.

**The rules:**

- Never include real client data in agent prompts, test inputs, example requirements, or any artifact that passes through the FORGE pipeline
- Use synthetic or anonymized data for all development and testing
- If you are unsure whether something qualifies as sensitive, treat it as sensitive

These rules apply during the build phase (using Mike's personal API account) and in production (using LAA's organizational API account). The account does not change the obligation.

**Useful references:**
- [Claude Code Security](https://docs.anthropic.com/en/docs/claude-code/security) — Principle of least privilege and explicit permission model — the same principles that govern what data should go into an agent

---

## 8. Practical AI Governance

Governance is how an organization maintains control, accountability, and auditability over AI use as that use scales. It does not require a regulatory framework to be meaningful — it requires clear rules, clear ownership, and a way to change the rules when they stop working.

**FORGE's governance model in brief:**

FORGE implements governance through structure, not policy documents. The human gates at every stage are governance. The ADR record in `core/decisions/` is governance. The RFC process for core layer changes is governance. The rule that no agent merges its own PR is governance. These are not bureaucratic formalities — they are the mechanisms by which a team retains meaningful control over what an AI-orchestrated pipeline produces and deploys on their behalf.

**What this means for developers:**

You are a participant in FORGE's governance, not a bystander. When you review and approve a PR at the code gate, you are exercising a governance function. When you identify that an agent is producing output that is consistently wrong in a particular way and raise it as a candidate for an RFC, you are participating in the governance process. When you flag that a team-layer customization is approaching a core-layer boundary, you are protecting the governance model.

**The broader context:**

Anthropic publishes its own governance commitments publicly, including its Responsible Scaling Policy (RSP), which defines how safety obligations scale with model capability. Understanding that Anthropic has its own governance layer helps put FORGE's internal governance in context — the platform you are building on is itself subject to structured oversight.

**Useful references:**
- [Anthropic's Responsible Scaling Policy](https://www.anthropic.com/responsible-scaling-policy) — How AI safety obligations scale with capability — the external analogue to FORGE's internal governance
- [Anthropic Transparency Hub](https://www.anthropic.com/transparency/voluntary-commitments) — Anthropic's public governance commitments

For FORGE's internal governance details — RFC process, ADR format, decision authority, core vs. team layer boundaries — see **Document 4: FORGE Governance Model**.

---

## 9. External Training and Certifications

The following resources are recommended for developers working with or inside FORGE. They are sequenced from broadest (conceptual foundation) to most specific (FORGE-relevant technical depth).

---

**[Anthropic Academy](https://anthropic.skilljar.com)**  
*Free — no subscription required — certificates on completion*

The official learning platform from Anthropic. Covers AI fluency, the Claude API, the Agent SDK, and Model Context Protocol (MCP) across 20+ self-paced courses (~15–20 hours total). This is the single most relevant resource for understanding what FORGE's agents are doing under the hood. Start here before anything else.

---

**[Managed Agents Quickstart](https://platform.claude.com/docs/en/managed-agents/quickstart)**  
*Free — official Anthropic documentation*

Covers how to define agents, environments, and agent sessions using the Managed Agents API. This is the concrete, hands-on companion to the conceptual "Managed Agents exception" explained in Section 3 above — read it before working on Stage 3 (Implementation Coordinator, Backend, Frontend, Test Writer).

---

**[Managed Agents Multi-agent Patterns](https://platform.claude.com/docs/en/managed-agents/multi-agent)**  
*Free — official Anthropic documentation*

Documents the coordinator/subagent pattern directly — one coordinator agent orchestrating multiple specialist subagents on a shared sandbox. This is the exact pattern FORGE's Stage 3 Implementation Coordinator is built on.

---

**[Claude Cookbooks — Managed Agents](https://github.com/anthropics/claude-cookbooks/tree/main/managed_agents)**  
*Free — open-source example code*

A working example of a coordinator running three specialists in parallel — a near-exact match to FORGE's Backend/Frontend/Test Writer subagent split. Reading the code is often faster than reading the docs if you already understand the concept and want to see it wired up.

---

**[Claude Certified Architect – Foundations (CCA-F)](https://anthropic.skilljar.com/claude-certified-architect-foundations-certification)**  
*Paid exam — free prep materials via Anthropic Academy*

Anthropic's first official certification, launched March 2026. Tests practical knowledge of Claude Code, Agent SDK, Claude API, and MCP through scenario-based questions covering multi-agent pipelines, CI/CD integrations, and structured data extraction — all directly relevant to FORGE. Recommended for any developer who will work on the agent layer or configure team-layer customizations.

---

**[DeepLearning.AI — AI for Everyone](https://www.deeplearning.ai/courses/ai-for-everyone/)**  
*Free — certificate available*

Andrew Ng's non-technical introduction to AI: what machine learning is, what AI can and cannot do today, and how AI is reshaping organizations and society. If you want a conceptual foundation before diving into the more technical Anthropic Academy content, this is the right starting point. Takes 6–8 hours.

---

**[DeepLearning.AI — Agentic AI](https://www.deeplearning.ai/courses/agentic-ai)**  
*Free short courses — no certificate*

Hands-on courses on building multi-step agentic workflows, including agentic design patterns (reflection, tool use, planning, multi-agent collaboration). Directly relevant to understanding how FORGE's ten-agent pipeline is structured and why each architectural choice was made the way it was.

---

**[AWS Certified AI Practitioner](https://aws.amazon.com/certification/certified-ai-practitioner/)**  
*Paid exam — free prep materials available*

A broad, vendor-agnostic foundation on AI/ML concepts, responsible AI principles, and cloud AI services. Useful for developers new to AI who want a structured credential. AWS leads in employer recognition for AI certifications. Not FORGE-specific, but builds durable foundational knowledge.

---

**[Microsoft Azure AI Fundamentals (AI-901)](https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-fundamentals/)**  
*Paid exam — free learning paths on Microsoft Learn*

Covers AI workloads, responsible AI principles, and Azure AI services. Relevant given LAA's Microsoft ecosystem (Azure hosting, Azure DevOps). A practical choice if your team is already invested in the Azure stack and wants a credential that maps directly to your existing infrastructure.

---

## Summary

| Concept | The short version |
|---|---|
| What LLMs are | Statistical models that predict plausible text — not databases, not calculators |
| Hallucination | Models generate confident-sounding wrong answers; human gates exist because of this |
| Agents | Models with tools in a loop; FORGE agents are stateless, stage-scoped, and single-purpose |
| Orchestration | Deterministic layer (GitHub Actions) + bounded agent execution (Claude SDK) — never mix them up |
| Prompt engineering | What goes into the prompt determines what comes out; vague in, vague out |
| Context window | The model's working memory; FORGE keeps inputs scoped per stage to stay well within limits |
| Responsible AI | The human gate is only as good as the attention the reviewer brings to it |
| Client data | Never goes into a FORGE pipeline, a prompt, or a test fixture — no exceptions |
| Governance | FORGE's gates, ADRs, and RFC process are governance in action; you are a participant |

---

*For hands-on setup and operation of a FORGE instance, proceed to **Document 6: Orchestration Manager Guide**.*
