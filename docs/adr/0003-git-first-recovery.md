# ADR 0003: Git-first recovery

Status: accepted

## Decision

Use the pinned public Aidee release plus private fleet state as the primary recovery inputs. The owner may back up Git-safe fleet state to a private Git remote. Treat containers, dependencies, caches, checkouts, and generated runtime files as disposable.

Use encrypted backups only for non-reconstructable state that cannot be committed.

## Reason

This keeps recovery understandable without requiring every owner to use one Git provider. It also separates public product history, private fleet history, and secret backups.

