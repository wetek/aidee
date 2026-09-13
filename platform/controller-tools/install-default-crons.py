#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


UPDATE_JOB_NAME = "Aidee daily update check"
UPDATE_SCHEDULE = "every 24h"
UPDATE_PROMPT = """Check for a newer tagged Aidee release.

Read https://raw.githubusercontent.com/wetek/aidee/main/LATEST.
Compare it with ~/.hermes/aidee-upstream/SYNCED_RELEASE and the installed
host release at /opt/aidee/source.

If no newer release exists and no host update is pending, respond with
[SILENT].

If a newer release exists, use the controller-update skill to fetch and
preview it. Summarize the release notes, migrations, security changes, and
host update requirements. Ask the owner whether to sync. Do not apply the
update, use sudo, or modify root-owned files during this cron run."""

WATCHDOG_JOB_NAME = "Aidee fleet health watchdog"
WATCHDOG_SCHEDULE = "every 6h"
WATCHDOG_PROMPT = """Check the health and status of the Aidee controller and all provisioned fleet assistants.

Verify that:
1. The administration helper at /run/aidee/admin.sock is reachable.
2. All registered assistants in /var/lib/aidee/fleet/registry.yaml are running and healthy.
3. System resources (disk space and memory) are within safe operating limits.

If all services and assistants are healthy, respond with [SILENT].

If any assistant is stopped or unhealthy, or if errors/resource warnings are detected, summarize the issue clearly and alert the owner."""


def update_status(status_path, update_check=True):
    status = json.loads(status_path.read_text())
    if update_check:
        status["update_check_status"] = "active"
    status["health_watchdog_status"] = "active"
    temporary = status_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, indent=2) + "\n")
    os.chmod(temporary, 0o640)
    temporary.replace(status_path)


def run(command):
    return subprocess.run(command, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(
        description="Install default Aidee cron jobs."
    )
    parser.add_argument("--status-file", type=Path, default=None)
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--skip-update-check", action="store_true")
    arguments = parser.parse_args()

    if os.geteuid() == 0:
        print("error: run as the unprivileged controller", file=sys.stderr)
        return 1
    if not arguments.approved:
        print("error: owner approval is required; pass --approved", file=sys.stderr)
        return 1

    hermes = shutil.which("hermes")
    if hermes is None:
        print("error: hermes command not found", file=sys.stderr)
        return 1

    existing = run([hermes, "cron", "list", "--all"])
    if existing.returncode != 0:
        print(existing.stderr.strip(), file=sys.stderr)
        return existing.returncode

    if not arguments.skip_update_check and UPDATE_JOB_NAME not in existing.stdout:
        created_update = run(
            [
                hermes,
                "cron",
                "create",
                UPDATE_SCHEDULE,
                UPDATE_PROMPT,
                "--name",
                UPDATE_JOB_NAME,
                "--deliver",
                "telegram",
                "--skill",
                "controller-update",
                "--continuity",
            ]
        )
        if created_update.returncode != 0:
            print(created_update.stderr.strip(), file=sys.stderr)
            return created_update.returncode

    if WATCHDOG_JOB_NAME not in existing.stdout:
        created_watchdog = run(
            [
                hermes,
                "cron",
                "create",
                WATCHDOG_SCHEDULE,
                WATCHDOG_PROMPT,
                "--name",
                WATCHDOG_JOB_NAME,
                "--deliver",
                "telegram",
                "--continuity",
            ]
        )
        if created_watchdog.returncode != 0:
            print(created_watchdog.stderr.strip(), file=sys.stderr)
            return created_watchdog.returncode

    if arguments.status_file:
        try:
            update_status(
                arguments.status_file,
                update_check=not arguments.skip_update_check,
            )
        except (FileNotFoundError, json.JSONDecodeError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    print("Default Aidee cron jobs are active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
