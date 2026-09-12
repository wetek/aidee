# ADR 0005: Provider-neutral migration

Status: accepted

## Decision

Treat compute providers as replaceable hosts. Rebuild the controller and assistants from a pinned public Aidee release, private fleet state, and encrypted non-Git state.

Do not use a provider machine image as the primary recovery method.

## Reason

The same documented process must recover the fleet after host loss or a provider change.
