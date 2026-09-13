# ADR 0001: Controller and container boundary

Status: accepted

## Decision

Run the Hermes controller on a dedicated VPS with passwordless sudo permission for autonomous host and fleet management, while assistants remain isolated in unprivileged containers. Expose container lifecycle and verified operations through a root-owned Aidee helper with strict argument, path, image, mount, and resource validation.

Run assistants in separate containers when they require project, credential, resource, or network isolation. An assistant can access only its own mounted state, repositories, and configured services.

## Reason

The controller must request provisioning, repair, update, and inspection without gaining arbitrary root execution. Containers reduce the impact of compromised prompts, tools, dependencies, or credentials.

