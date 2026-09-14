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

If controller dashboard credentials were inherited, inform the owner they can sign in to the assistant dashboard using their existing controller credentials. Otherwise, direct them to open the controller dashboard Fleet page to reveal the initial password. Never send passwords or SSH commands in chat.

The owner creates third-party credentials and enters them through the assistant dashboard. Never request dashboard passwords or service tokens in Telegram.

For Telegram and Bot Identity:

1. Ask the owner to create a separate bot through BotFather.
2. Ask them to enter the token in the assistant dashboard.
3. Use DM pairing for owner access.
4. Configure the Telegram Chat Menu Button (`setChatMenuButton`) pointing to
   `dashboard.public_url` in the assistant `config.yaml`. That URL is Tailscale
   by default, or a custom HTTPS origin if the owner recorded one. Never invent
   a Tailscale host. Set descriptions for the default profile and
   `language_code=en`. Do not put dashboard URLs in bio text.
5. Respect Telegram platform limits: custom-port URLs (e.g. `:8444`) do not linkify in iOS bios; rely on the fixed Chat Menu Button and native Mini App card instead of raw URLs in bio text.
6. When repositories are connected, inspect brand assets (`public/brand/*`) and proactively offer to set the Telegram bot profile photo.
7. Test one harmless response.

## Repository Access

Default to least-privilege repository access:

1. Clone and store every coding-task repository under `/opt/data/aidee/repos`.
2. Avoid account-wide OAuth device authorization (`gh auth login`).
3. Proactively generate and provide a dedicated SSH Deploy Key (write-enabled) scoped strictly to the target repository.
4. Or request a fine-grained Personal Access Token (PAT) scoped exclusively to the specific repository with minimal permissions.

## Validate

Request `status_assistant` through the administration helper. Confirm:

- Main and dashboard proxy containers are running.
- The recorded image ID matches the approved shared image.
- The dashboard opens through Tailscale.
- The assistant responds through enabled messaging.
- No other assistant state is visible.

Keep the assistant in provisioning status until all enabled checks pass.
