# Update an existing Aidee controller

These instructions are for an existing Aidee VPS. When a newer tag exists,
the controller sends a Telegram notice and offers Start update. After the
owner sends Start update, then Apply now, the controller runs the fleet
updater with sudo.

SSH remains a fallback when Telegram buttons are unavailable. Apply can take
several minutes because it rebuilds the assistant image.

## Rules

1. Read `https://raw.githubusercontent.com/wetek/aidee/main/LATEST`.
2. Require a version matching `v<major>.<minor>.<patch>-alpha.<number>`.
3. The first Telegram notice is discovery only. Do not use sudo yet.
4. Offer `Start update` and `Not now` as Telegram buttons. Cron runs
   cannot use clarify, so they send those buttons with
   `send-telegram-choices.py`. Interactive chats use clarify.
5. After `Start update`, run preview with sudo and summarize the plan.
6. After `Apply now`, run apply with `--approved`.
7. Never apply from an unanswered cron run.
8. Verify the host, controller, crons, image, containers, and assistant state.

## Find the latest release

`https://raw.githubusercontent.com/wetek/aidee/main/LATEST`

## Telegram update

Use this notice shape:

~~~text
✨ Aidee RELEASE is ready

You're on INSTALLED.

What's new
• at most 3 short owner-facing bullets

Preview first. Apply updates the host, controller, image, and assistants
and can take several minutes.
~~~

Then offer `Start update` or `Not now` as Telegram buttons. Do not write
those labels as numbered text. Cron runs pipe the notice to
`send-telegram-choices.py`. Interactive chats use the clarify tool.

After `Start update`, run preview. After `Apply now`, run apply. Replace
`RELEASE` with the exact tag from `LATEST`:

~~~bash
sudo /opt/aidee/source/platform/scripts/update-host.sh \
  --release RELEASE --preview
~~~

~~~bash
sudo /opt/aidee/source/platform/scripts/update-host.sh \
  --release RELEASE --apply --approved
~~~

Preview may fetch the release tag, but it does not change active state. Apply
prints numbered steps and streams the long image build and Hermes update so
the session stays active. It refreshes root-owned services, controller
knowledge and Hermes, controller-only default crons, the validated assistant
image, and all registered assistants.
It preserves bind-mounted runtime data and rolls back failed container
replacement. Existing Hermes sessions keep their message history. On the next
turn after a managed SOUL or tool-context change, Hermes rebuilds and persists
the effective system prompt and tool list.

## SSH fallback

Use these commands from the owner's SSH terminal only when Telegram buttons
are unavailable.

### One-time bootstrap from Alpha 12 or older

Older releases do not contain the fleet updater. Read `LATEST`, fetch that
exact tag, and preview it. Replace `RELEASE` with the tag from `LATEST`:

~~~bash
sudo install -d -m 0755 /opt/aidee/releases
sudo git clone --branch RELEASE --depth 1 \
  https://github.com/wetek/aidee.git \
  /opt/aidee/releases/RELEASE
sudo /opt/aidee/releases/RELEASE/platform/scripts/update-host.sh \
  --release RELEASE --preview
~~~

After reviewing the preview and explicitly approving it, run:

~~~bash
sudo /opt/aidee/releases/RELEASE/platform/scripts/update-host.sh \
  --release RELEASE --apply --approved
~~~

### Later SSH updates

~~~bash
sudo /opt/aidee/source/platform/scripts/update-host.sh \
  --release RELEASE --preview
~~~

After reviewing and approving the preview:

~~~bash
sudo /opt/aidee/source/platform/scripts/update-host.sh \
  --release RELEASE --apply --approved
~~~

## Report

Inspect the controller's durable decision and incomplete steps:

~~~bash
sudo /opt/aidee/source/platform/setup/onboarding-gate.py \
  --status-file /var/lib/aidee/fleet/controller/CONTROLLER_ONBOARDING_STATUS.json \
  --role controller --mode inspect
~~~

Inspect one assistant from the host. Replace `control-tower` and `coding` as needed:

~~~bash
sudo python3 /opt/aidee/source/platform/setup/onboarding-gate.py \
  --status-file /var/lib/aidee/runtime/assistants/control-tower/data/aidee/onboarding-status.json \
  --role assistant --assistant-kind coding --mode inspect
~~~

The same file is `/opt/data/aidee/onboarding-status.json` inside the assistant container.

Inspect controller and fleet rollups with one report:

~~~bash
sudo /opt/aidee/source/platform/setup/onboarding-report.py
~~~

The update report must include:

- The activated host release and controller knowledge release.
- The controller Hermes version and central cron jobs.
- The validated image ID and each assistant container image.
- Repaired directories, instructions, configuration, skills, and onboarding status.
- Any rollback, failed check, or incomplete external onboarding step.
