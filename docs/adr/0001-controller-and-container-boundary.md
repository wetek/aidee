# ADR 0001: Controller and container boundary

Status: accepted

## Decision

Run the Hermes controller as an unprivileged account on a dedicated VPS. Give it no sudo permission or Docker socket access. Expose approved host and container operations through a root-owned Aidee helper with strict argument, path, image, mount, and resource validation.

Run assistants in separate containers when they require project, credential, resource, or network isolation. An assistant can access only its own mounted state, repositories, and configured services.

## Reason

The controller must request provisioning, repair, update, and inspection without gaining arbitrary root execution. Containers reduce the impact of compromised prompts, tools, dependencies, or credentials.

