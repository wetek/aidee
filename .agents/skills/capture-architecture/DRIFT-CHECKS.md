# Drift checks

Run these after every capture. Fail closed on broken links.

## Link check

From this skill directory, with `--root` set to the repository being
documented:

```sh
python3 scripts/check-markdown-links.py --root <repo-root>
```

The script resolves relative Markdown targets and GitHub-style heading
fragments. It ignores `http`, `https`, and `mailto` links. A missing file
or unknown fragment is a failure.

After a heading rename, grep the old slug before relying on the script.
A hand-written `#whats-left` will not match `What we skipped`.

## Code to docs

Build a matrix for this repo. Typical rows:

| Claim | Doc location | Code symbol |
| --- | --- | --- |
| Ingest or sync result statuses | architecture paragraph | shared status enum |
| Workflow edges | state diagram | adjacency map |
| Human work kinds | reviewer table | review item types |
| Seed or deliver behavior | product README | seed command |
| Deploy secrets and cron | deploy notes | deploy config |
| Who may write the system of record | ADR plus architecture | auth and API handler |

If a cell disagrees, the ranking in [DOC-LAYERS.md](DOC-LAYERS.md) decides.

## Phrase traps

Grep and delete or rewrite:

- topology the code already left behind
- leftover servers described as the live path
- plan language presented as current topology
- CONTEXT `_Avoid_` terms used as primary names

## Plan supersession

If a plan still describes an older topology, say so in the report. Do not
promote the plan into architecture. Do not silently edit the plan unless
the user asked.

## Vocabulary

Primary terms in diagrams and headings must exist in CONTEXT, or CONTEXT
must gain them in the same pass. Use the `domain-modeling` companion
when you add a term.
