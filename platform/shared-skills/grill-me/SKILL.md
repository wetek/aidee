---
name: grill-me
description: Interrogate requirements and clarify architecture before coding.
---

# Grill-Me (Requirements & Architecture Interrogation)

Interrogate requirements, unearth edge cases, challenge hidden assumptions, and clarify architectural tradeoffs before writing code.

## When to Use

- Starting a non-trivial feature, refactoring, or architectural change.
- Handling open-ended or ambiguous requests from the owner or user.
- Evaluating multiple design options or integration strategies.
- Clarifying boundaries, security constraints, and operational requirements.

## Interrogation Workflow

### 1. Interrogate Scope & Goals

Ask targeted, probing questions to establish exact boundaries:
- **Core value:** What exact problem does this solve? What is the primary use case?
- **Non-goals:** What is explicitly out of scope for this iteration?
- **Users & Actors:** Who calls this? What permissions and roles are required?

### 2. Probe Edge Cases & Failure Modes

- **Boundary conditions:** What happens with empty data, extreme scale, zero values, or duplicate records?
- **Failure recovery:** How should network timeouts, database outages, or third-party service failures be handled?
- **Concurrency & Race conditions:** Can multiple concurrent requests mutate the same resource?
- **Data integrity & Migration:** How does existing data migrate? Is backward compatibility preserved?

### 3. Evaluate Architecture Tradeoffs

When multiple implementation paths exist, present structured options:
- **Option A vs Option B:** Contrast complexity, performance, maintainability, and operational overhead.
- Present decisions clearly with pros, cons, and recommended default.
- On interactive channels (e.g. Telegram), present choices with interactive clickable buttons.

### 4. Record Decision

Document the agreed outcome before coding:
- Record decision context, chosen solution, rationale, and consequences (ADR format).
- Summarize accepted requirements and explicit non-goals.

## Anti-Patterns to Avoid

- **Vibe coding without boundaries:** Jumping into implementation before nailing down specifications.
- **Passive acceptance of vague prompts:** Implementing ambiguous requirements without asking clarifying questions.
- **Premature over-engineering:** Adding speculative complexity that was not requested or justified.
