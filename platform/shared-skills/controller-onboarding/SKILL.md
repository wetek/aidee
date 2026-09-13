---
name: controller-onboarding
description: Completes the Aidee controller's first-run Telegram branding and dashboard verification. Use before any project or assistant work when CONTROLLER_ONBOARDING.md exists and onboarding is incomplete.
---

# Controller onboarding

Offer this workflow in the first authorized conversation. The owner may complete Telegram branding now, defer it, or keep the current profile.

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

## Create the daily update check

If `SETUP_SUMMARY.md` enables daily update checks:

1. Ask the owner to send `/sethome` in this Telegram chat.
2. Wait for confirmation that it is the home channel.
3. Run:

~~~bash
/opt/aidee/source/platform/controller-tools/install-update-cron.py \
  --status-file /var/lib/aidee/fleet/controller/CONTROLLER_ONBOARDING_STATUS.json \
  --approved
~~~

The cron runs every 24 hours. It stays silent when no update exists. When it finds a newer release, it previews the changes and asks the owner before applying knowledge sync. It never updates from cron.

## Offer Telegram branding

Ask:

1. Set up the bot profile now (recommended).
2. Remind me later.
3. Keep the current profile.

If the owner chooses later, run:

~~~bash
/opt/aidee/source/platform/controller-tools/set-telegram-profile-status.py \
  --status-file /var/lib/aidee/fleet/controller/CONTROLLER_ONBOARDING_STATUS.json \
  --status deferred \
  --confirmed
~~~

If the owner keeps the current profile, run:

~~~bash
/opt/aidee/source/platform/controller-tools/set-telegram-profile-status.py \
  --status-file /var/lib/aidee/fleet/controller/CONTROLLER_ONBOARDING_STATUS.json \
  --status skipped \
  --confirmed
~~~

For either choice, skip profile drafting and continue to phone access verification.

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
