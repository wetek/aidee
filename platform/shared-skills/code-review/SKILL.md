---
name: code-review
description: "Two-axis diff review: standards compliance and spec fidelity."
---

# Code Review

Two-axis review of the diff between `HEAD` and a fixed point the user supplies:

- **Standards**: does the code conform to this repo's documented coding standards and clean design principles?
- **Spec**: does the code faithfully implement the originating issue / spec?

Both axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

## Process

### 1. Pin the fixed point

Whatever the user designated as the fixed point (a commit SHA, branch name, tag, `main`, `HEAD~5`, etc.). If not specified, request it.

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, comparing against the merge-base). Note the commit list via `git log <fixed-point>..HEAD --oneline`.

Confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty before proceeding.

### 2. Identify the spec source

Look for the originating spec in this order:

1. Issue references in commit messages (`#123`, `Closes #45`, etc.), fetched via issue tracker or local issue files.
2. A path passed as an argument.
3. A spec or PRD file under `docs/`, `specs/`, or `.scratch/` matching the branch or feature name.
4. If no spec is found, ask where the spec is. If none exists, the **Spec** sub-agent reports "no spec available".

### 3. Identify standards sources

Check for repo standards documents (`CODING_STANDARDS.md`, `CONTRIBUTING.md`, linter configs).

The Standards axis carries the baseline of Fowler code smells (*Refactoring*, ch.3):

- **The repo overrides:** Documented repository conventions take precedence over baseline heuristics.
- **Judgement calls:** Each smell is a heuristic, never a hard tool error. Skip anything tooling/linters already enforce.

Smell baseline (*what it is* → *how to fix*):

- **Mysterious Name**: function, variable, or type whose name doesn't reveal intent → rename clearly.
- **Duplicated Code**: identical or near-identical logic in multiple hunks → extract shared helper.
- **Feature Envy**: a method reaching into another object's internal data → move method onto the target data.
- **Data Clumps**: parameters or fields repeatedly travelling together → encapsulate into a dedicated type.
- **Primitive Obsession**: primitives representing rich domain concepts → create small domain types.
- **Repeated Switches**: recurring switch/if cascades across types → replace with polymorphism or dispatch maps.
- **Shotgun Surgery**: single logical change requires edits across many files → consolidate into one module.
- **Divergent Change**: module modified for multiple unrelated reasons → split responsibilities.
- **Speculative Generality**: unused hooks, parameters, or abstractions → delete and inline.
- **Message Chains**: deep property navigation (`a.b().c().d()`) → encapsulate behind a single method call.
- **Middle Man**: class or function primarily delegating without adding value → call target directly.
- **Refused Bequest**: subclass ignoring inherited behavior → replace inheritance with composition.

### 4. Spawn sub-agents in parallel

- **Standards sub-agent**: review diff against repository standards and smell baseline. Cite the rule, file, and line/hunk for every finding.
- **Spec sub-agent**: review diff against the spec. Report missing requirements, scope creep, and incorrect implementations, quoting spec lines.

### 5. Aggregate findings

Present reports under separate `## Standards` and `## Spec` sections without merging or reranking. Provide a summary with total findings per axis and the worst issue on each axis.
