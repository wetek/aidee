---
name: controller-dashboard-origin
description: Records the published HTTPS origin for one assistant dashboard. Use when the owner wants Tailscale or a custom domain on that assistant's dashboard, Telegram menu, and Hermes Host header.
---

# Set a dashboard origin

Keep each response under 120 words unless an error needs more detail.

Tailscale Serve is the default published origin. A custom HTTPS hostname is
optional and per dashboard. Do not apply one owner's domain to every
assistant. Do not invent a Tailscale URL when `dashboard.public_url` is
already a custom origin.

## Interview

Ask one question at a time:

1. Which assistant.
2. The exact `https://` origin they want. No path, query, or secrets.

If they want Tailscale, use the existing `registry.yaml` Tailscale URL for
that assistant, including the port when Serve uses one.

## Request

After approval, write a request matching
`/opt/aidee/source/platform/schemas/assistant-request.schema.json` for
`set_dashboard_origin`. Store it under
`/var/lib/aidee/fleet/controller/requests/<request-id>.json`.

Call:

~~~bash
/opt/aidee/source/platform/controller-tools/aidee-admin-client.py \
  /var/lib/aidee/fleet/controller/requests/<request-id>.json
~~~

The helper writes `registry.yaml` `dashboard.url` and that assistant's
`config.yaml` `dashboard.public_url`. It does not call Telegram.

## After the helper

Tell the owner to message that assistant:

`Set the Telegram menu button to dashboard.public_url from config.yaml for
the default chat and this chat. Set descriptions for the default profile and
language_code en. Do not put dashboard URLs in bio or description.`

Report the origin from the helper. Never print tokens.
