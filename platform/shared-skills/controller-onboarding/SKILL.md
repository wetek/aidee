---
name: controller-onboarding
description: Completes the Aidee controller's first-run Telegram branding and dashboard verification. Use before any project or assistant work when CONTROLLER_ONBOARDING.md exists and onboarding is incomplete.
---

# Controller onboarding

Complete this workflow before project or assistant work.

## Read the approved state

Read:

- `/var/lib/aidee/fleet/controller/CONTROLLER_ONBOARDING.md`
- `/var/lib/aidee/fleet/controller/SETUP_SUMMARY.md`
- `/var/lib/aidee/fleet/controller/DASHBOARD_URL`
- `/var/lib/aidee/fleet/controller/CONTROLLER_ONBOARDING_STATUS.json`

Stop if the files disagree or contain unresolved placeholders.

## Authorize the owner

Use the access method in `CONTROLLER_ONBOARDING.md`.

For pairing:

1. Ask the owner to message the bot.
2. Direct them to approve the pending code through the protected dashboard's Pairing page.
3. Ask them to send `/whoami` in Telegram.
4. Confirm that Hermes reports authorized access.

For an allowlist, confirm that the owner's numeric ID is present. Do not use `*`.

After verification, run:

~~~bash
/opt/aidee/source/platform/controller-tools/mark-telegram-authorized.py \
  --status-file /var/lib/aidee/fleet/controller/CONTROLLER_ONBOARDING_STATUS.json \
  --confirmed
~~~

## Draft the bot profile

Draft:

- Name, at most 64 characters.
- Short description, at most 120 characters.
- Full description, at most 512 characters.
- Commands supported by the installed Hermes release.
- A menu button named `Open dashboard` when enabled.
- A static JPG avatar.

Do not invent commands. Inspect the installed Hermes messaging documentation or existing command registry.

## Prepare the avatar

Check whether an image-generation tool is available.

If available:

1. Ask the owner for a visual style.
2. Generate up to three square options.
3. Show them to the owner.
4. Save the approved option as a JPG.

If unavailable, ask the owner to upload a square JPG through the protected dashboard.

Store the selected file under the controller's Hermes home. Do not store image-generation credentials in the profile.

## Request approval

Show the proposed name, descriptions, commands, menu button, and avatar. Wait for explicit approval before changing Telegram.

Write the approved profile to:

`/var/lib/aidee/fleet/controller/TELEGRAM_PROFILE.json`

Match `platform/schemas/telegram-profile.schema.json`.

Validate it:

~~~bash
/opt/aidee/source/platform/controller-tools/update-telegram-profile.py \
  --profile /var/lib/aidee/fleet/controller/TELEGRAM_PROFILE.json \
  --avatar-root /var/lib/aidee/controller-home/.hermes/onboarding \
  --check
~~~

## Apply and verify

After approval, run:

~~~bash
/opt/aidee/source/platform/controller-tools/update-telegram-profile.py \
  --profile /var/lib/aidee/fleet/controller/TELEGRAM_PROFILE.json \
  --avatar-root /var/lib/aidee/controller-home/.hermes/onboarding \
  --env-file /var/lib/aidee/controller-home/.hermes/.env \
  --status-file /var/lib/aidee/fleet/controller/CONTROLLER_ONBOARDING_STATUS.json \
  --approved
~~~

The tool applies and reads back the name, descriptions, commands, avatar, and menu button. Stop if verification fails.

## Verify phone access

Ask the owner to open the Telegram menu button from their phone. For a Tailscale URL, remind them that Tailscale must be connected.

After the owner confirms that the dashboard loaded, run:

~~~bash
/opt/aidee/source/platform/controller-tools/mark-dashboard-verified.py \
  --status-file /var/lib/aidee/fleet/controller/CONTROLLER_ONBOARDING_STATUS.json \
  --dashboard-url-file /var/lib/aidee/fleet/controller/DASHBOARD_URL \
  --confirmed
~~~

Report the verified bot fields and dashboard URL. Then ask the owner to rerun `sudo ./setup.sh` so Aidee can mark controller setup complete.
