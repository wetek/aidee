# Update an existing Aidee controller

These instructions are for an existing Aidee VPS. Alpha 13 adds one owner-facing
preview and apply command for the host, controller, and every registered
assistant. Run it from the owner's SSH terminal with sudo.

## Rules

1. Read `https://raw.githubusercontent.com/wetek/aidee/main/LATEST`.
2. Require a version matching `v<major>.<minor>.<patch>-alpha.<number>`.
3. Run the root-owned preview from the owner's SSH terminal.
4. Review the release notes and listed actions.
5. Run apply only after explicit owner approval.
6. Verify the host, controller, crons, image, containers, and assistant state.
7. Never apply from a scheduled run or Hermes interaction.

## Find the latest release

`https://raw.githubusercontent.com/wetek/aidee/main/LATEST`

## Host update

### One-time bootstrap from Alpha 12 or older

Older releases do not contain the fleet updater. Fetch the exact Alpha 13 tag
and preview it:

~~~bash
sudo install -d -m 0755 /opt/aidee/releases
sudo git clone --branch v0.1.0-alpha.13 --depth 1 \
  https://github.com/wetek/aidee.git \
  /opt/aidee/releases/v0.1.0-alpha.13
sudo /opt/aidee/releases/v0.1.0-alpha.13/platform/scripts/update-host.sh \
  --release v0.1.0-alpha.13 --preview
~~~

After reviewing the preview and explicitly approving it, run:

~~~bash
sudo /opt/aidee/releases/v0.1.0-alpha.13/platform/scripts/update-host.sh \
  --release v0.1.0-alpha.13 --apply --approved
~~~

### Future updates

Use the permanently installed command with the exact tag from `LATEST`:

~~~bash
sudo /opt/aidee/source/platform/scripts/update-host.sh \
  --release RELEASE --preview
~~~

After reviewing and approving the preview:

~~~bash
sudo /opt/aidee/source/platform/scripts/update-host.sh \
  --release RELEASE --apply --approved
~~~

Preview may fetch the release tag, but it does not change active state. Apply
refreshes root-owned services, controller knowledge and Hermes, controller-only
default crons, the validated assistant image, and all registered assistants.
It preserves bind-mounted runtime data and rolls back failed container
replacement.

## Report

Report:

- The activated host release and controller knowledge release.
- The controller Hermes version and central cron jobs.
- The validated image ID and each assistant container image.
- Repaired directories, instructions, configuration, skills, and onboarding status.
- Any rollback, failed check, or incomplete external onboarding step.
