---
name: improve-architecture
description: Reduce complexity and refactor codebases for modularity.
---

# Improve-Architecture (Anti-Entropy & Refactoring)

Systematically eliminate accidental complexity, improve modularity, and fight code entropy without altering external behavior.

## Core Principles

- **Separation of Concerns:** Keep business logic isolated from infrastructure, I/O, network protocols, and persistence layers.
- **Single Responsibility:** Each module, class, or function must have one reason to change.
- **Explicit Dependencies:** Use dependency injection and explicit parameters; avoid global mutable state.
- **Narrow Interfaces:** Design cohesive, minimal interfaces that expose only what consumers require.
- **Anti-Entropy Cleanup:** Regularly eliminate dead code, redundant abstractions, duplicate logic, and cyclic dependencies.

## Systematic Refactoring Workflow

Follow this 4-step workflow when improving existing code:

### Step 1: Baseline Verification

- Ensure a passing test suite exists covering the code to be refactored.
- If coverage is insufficient, use the `tdd` skill to write characterization/regression tests before making structural changes.

### Step 2: Identify Complexity & Code Smells

Scan for common anti-patterns:
- **God Modules / Functions:** Files over 500 lines or functions doing multiple unrelated tasks.
- **Feature Envy:** Functions that excessively access and manipulate another module's internal state.
- **Deep Nesting:** Conditionals nested 3+ levels deep (replace with early returns / guard clauses).
- **Leaky Abstractions:** Low-level implementation details exposed through high-level APIs.
- **Duplicated Logic:** Identical or near-identical business logic repeated across multiple call sites.

### Step 3: Apply Atomic Refactorings

Make small, incremental, behavior-preserving transformations:
- **Extract Function / Module:** Break large routines into named, pure helpers.
- **Invert Dependencies:** Accept interfaces/callables rather than hardcoded concrete classes.
- **Consolidate Duplication:** Unify repeated patterns into reusable utilities.
- **Simplify Control Flow:** Replace nested `if/else` ladders with polymorphism, mapping tables, or early exits.

### Step 4: Verify Zero Regressions

- Run the full test suite after each atomic edit.
- Confirm linting, static type checks (`mypy`, `tsc`), and integration tests all pass with zero errors.

## Refactoring Discipline

- **Never combine refactoring with feature additions:** Separate structural cleanup commits from behavior-changing commits.
- **Keep diffs reviewable:** Make small, logical commits rather than massive monolithic rewrites.
