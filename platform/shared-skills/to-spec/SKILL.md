---
name: to-spec
description: Synthesize conversations into structured technical specs.
---

# To-Spec

Synthesizes conversational discussions, requirements, and codebase understanding into a structured, actionable technical specification.

## Principles

- **Pure synthesis:** Synthesize decisions already agreed upon; do not run a new interview.
- **Identify test seams:** Define the highest test seams where behavior will be verified. Keep seams minimal.
- **Respect domain language:** Incorporate glossary terms from `CONTEXT.md` and adhere to existing ADRs.

## Specification Template

```markdown
# [Feature Name] - Specification

## Problem Statement
The user problem and context from the user's perspective.

## Solution Overview
The proposed technical solution and behavior from the user's perspective.

## User Stories
Numbered list of comprehensive user stories:
1. As a [role], I want [capability], so that [benefit].

## Implementation Decisions
- Modules to create or modify.
- Module interfaces, contracts, and responsibilities.
- Architectural boundaries, schemas, and data models.
- Note: Avoid volatile code snippets or transient file paths unless capturing exact state machine / schema definitions.

## Testing Strategy & Seams
- Specific test seams and boundaries.
- Definition of done: external behavior verification vs internal unit tests.
- Prior art in the codebase.

## Acceptance Criteria
- [ ] Criterion 1 (automated test verifiable)
- [ ] Criterion 2 (functional / CLI verifiable)
- [ ] Criterion 3 (schema / contract compliant)

## Out of Scope
Explicitly excluded items and deferred capabilities.
```
