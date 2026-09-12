# ADR 0002: Versioned platform and fleet state

Status: accepted

## Decision

Keep Aidee code, templates, and shared behavior in the public repository. Generate assistant-specific meaningful state under `/var/lib/aidee/fleet` on the owner's server.

Each assistant records an exact Aidee version. Approved assistant files are bind-mounted from private fleet state into the container. If the owner enables private Git backup, only the controller commits approved files after a secret scan.

## Reason

Public code can evolve without mixing it with an owner's identity, infrastructure, or memory. Private fleet state remains isolated and recoverable.

