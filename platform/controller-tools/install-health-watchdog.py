#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


JOB_NAME = "Aidee fleet health watchdog"
SCHEDULE = "every 6h"
PROMPT = """Check the health and status of the Aidee controller and all provisioned fleet assistants.

Verify that:
1. The administration helper at /run/aidee/admin.sock is reachable.
2. All registered assistants in /var/lib/aidee/fleet/registry.yaml are running and healthy.
3. System resources (disk space and memory) are within safe operating limits.

If all services and assistants are healthy, respond with [SILENT].

If any assistant is stopped or unhealthy, or if errors/resource warnings are detected, summarize the issue clearly and alert the owner."""


def update_status(status_path):
    status = json.loads(status_path.read_text())
    status["health_watchdog_status"] = "active"
    temporary = status_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, indent=2) + "\n")
    os.chmod(temporary, 0o640)
    temporary.replace(status_path)


def run(command):
    return subprocess.run(command, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(
        description="Install Aidee fleet health watchdog cron job."
    )
    parser.add_argument("--status-file", type=Path, default=None)
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
                "--continuity",
            ]
        )
        if created.returncode != 0:
            print(created.stderr.strip(), file=sys.stderr)
            return created.returncode

    if arguments.status_file:
        try:
            update_status(arguments.status_file)
        except (FileNotFoundError, json.JSONDecodeError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    print("Fleet health watchdog is active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
