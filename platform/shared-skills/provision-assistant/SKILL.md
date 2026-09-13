---
name: provision-assistant
description: Creates and validates one isolated Aidee assistant through the narrow administration helper. Use when the owner asks to create, add, start, stop, or inspect an assistant.
---

# Provision an assistant

Keep each response under 120 words unless safety or an error needs more detail.

## Interview

Ask one question at a time:

1. Assistant name and purpose.
2. Personal, coding, client, or project scope.
3. Model provider.
4. Whether it needs a separate Telegram bot.
5. Repositories and services.
6. Actions that require approval.
7. CPU and memory limits.

Choose dashboard ports from unused values in the fleet registry. Do not ask the owner to choose ports.

For an 8 GB pilot host, recommend 0.75 CPU, 2048 MB memory, and 512 processes. This permits two light assistants while reserving resources for the controller. Check host capacity before recommending more.

## Plan

Show:

- Identity and purpose.
- Shared image version and image ID.
- Resource limits.
- Mounted state paths.
- Dashboard URL plan.
- Messaging and model setup.
- Repository access.
- Approval rules.

Wait for explicit approval.

## Request

Write a request matching:

`/opt/aidee/source/platform/schemas/assistant-request.schema.json`

Store it under:

`/var/lib/aidee/fleet/controller/requests/<request-id>.json`

Set `owner_approved` to `true` only after approval.

Call:

~~~bash
/opt/aidee/source/platform/controller-tools/aidee-admin-client.py \
  /var/lib/aidee/fleet/controller/requests/<request-id>.json
~~~

Do not send Docker flags, host paths, image names, environment files, or shell commands. The helper chooses them from the approved release.

## Configure

Return the private dashboard URL from the helper response.

The helper also returns a dashboard username and an SSH command for retrieving the initial password. Send the command, not the password. The owner runs it in SSH and enters the result directly into the dashboard.

The owner creates third-party credentials and enters them through the assistant dashboard. Never request dashboard passwords or service tokens in Telegram.

For Telegram:

1. Ask the owner to create a separate bot through BotFather.
2. Ask them to enter the token in the assistant dashboard.
3. Use DM pairing for owner access.
4. Test one harmless response.

## Validate

Request `status_assistant` through the administration helper. Confirm:

- Main and dashboard proxy containers are running.
- The recorded image ID matches the approved shared image.
- The dashboard opens through Tailscale.
- The assistant responds through enabled messaging.
- No other assistant state is visible.

Keep the assistant in provisioning status until all enabled checks pass.
