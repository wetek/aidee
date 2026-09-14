# Aidee versioning

Aidee uses semantic versions.

- Patch: fixes that preserve assistant behavior and configuration contracts.
- Minor: backward-compatible additions to instructions, skills, workflows, or tools.
- Major: changes that require migration or materially change fleet behavior.

Every assistant records an exact Aidee version in the private fleet registry. Released containers never follow a moving `latest` tag.

The root `LATEST` file names the newest published tag for update discovery. Controllers may preview that tag, but they must not activate it without owner approval.

Setup plans, assistant image requests, and the host installer read `LATEST`
through `platform/release.py`. Do not copy the tag into schemas, examples, or
guides.

Alpha 13 and later use one owner-approved fleet updater for the host,
controller knowledge, pinned Hermes runtime, and registered assistants. The
controller's daily job discovers releases and offers Start update on
Telegram. Cron notices use tap-to-send buttons because Hermes cron cannot
use clarify. It applies only after the owner sends Start update, then
Apply now.

## Release process

1. Change the platform files.
2. Write the published tag name in `LATEST`.
3. Add `platform/releases/<tag>.md` and one line to `platform/releases/README.md`.
4. Tag that commit with the same name as `LATEST`.
5. Deploy to a designated pilot assistant as the canary.
6. Validate messaging, dashboard, memory, tools, the configured coding agent, and any enabled observability.
7. Roll out to selected assistants through the controller.

The controller records the previous and current versions for every rollout. A rollback restores the previous image and platform bundle without replacing assistant-specific state.
