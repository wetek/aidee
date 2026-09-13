# Administration helper

The unprivileged Aidee controller will receive narrow tools for:

- Provisioning and validating assistants.
- Managing containers and platform versions.
- Managing optional dashboard routes.
- Checking storage, CPU, memory, and health.
- Committing approved private fleet state when Git backup is enabled.
- Backing up and restoring non-Git state.
- Applying and verifying approved Telegram bot branding.
- Recording verified Telegram owner and dashboard access.

The root-owned helper must validate all identifiers, paths, images, mounts, ports, and resource limits. It must not accept arbitrary shell commands, controller-written Compose files, host paths outside Aidee directories, privileged containers, or Docker socket mounts.

The helper is not implemented yet. Do not grant the controller sudo or Docker group membership as a temporary substitute.

Future agent-to-agent communication may use a private MCP service. It is outside the first implementation.

Telegram profile tools run as the unprivileged controller. They read the bot token from the controller's private `.env` file without printing it. They require explicit approval flags before external changes or completion markers.
