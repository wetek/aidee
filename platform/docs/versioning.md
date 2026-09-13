# Aidee versioning

Aidee uses semantic versions.

- Patch: fixes that preserve assistant behavior and configuration contracts.
- Minor: backward-compatible additions to instructions, skills, workflows, or tools.
- Major: changes that require migration or materially change fleet behavior.

Every assistant records an exact Aidee version in the private fleet registry. Released containers never follow a moving `latest` tag.

The root `LATEST` file names the newest published tag for update discovery. Controllers may preview that tag, but they must not activate it without owner approval.

Controller knowledge sync and host updates are separate. Knowledge sync runs without root and refreshes shared Aidee skills. Host updates change `/opt/aidee`, packages, or system services and require a documented owner-approved process.

## Release process

1. Change the platform files.
2. Update tests and migration notes.
3. Create a release manifest under releases/.
4. Increment VERSION.
5. Build an immutable image tagged with the version and source commit.
6. Deploy to a designated pilot assistant as the canary.
7. Validate messaging, dashboard, memory, tools, the configured coding agent, and any enabled observability.
8. Roll out to selected assistants through the controller.

The controller records the previous and current versions for every rollout. A rollback restores the previous image and platform bundle without replacing assistant-specific state.

