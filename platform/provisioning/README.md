# Provisioning wizard

The chatbot interview follows `docs/setup.md`. It collects owner experience, host, access, identity, project, repository, service, approval, resource, messaging, MCP, coding-agent, backup, and dashboard settings.

After approval, the chatbot writes the non-secret answers as a setup plan that matches `platform/schemas/setup-plan.schema.json`. The owner pastes one bootstrap block. `setup.sh` validates the plan and handles host and controller setup.

The setup program creates a loopback-bound dashboard before requesting secrets. The owner enters secrets through that dashboard, never through chat, messaging, the setup plan, or Git.

The generated assistant remains in `provisioning` status until its container, enabled messaging, dashboard, repositories, MCP tools, and coding agent pass validation.

The chatbot does not narrate individual host commands. Versioned scripts perform and validate changes, persist progress, and return one next action when setup pauses.

## Assistant creation

The controller uses the `provision-assistant` skill in Telegram:

1. Ask one question at a time.
2. Select unused dashboard ports from the fleet registry.
3. Show the complete assistant plan.
4. Wait for owner approval.
5. Write a request matching `assistant-request.schema.json`.
6. Send it through `aidee-admin-client.py`.
7. Return the private dashboard URL.
8. Guide credential entry through that dashboard.
9. Validate the container, messaging, and isolation.

The controller requests an assistant ID and Aidee version. It cannot provide Docker flags, image names, host paths, environment files, or Compose configuration.

One shared image is built and validated during host setup. Creating another assistant must reuse the approved image ID without rebuilding.
