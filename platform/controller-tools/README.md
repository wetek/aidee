# Administration helper

The unprivileged Aidee controller will receive narrow tools for:

- Provisioning and validating assistants.
- Managing containers and platform versions.
- Managing optional dashboard routes.
- Checking storage, CPU, memory, and health.
- Committing approved private fleet state when Git backup is enabled.
- Backing up and restoring non-Git state.
- Applying and verifying approved Telegram bot branding.
- Recording the published HTTPS origin for an assistant dashboard.
- Recording verified Telegram owner and dashboard access.
- Creating the owner-approved daily Aidee update check and fleet health watchdog crons.
- Sending a Telegram notice with tap-to-send choice buttons when cron cannot use clarify.
- Drafting a pre-filled GitHub issue URL for owner-approved Aidee feedback.

The root-owned helper must validate all identifiers, paths, images, mounts, ports, and resource limits. It must not accept arbitrary shell commands, controller-written Compose files, host paths outside Aidee directories, privileged containers, or Docker socket mounts.

The helper runs as a root-owned system service and exposes a controller-only Unix socket. It accepts requests matching `assistant-request.schema.json`. Do not grant the controller sudo or Docker group membership as a substitute.

Future agent-to-agent communication may use a private MCP service. It is outside the first implementation.

Telegram profile tools run as the unprivileged controller. They read the bot token from the controller's private `.env` file without printing it. They require explicit approval flags before external changes or completion markers.
