---
name: domain-modeling
description: Build domain models, glossary in CONTEXT.md, and ADRs.
---

# Domain Modeling

Actively build and maintain the project's domain model, ubiquitous language glossary in `CONTEXT.md`, and Architectural Decision Records (ADRs).

## Core Practices

1. **Challenge against the glossary:** Flag terms that deviate from established definitions in `CONTEXT.md`.
2. **Sharpen ambiguous terminology:** Disambiguate overloaded concepts (e.g. Account vs Customer vs User) into crisp domain entities.
3. **Stress-test with concrete scenarios:** Use realistic edge cases to test domain boundaries and entity relationships.
4. **Cross-reference with code:** Check that codebase implementations match domain definitions.
5. **Update CONTEXT.md inline:** Record domain terms and relationships in `CONTEXT.md` as they are decided, keeping it free of ephemeral implementation details.
6. **Record ADRs for architectural decisions:** Create ADRs under `docs/adr/` when decisions are:
   - Hard to reverse.
   - Surprising without historical context.
   - The result of conscious trade-offs between alternatives.

## File Organization

- **Single-context repository:**
  - Root `CONTEXT.md` for domain vocabulary.
  - `docs/adr/` for numbered decision records (`0001-description.md`).
- **Multi-context repository:**
  - `CONTEXT-MAP.md` mapping bounded contexts.
  - Per-context `CONTEXT.md` and local `docs/adr/` directories.
