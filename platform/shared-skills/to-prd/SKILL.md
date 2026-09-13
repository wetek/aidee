---
name: to-prd
description: Convert ideas and conversations into actionable PRD specs.
---

# To-PRD (Product Requirement Document Synthesizer)

Convert discussions, brainstorms, issues, or feature ideas into concise, actionable, and testable Product Requirement Documents (PRDs).

## When to Use

- Turning an unstructured idea or chat thread into an executable project specification.
- Defining a new service, major feature, CLI tool, or integration.
- Preparing a clear plan of work before delegating tasks to autonomous subagents or coding tools.

## Standard PRD Structure

Every generated PRD must include these structured sections:

```markdown
# [Feature Name] - PRD

## 1. Problem Statement
Concise 1-2 paragraph description of the user problem, current limitations, and motivation.

## 2. Goals & Non-Goals
- **Goals:** Measurable, concrete outcomes delivered by this work.
- **Non-Goals:** Explicitly excluded capabilities to prevent scope creep.

## 3. User Stories & Workflows
- **As a [role], I want [capability] so that [benefit].**
- Step-by-step workflow describing user and system actions.

## 4. Technical Specifications & Architecture
- **Data models & schemas:** Input/output formats, database schemas, API payloads.
- **Components & Boundaries:** Modified services, new endpoints, file locations.
- **Security & Permissions:** Authentication, least-privilege access, secrets handling.
- **Error Handling:** Fallbacks, retries, user-facing error messages.

## 5. Acceptance Criteria (Checklist)
Checklist of unambiguous, testable conditions for completion:
- [ ] Criterion 1 (unit/integration test verifiable)
- [ ] Criterion 2 (UI / CLI behavior verifiable)
- [ ] Criterion 3 (schema / format compliance)

## 6. Open Questions & Risks
- List any unresolved dependencies, platform constraints, or research spikes needed.
```

## Generation Guidelines

1. **Be specific and measurable:** Replace vague statements ("fast", "intuitive") with concrete limits or checkable actions.
2. **Prioritize testability:** Every acceptance criterion must be verifiable by an automated test or clear manual check.
3. **Keep it concise:** Prune boilerplate; focus on architectural decisions and checkable requirements.
