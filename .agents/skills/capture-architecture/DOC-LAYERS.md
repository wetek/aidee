# Doc layers

Put each fact in one file. Duplicate truth drifts.

## Source ranking

On conflict, higher wins:

1. Compiled contracts, schemas, enums, and state machines
2. The write path that mutates the system of record
3. Source delivery (outbox, CLI, seed, cron)
4. Deploy config
5. ADRs
6. Product READMEs
7. Architecture narrative and the root README
8. Plans, work logs, skipped-work pages

`CONTEXT.md` is not a behavior source. It is the vocabulary filter.

If an ADR disagrees with code, do not silently rewrite current-state docs
to match the ADR. Either the code is wrong, or the ADR is superseded.

Plans are not current architecture. An unchecked plan item can describe a
topology the code already left behind.

## What belongs where

**Root README.** One short system sentence. One overview diagram. Status.
Reading order. Pointers. No decision trees, env dumps, or wave history.

**CONTEXT.md.** Term, definition, `_Avoid_` list. One or two sentences.
Define what the thing is, not what it does. No implementation. Single
context at the repo root, or a `CONTEXT-MAP.md` that points at several.
When you add or sharpen a term, follow `CONTEXT-FORMAT.md` from the
`domain-modeling` companion.

**docs/architecture.md.** How data moves now. Who may write what. Diagrams
tied to live seams. Point to ADRs for why, skipped-work for not-now,
product READMEs for how to run.

**docs/adr/.** Sequential `0001-slug.md`. A paragraph is enough. Optional
considered options and consequences only when they add information.
When you offer an ADR, follow `ADR-FORMAT.md` from the
`domain-modeling` companion.

**Product README.** Setup, env, commands, owned schema. Intro: this product
is part of the system; read CONTEXT and architecture first.

**Ops report.** Dated aggregate counts and fingerprints. No secrets or
personal data. Do not copy those counts into architecture.

**Deploy notes.** Projects, databases, secrets, migrate, seed, cron. No
domain lecture.

**Skipped-work page.** Improvements noticed and not built. Architecture
must not keep a parallel leftover list.

## Bans

- How-to-run steps in architecture
- Schemas, routes, or table names in CONTEXT
- Aspirational boxes on a current-state diagram
- Specialty counts or rule tables copied out of their own docs
- Treating a plan checkbox as a deployed fact
