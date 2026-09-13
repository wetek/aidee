#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


JOB_NAME = "Aidee daily update check"
SCHEDULE = "every 24h"
PROMPT = """Check for a newer tagged Aidee release.

Read https://raw.githubusercontent.com/wetek/aidee/main/LATEST.
Compare it with ~/.hermes/aidee-upstream/SYNCED_RELEASE and the installed
host release at /opt/aidee/source.

If no newer release exists and no host update is pending, respond with
[SILENT].

If a newer release exists, use the controller-update skill to fetch and
preview it. Summarize the release notes, migrations, security changes, and
host update requirements. Ask the owner whether to sync. Do not apply the
update, use sudo, or modify root-owned files during this cron run."""


def update_status(status_path):
    status = json.loads(status_path.read_text())
    status["update_check_status"] = "active"
    temporary = status_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, indent=2) + "\n")
    os.chmod(temporary, 0o640)
    temporary.replace(status_path)


def run(command):
    return subprocess.run(command, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--approved", action="store_true")
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

    if JOB_NAME not in existing.stdout:
        created = run(
            [
                hermes,
                "cron",
                "create",
                SCHEDULE,
                PROMPT,
                "--name",
                JOB_NAME,
                "--deliver",
                "telegram",
                "--skill",
                "controller-update",
                "--continuity",
            ]
        )
        if created.returncode != 0:
            print(created.stderr.strip(), file=sys.stderr)
            return created.returncode

    try:
        update_status(arguments.status_file)
    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print("Daily Aidee update check is active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
