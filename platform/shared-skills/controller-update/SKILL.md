---
name: controller-update
description: Checks Aidee releases and guides the owner through the fleet updater. Use when the owner asks to check or update Aidee.
---

# Controller update

Read `docs/update-controller.md` from the latest fetched Aidee release.

Rules:

1. Fetch and preview before asking for approval.
2. Name the installed host and available releases.
3. Summarize release notes and migration requirements.
4. Give the owner the preview command from `docs/update-controller.md`.
5. Ask the owner to run preview and review its actions before apply.
6. Never run the root-owned updater from a Hermes interaction or cron.
7. Report host, controller, cron, image, and assistant verification results.

When invoked by cron, stop after preview and ask the owner. Never apply an update from a scheduled run.

The fleet updater handles controller knowledge as part of apply. Do not run the
legacy split knowledge-sync workflow for Alpha 13 or later.
