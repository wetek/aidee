# Security policy

Aidee controls long-running AI agents, credentials, project files, and server resources. Treat every installation as security-sensitive.

## Supported versions

Aidee has no supported release yet. The repository is being used for a private pilot. Do not use it with production or client credentials.

## Report a vulnerability

Do not open a public issue for a suspected vulnerability or leaked credential. Use the repository host's private vulnerability reporting feature after it is configured.

Until a private reporting channel is published, do not send sensitive details.

## Deployment rules

- Use a dedicated VPS.
- Keep the controller unprivileged.
- Grant administrative operations only through the installed root-owned helper.
- Do not expose Docker's socket to an assistant or controller.
- Bind dashboards and APIs to loopback unless an authenticated private access layer protects them.
- Enter secrets through masked terminal input or a protected local dashboard.
- Never paste secrets into chatbot conversations.
- Give each assistant separate state and credentials.
- Use MCP tool allowlists for sensitive services.
- Back up secrets separately from Git-safe configuration and memory.

## Secret response

If a credential enters Git, logs, terminal history, or chat:

1. Revoke or rotate it immediately.
2. Remove it from the affected system.
3. Inspect access logs where available.
4. Rewrite repository history before publication if Git contained it.
5. Record the cause without copying the credential.
