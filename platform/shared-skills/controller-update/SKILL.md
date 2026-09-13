---
name: controller-update
description: Previews and applies unprivileged Aidee controller knowledge updates. Use when the owner asks to check, load, sync, or update Aidee.
---

# Controller update

Read `docs/update-controller.md` from the latest fetched Aidee release.

Rules:

1. Fetch and preview before asking for approval.
2. Name the installed host, synced knowledge, and available releases separately.
3. Summarize release notes and migration requirements.
4. Apply knowledge sync only after owner approval.
5. Never run the sync script with sudo.
6. Never modify `/opt/aidee`, system packages, or system services.
7. Never claim that knowledge sync updated the host installation.
8. Start a new Hermes session after skill sync.

When invoked by cron, stop after preview and ask the owner. Never apply an update from a scheduled run.

If a host update is required, report it and wait for the documented root-owned updater. Do not invent commands or request broader privileges.
