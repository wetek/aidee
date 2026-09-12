# Provisioning wizard

The wizard follows `docs/setup.md`. It collects owner experience, host, access, identity, project, repository, service, approval, resource, messaging, MCP, coding-agent, backup, and dashboard settings.

It must show a final plan before creating resources. It creates a loopback-bound protected dashboard before requesting secrets. Secrets are entered through masked terminal input or that dashboard, never through chat, messaging, or Git.

The generated assistant remains in `provisioning` status until its container, enabled messaging, dashboard, repositories, MCP tools, and coding agent pass validation.

The interview document does not replace implementation. Versioned scripts and the Aidee administration helper perform and validate changes.
