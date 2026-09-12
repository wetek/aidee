# Recovery contract

Git is the primary recovery mechanism.

An assistant is reconstructable from:

1. The Aidee and Hermes versions recorded in the private fleet registry.
2. Its Git-safe directory under `/var/lib/aidee/fleet`.
3. Its declared project repositories.
4. Its separately stored secrets and non-Git backup.

Containers, installed packages, caches, cloned repositories, worktrees, and build output are disposable.

The same recovery process must work on a clean host from another provider. See migration.md for the transfer sequence.

## Git-safe state

The host files under `/var/lib/aidee/fleet/assistants/<id>/` are authoritative. Approved paths are mounted directly into the container. The assistant writes to these host files. When the owner enables private Git backup, the controller alone commits and pushes approved files after a secret scan.

## Encrypted non-Git backup

Back up only state that cannot be reconstructed and must not enter Git:

- .env
- auth.json
- OAuth and MCP tokens
- state databases
- Session history selected for retention

Create a backup before upgrades and on a schedule. A recovery is complete only after enabled messaging, dashboard authentication, memory, repositories, MCP tools, coding agent, and observability are validated.
