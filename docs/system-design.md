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

The controller interviews the owner, generates plans and configuration, executes approved operations, validates the fleet, and reports failures. It has sudo access for autonomous host and fleet management, and coordinates assistant containers through the root-owned Aidee administration helper.

The controller calls a root-owned Aidee helper for a fixed set of operations. The helper validates assistant identifiers, paths, resource limits, image references, mounts, ports, and requested actions. It never executes a controller-provided shell command or Compose file.

The helper listens on a Unix socket available only to the controller account. It supports fixed image, create, start, stop, and status operations. The controller submits validated JSON requests after owner approval.

### Assistants

Each assistant runs in a separate Hermes container when credential, resource, or project isolation matters. An assistant can access only its own mounted state, repositories, secrets, and approved network services. It cannot access the controller state, Docker socket, administration helper, or another assistant.

Hermes supports multiple profiles in one container, but Aidee uses separate containers in the first release to keep credentials and resources isolated.

## Shared assistant image

Every assistant on one Aidee release uses the same immutable image ID. Docker stores shared read-only layers once. Each assistant still has a separate container and writable state.

The image derives from a pinned official Hermes image. Alpha 14 applies one
checksum-verified temporary Hermes runtime-context patch to the exact pinned
source. It adds GitHub CLI, jq, OpenCode, socat, Aidee shared skills, and the
onboarding plugin. It contains no identity, memory, project repository, or
credential.

The root-owned image record under `/etc/aidee/images` is authoritative. Controller-written requests choose an Aidee version, not a Docker image or build argument.

Assistant containers receive:

- Their own Hermes data directory.
- Individual mounts for `SOUL.md` and memories.
- A private Hermes `config.yaml` and `.env` inside its own data directory.
- Their own CPU, memory, and process limits.
- A read-only root filesystem and bounded temporary filesystems.
- A loopback dashboard forwarded to one host port.

They never receive the Docker socket, controller files, another assistant's directory, host networking, or privileged mode.

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
- `assistant.yaml`
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

Dashboards and APIs bind to loopback by default. Tailscale Serve is the default automated phone-access adapter. An SSH tunnel provides temporary access. An owner may record a custom HTTPS origin per dashboard. That origin is stored in `registry.yaml` and the assistant `config.yaml` `dashboard.public_url`. Telegram menu buttons copy that URL. Cloudflare Tunnel remains a planned adapter for provisioning the hostname itself.

## Controller onboarding

The controller runs a locked durable gate before operational work. An
incomplete required step produces one resume offer. `Not now` suppresses
repeat offers until manual reopen or a later schema adds a required step.
After `Resume now`, the controller completes this flow:

1. Authorize the owner through Telegram pairing or an explicit allowlist.
2. Offer to configure the bot profile or explicitly keep the current profile.
3. If accepted, draft the bot name, descriptions, supported commands, and avatar.
4. Generate avatar options when image generation is available, or request a JPG upload.
5. Show the full profile and wait for approval.
6. Apply and read back the Telegram profile through the Bot API.
7. Add the verified private dashboard URL as the menu button when selected.
8. Ask the owner to open the dashboard from their phone.
9. Create the owner-approved daily update check when selected.

Controller setup is complete only after every step is `completed` or
owner-confirmed `skipped`. Required steps control the resume offer. Optional
steps remain part of the resumed flow and block the complete rollup until
resolved.

The same versioned module defines assistant steps by role, assistant kind, and
non-secret configuration. Coding and project assistants must resolve repository
and coding-tool setup. Personal and client assistants may skip those steps with
a recorded reason. Atomic file replacement under `fcntl` locking prevents two
concurrent Telegram turns from both producing an offer.

The daily update job performs preview-only discovery. It stays silent when no
update exists and gives the owner the documented SSH preview command for a new
release. It never applies an update or modifies root-owned host files.

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
