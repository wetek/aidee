# Aidee system design

## Purpose

Aidee runs a private fleet of persistent AI assistants on a dedicated server. Hermes Agent is the first supported runtime. Each assistant can receive its own messaging account, MCP servers, project repositories, coding agent, approval rules, and resource limits.

Aidee targets one human owner. Team access and interchangeable agent runtimes are outside the first release.

## Components

~~~text
Dedicated Ubuntu VPS
├── Aidee controller, unprivileged Hermes process
├── Aidee admin helper, root-owned narrow command interface
├── Public Aidee release, root-owned and read-only to the controller
├── Private fleet state under /var/lib/aidee
└── Docker
    ├── assistant container A
    ├── assistant container B
    └── future assistant containers
~~~

## Trust boundaries

### Owner

The owner approves provisioning, destructive changes, purchases, external messages, production deployment, and expansion of tool access.

### Controller

The controller interviews the owner, generates plans and configuration, requests approved operations, validates the fleet, and reports failures. It has no unrestricted sudo permission and no Docker socket access.

The controller calls a root-owned Aidee helper for a fixed set of operations. The helper validates assistant identifiers, paths, resource limits, image references, mounts, ports, and requested actions. It never executes a controller-provided shell command or Compose file.

### Assistants

Each assistant runs in a separate Hermes container when credential, resource, or project isolation matters. An assistant can access only its own mounted state, repositories, secrets, and approved network services. It cannot access the controller state, Docker socket, administration helper, or another assistant.

Hermes supports multiple profiles in one container, but Aidee uses separate containers in the first release to keep credentials and resources isolated.

## Public code and private state

The public Aidee repository contains:

- Setup documentation.
- Versioned host and controller tools.
- Configuration schemas and policies.
- Fleet templates.
- Tests and release records.

Setup creates private state under `/var/lib/aidee`:

~~~text
/var/lib/aidee/
├── controller/
├── controller-home/
├── fleet/
│   ├── registry.yaml
│   ├── controller/
│   └── assistants/
│       └── <assistant-id>/
├── secrets/
├── runtime/
└── backups/
~~~

The owner may configure a private Git remote for approved fleet files. Public Aidee updates and private fleet history remain separate.

## State classes

Git-safe state includes:

- `SOUL.md`
- `config.yaml`
- `MEMORY.md` and `USER.md`
- Project records
- Custom skills
- Cron definitions
- Knowledge and preferences

Excluded state includes:

- `.env` and `auth.json`
- OAuth, MCP, messaging, Git, and model credentials
- Databases and sessions
- Logs and caches
- Cloned repositories and worktrees
- Generated packages and build output

The controller scans Git-safe changes before committing them. Encrypted backups cover selected excluded state.

## Secret entry

A chatbot must never receive secrets. The owner enters them through masked terminal input or a private Hermes dashboard.

Dashboards and APIs bind to loopback by default. Tailscale Serve is the default automated phone-access adapter. An SSH tunnel provides temporary access. Cloudflare Tunnel and Access remain a planned custom-domain adapter.

## Controller onboarding

The controller completes first-run onboarding before project or assistant work:

1. Authorize the owner through Telegram pairing or an explicit allowlist.
2. Draft the bot name, descriptions, supported commands, and avatar.
3. Generate avatar options when image generation is available, or request a JPG upload.
4. Show the full profile and wait for approval.
5. Apply and read back the Telegram profile through the Bot API.
6. Add the verified private dashboard URL as the menu button when selected.
7. Ask the owner to open the dashboard from their phone.

Controller setup is complete only after Telegram owner access, bot branding, and phone dashboard access are recorded as verified.

## Assistant provisioning

The controller collects:

1. Assistant name, purpose, and project scope.
2. Repositories and permission boundaries.
3. Messaging and dashboard choices.
4. MCP servers and allowed tools.
5. Coding-agent adapter.
6. Approval policy.
7. CPU, memory, and storage limits.
8. Git and encrypted backup choices.

It shows the complete plan before creating files, containers, routes, or external resources.

The administration helper then creates fixed directories and a container from validated inputs. The new assistant remains in `provisioning` status until health, messaging, dashboard, MCP, and coding checks pass.

## Coding work

A project assistant investigates a request before asking for implementation approval. After approval, it may create a work item and delegate a bounded task to the configured coding agent. Merge and production deployment remain manual by default.

The coding agent receives only the repository, task, credentials, and tools required for that run.

## Recovery

Reconstruct an assistant from:

1. Its recorded Aidee and Hermes versions.
2. Its Git-safe private fleet directory.
3. Its project repository declarations.
4. Its encrypted non-Git backup.

Images, containers, dependencies, caches, and generated worktrees are disposable. Recovery must work on a clean supported host without provider-specific machine images.

## Deferred work

- Additional agent runtimes.
- Multiple human operators.
- Automatic cloud-account or domain purchases.
- Controller-to-assistant messaging through a private MCP service.
- Shared-container optimization for low-risk assistants.
