# Provisioning wizard

The chatbot interview follows `docs/setup.md`. It collects owner experience, host, access, identity, project, repository, service, approval, resource, messaging, MCP, coding-agent, backup, and dashboard settings.

After approval, the chatbot writes the non-secret answers as a setup plan that matches `platform/schemas/setup-plan.schema.json`. The owner pastes one bootstrap block. `setup.sh` validates the plan and handles host and controller setup.

The setup program creates a loopback-bound dashboard before requesting secrets. The owner enters secrets through that dashboard, never through chat, messaging, the setup plan, or Git.

The generated assistant remains in `provisioning` status until its container, enabled messaging, dashboard, repositories, MCP tools, and coding agent pass validation.

The chatbot does not narrate individual host commands. Versioned scripts perform and validate changes, persist progress, and return one next action when setup pauses.
