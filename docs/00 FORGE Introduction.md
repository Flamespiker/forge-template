# FORGE Introduction
 
**Full-SDLC Orchestration with Review Gates for Engineers**
 
---
 
## What is FORGE?
 
FORGE is an AI-orchestrated software development platform. It takes business requirements — captured by a BA in a standard spreadsheet — and moves them through a complete software development lifecycle, from clarifying questions to a deployed application, with humans reviewing and approving at defined checkpoints along the way.
 
FORGE is not a hosted service. It's a **GitHub template repository**. Each development team at Legal Aid Alberta clones it and runs their own instance — their own agents, their own pipeline, their own history of decisions — while staying compatible with a shared core that everyone builds on.
 
## The Problem FORGE Solves
 
AI coding assistants are good at writing code when someone tells them exactly what to write. They're less good at the parts around the code: turning a business request into clear requirements, keeping a design consistent with what was actually approved, making sure tests and security checks run before anything ships, and leaving a trail that shows why decisions were made.
 
FORGE exists to close that gap — not by making AI more autonomous, but by giving it a structured, repeatable path to follow, with people checking the work at the points that matter.
 
## The Core Pattern
 
FORGE runs on two things working together:
 
- **Deterministic orchestration** handles the parts that must behave the same way every time — creating branches, opening pull requests, tracking state, moving work from one stage to the next.
- **Bounded agent execution** handles the parts that require judgment — reading requirements, writing code, designing tests — with each agent scoped to a specific stage and a specific job.
In short: **agents do the work, humans approve the outcomes.** No agent moves the pipeline forward on its own judgment call. Every stage produces something a person can read, question, and either approve or send back.
 
## How Work Moves Through FORGE
 
At a glance, a request travels through FORGE like this:
 
1. A BA fills out an intake spreadsheet describing what's needed.
2. FORGE asks a short round of clarifying questions, then drafts formal requirements.
3. Once a person approves the requirements, FORGE creates the corresponding work items and drafts a technical design.
4. Once a person approves the design, FORGE implements the backend, frontend, and tests in parallel.
5. QA and security checks run against the implementation.
6. Once everything passes and a person gives final sign-off, FORGE deploys the application.
If the change is an enhancement to an existing application rather than a new one, FORGE first spends time understanding the existing codebase before any requirements work begins.
 
The full detail of each stage — triggers, outputs, and timing — is covered in the FORGE Architecture Document. This is the shape of it, not the specification.
 
## Where Humans Stay in Control
 
FORGE is built around the idea that AI should accelerate the parts of software delivery that are mechanical and well-understood, while people remain the decision-makers at every point that carries real consequence. Concretely, that means a human checkpoint before:
 
- Requirements become official work items
- A design is locked in
- Code is merged
- QA results are accepted
- Security findings are cleared
- Anything is deployed
Nothing moves past one of these points without a person saying so.
 
## Two Layers: What's Fixed, What's Yours
 
FORGE separates what has to be consistent across every team from what each team should be free to shape:
 
- **The core layer is locked.** Security gates, work item structure, naming conventions, branching strategy, deployment standards, and the intake spreadsheet format are the same everywhere. This is what makes FORGE instances trustworthy and comparable across teams.
- **The team layer is yours.** Specific tools, agent personas, notification channels, and team-specific skills can be adapted to how your team actually works.
Because FORGE is a template repository, teams can pull in updates to the core layer over time without losing what they've customized.
 
## Greenfield and Enhancement Work
 
FORGE handles two kinds of projects: building something new, and changing something that already exists. For new applications, FORGE starts straight from intake. For enhancements, FORGE first reads the existing codebase to understand its architecture and conventions, so the work it proposes actually fits what's already there.
 
## The Orchestration Manager
 
Every team instance of FORGE has an owner — a developer or tech lead called the **Orchestration Manager**. This person maintains the team's instance, manages customizations within the boundaries of the core layer, and is the point of contact when something in the pipeline needs attention. Their role is covered in full in the Orchestration Manager Guide.
 
## What FORGE Is Not
 
To set expectations early:
 
- FORGE does not replace the BA. It structures and accelerates the work that follows a BA's requirements gathering — it doesn't do the requirements gathering itself.
- FORGE does not grant AI agents the authority to ship changes on their own. Every stage is bounded, and every gate requires a person.
- FORGE's security approach is practical, not built for a heavy regulatory environment. It's scoped to where Legal Aid Alberta operates today, not designed as a compliance framework for a more heavily regulated context.
## Where to Go Next
 
This document is the starting point. The rest of the FORGE document set goes deeper:
 
- **Product Specification** — the full feature set, personas, and success criteria
- **Architecture Document** — the technical design behind every stage
- **Governance Model** — how core changes get proposed and decided
- **AI Foundations Guide** and **Orchestration Manager Guide** — the two training tracks
- **Customization Reference** — exactly what's locked, flexible, or open
- **FORGE README** — how to get a new instance running in under 30 minutes
If you're new to FORGE, this is all you need to understand *why* it exists and *how* it's shaped. Everything else builds on it.
 
