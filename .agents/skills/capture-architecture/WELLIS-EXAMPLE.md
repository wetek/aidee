# Worked example

This is one capture that produced this skill. Use it as a worked
example, not as a template to copy into another product.

## What that system was

A patient information system for medically supervised weight care. Three
products share one domain:

- `legacy_import` reads an immutable export and writes fingerprinted runs
- `patient_intake` collects a new intake into its own Postgres and delivers
  later through an outbox
- `review_console` is the system of record and the care-team queue

They compile against `@wellis/contracts`. Sources send drafts. They never
write the console database.

## Plan history the capture had to read

Plans 001 through 005 lived under `.cursor/plans`. Several early choices
were later reversed. A capture that read only the latest README would have
missed why.

1. Quarantine-first JSON importer. No Postgres. Strict baseline. Merge
   only on full identity match.
2. Importer handoff. 6 ready bundles, 2,460 quarantined, 21 orphans.
   Quarantine reduced one evidence-backed rule at a time.
3. Review console data layer. npm workspaces, shared contracts including
   the eligibility evaluator, staged records vs real patients, field-level
   provenance, bearer-token ingest.
4. Data-layer handoff. Schema, classify, ingest API, seed. Some counts
   were already stale after merge. A third importer database was still on
   the table.
5. Assignment completion. Two product databases, not three. File-based
   importer kept. Every `auto_*` eligibility result goes through
   `in_review` to a human. Bulk group resolution deferred. Demo reviewer
   instead of full auth.

A capture must read those plans as history, then rank live contracts and
write paths above them.

## Decisions that survived into docs

- Shared contracts package (ADR 0001)
- Field-level provenance and human precedence (ADR 0002)
- Staged records separate from `patient` (ADR 0003)
- Sources never write the system of record (ADR 0004)
- Human review after every automatic eligibility result
- Immutable import runs, compare-then-deliver
- Intake submit stays up when the console is down (transactional outbox)

## What the docs look like after capture

Reading order: root README, CONTEXT, `docs/architecture.md`, then one
product README. `docs/README.md` is the hub. Each leaf has `## See also`.

Architecture diagrams match the catalog: who talks to whom, where data
lives, new-intake sequence, legacy-import flow, ingest classification,
field precedence, intake state machine, reviewer table.

Deferred work moved to `SKIPPED.md`. Architecture points at that page
instead of keeping a leftover dump. After that split, `#whats-left`
anchors in architecture and the import report went stale. That is the
failure the link checker exists to catch.

## Lessons to reuse

- Prove sharing: extract the package, then require existing consumer
  tests to pass unchanged.
- Ship the evaluator as a function when three products must agree.
- Keep a second adapter only when the question is different (legacy
  uncertainty vs a complete new intake). Share the constants catalog.
- Mark seed counts stale after a ruleset merge. Reseed before designing
  around the numbers.
- Freeze importer normalizations when remaining issues need a human, not
  another guessed alias.
- Record explicit supersessions. Two databases replacing three is a
  decision, not a cleanup note.
