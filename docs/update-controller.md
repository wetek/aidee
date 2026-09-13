# Update an existing Aidee controller

These instructions are for an installed Aidee controller. Run them as the unprivileged controller account. Never use sudo.

## Rules

1. Read the latest release marker.
2. Detect the installed host release and current knowledge release.
3. Fetch the tagged release into the controller's private cache.
4. Run preview mode.
5. Summarize changes and compatibility concerns.
6. Ask the owner for approval.
7. Run apply mode only after approval.
8. Report whether root-owned host files still need an update.

Knowledge sync and host update are separate:

- Knowledge sync refreshes Aidee documentation and shared skills available to the controller.
- Host update changes root-owned scripts and services. The controller cannot perform it.

Do not claim that the host is updated after knowledge sync.

The controller may run this workflow from the owner-provided prompt or its daily update cron. A cron run may preview changes and ask for approval, but it must never apply the update itself.

## Find the latest release

Read:

`https://raw.githubusercontent.com/wetek/aidee/main/LATEST`

The response must be one version matching `v<major>.<minor>.<patch>-alpha.<number>`.

## Fetch and preview

Replace `RELEASE` with the exact value from `LATEST`:

~~~bash
release="RELEASE"
hermes_home="${HERMES_HOME:-$HOME/.hermes}"
source_dir="$hermes_home/aidee-sync-source/$release"
mkdir -p "$hermes_home/aidee-sync-source"
git clone \
  --branch "$release" \
  --depth 1 \
  https://github.com/wetek/aidee.git \
  "$source_dir"
"$source_dir/platform/scripts/sync-controller.sh" \
  --release "$release" \
  --preview
~~~

If the source directory already exists, verify its exact tag instead of deleting or replacing it.

Summarize:

- Installed host release.
- Current knowledge release.
- Available release.
- Setup or state migrations.
- Security changes.
- New or changed controller skills.
- Work that still requires root access.

Ask the owner to approve knowledge sync.

## Apply after approval

Run:

~~~bash
"$source_dir/platform/scripts/sync-controller.sh" \
  --release "$release" \
  --apply \
  --approved
~~~

Start a new Hermes session after syncing so skill discovery reloads.

If `~/.hermes/aidee-upstream/HOST_UPDATE_REQUIRED.md` exists, explain that the host remains on an older release. Do not invent an update command or request sudo access. Use the release's documented host update process when available.

## Host update

After a successful knowledge preview, the owner may separately approve a host update. The controller must not run it.

Give the owner this command for their SSH terminal:

~~~bash
sudo "SOURCE_DIR/platform/scripts/update-host.sh" \
  --release "RELEASE" \
  --owner-name "OWNER_NAME" \
  --approved
~~~

Replace `SOURCE_DIR`, `RELEASE`, and `OWNER_NAME` with the previewed values. The updater archives the previous source, activates the tagged release, installs the administration helper, copies the Fleet dashboard plugin, restarts the controller dashboard when Hermes is present, and builds and validates the shared assistant image.

## Report

Report:

- The release fetched.
- The release activated for controller knowledge.
- Skills refreshed.
- Whether the host release differs.
- Any blocked migration.
- The next owner action.
