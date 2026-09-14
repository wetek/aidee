# Diagram catalog

Ask a reader question, then pick the smallest diagram that answers it.
One concern per figure. Labels use CONTEXT terms.

## Default set

| Reader question | Kind | Put it in |
| --- | --- | --- |
| Who talks to whom? | `flowchart LR` | architecture |
| Where does data live? | `flowchart TB` | architecture |
| What happens on the main write path? | `sequenceDiagram` | architecture |
| How does a batch or import land? | `flowchart LR` | architecture |
| How does the ingest or sync API decide? | `flowchart TD` | architecture |
| Who wins a disagreement? | `flowchart TD` | architecture |
| What states are legal? | `stateDiagram-v2` | architecture |
| What work can a human resolve? | table | architecture |
| What is the whole system, in one glance? | `flowchart LR` | root README |

Skip any row that has nothing to show in this repo. A table beats a
diagram when the set is a small closed enum.

## Rules

- Map every node and edge to a code symbol collected in the claim list.
- Prefer `flowchart`, `sequenceDiagram`, and `stateDiagram-v2`.
- Keep node IDs free of spaces. Quote labels that contain punctuation.
- Do not name sections "Context" or "Containers". Use the reader question.
- Do not draw a future payload, database, or queue.
- Do not restyle nodes with colors. The renderer picks the theme.

## Anti-patterns

- One diagram that mixes actors, tables, and deploy targets
- Edges with no verb
- A second overview that repeats the README figure
- Inventing a box so the picture looks complete
