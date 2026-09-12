# Fleet migration

The fleet must be reproducible on a clean supported host. VPS providers are deployment targets, not sources of truth.

## Inputs

- The pinned public Aidee release.
- The optional private Git repository containing approved fleet state.
- Encrypted backup of non-Git state.
- DNS access for moving dashboard routes.
- Access to enabled external services such as Git hosting, messaging, observability, and private dashboard access.

## Migration sequence

1. Pause new agent and coding runs.
2. Commit and push Git-safe state when private Git backup is enabled.
3. Create a final encrypted backup of non-Git state.
4. Record the installed Aidee and Hermes versions and assistant health.
5. Provision and secure the destination host.
6. Install the recorded public Aidee release.
7. Restore private fleet state.
8. Restore controller secrets and non-Git state.
9. Rebuild assistant containers from the fleet registry.
10. Restore each assistant's secrets and selected non-Git state.
11. Validate memory, messaging, dashboards, repositories, MCP tools, coding agents, and observability.
12. Move optional dashboard routes to the destination.
13. Run one harmless test request per assistant.
14. Retire the old host after the validation period.

## Portability rules

- Do not depend on provider-specific machine images.
- Keep host installation steps scripted in Aidee.
- Use standard Docker images, bind mounts, environment files, and filesystem paths.
- Keep provider identifiers out of assistant identity and project configuration.
- Record external resource names without embedding credentials.
- Never delete the source host until the destination passes recovery validation.
