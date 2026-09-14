#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "setup"))
from onboarding_state import (  # noqa: E402
    OnboardingError,
    mark_step,
    validate_status_path,
)


UPDATE_JOB_NAME = "Aidee daily update check"
UPDATE_SCHEDULE = "every 24h"
UPDATE_PROMPT = """Check for a newer tagged Aidee release.

Read https://raw.githubusercontent.com/wetek/aidee/main/LATEST.
Compare it with ~/.hermes/aidee-upstream/SYNCED_RELEASE and the installed
host release at /opt/aidee/source.

If no newer release exists and no host update is pending, respond with
[SILENT].

If a newer release exists, use the controller-update skill. Send one short
Telegram notice in this shape, then one clarify. Do not run sudo on this
first message.

✨ Aidee <tag> is ready

You're on <installed>.

What's new
• at most 3 short owner-facing bullets from the release notes

Preview first. Apply updates the host, controller, image, and assistants
and can take several minutes.

Then send one Telegram clarify whose only options are Start update
(recommended) and Not now. Do not include SSH commands in this notice.
Do not apply, use sudo, or modify root-owned files until the owner taps
Start update.

If the owner taps Start update in this continuity session, run preview
with sudo, summarize, then clarify Apply now or Cancel. If they tap Apply
now, run apply --approved and report the result."""

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
    detail = "health watchdog and daily update crons verified"
    if not update_check:
        detail = "health watchdog verified; owner disabled daily update checks"
    mark_step(
        status_path,
        "controller",
        "default_crons",
        "completed",
        evidence_source="reconciler",
        evidence_detail=detail,
    )


def run(command):
    return subprocess.run(command, capture_output=True, text=True)


def job_id(list_output, name):
    current_id = None
    for line in list_output.splitlines():
        clean = re.sub(r"\x1b\[[0-9;]*m", "", line)
        identifier = re.match(
            r"\s*([0-9a-f]{8,}(?:-[0-9a-f-]+)?)\s+\[", clean, re.I
        )
        if identifier:
            current_id = identifier.group(1)
        listed_name = re.match(r"\s*Name:\s*(.+?)\s*$", clean)
        if listed_name and listed_name.group(1) == name:
            return current_id
        if name in clean:
            inline_id = re.search(
                r"\b[0-9a-f]{8,}(?:-[0-9a-f-]+)?\b", clean, re.I
            )
            if inline_id:
                return inline_id.group(0)
    return None


def reconcile_job(hermes, existing_output, name, schedule, prompt, skill=None):
    existing_id = job_id(existing_output, name)
    if existing_id:
        command = [
            hermes,
            "cron",
            "edit",
            existing_id,
            "--schedule",
            schedule,
            "--prompt",
            prompt,
            "--name",
            name,
            "--deliver",
            "telegram",
            "--continuity",
        ]
        if skill:
            command.extend(["--skill", skill])
        return run(command)
    if name in existing_output:
        return subprocess.CompletedProcess(
            [],
            1,
            "",
            f"cannot identify existing cron job: {name}",
        )
    command = [
        hermes,
        "cron",
        "create",
        schedule,
        prompt,
        "--name",
        name,
        "--deliver",
        "telegram",
    ]
    if skill:
        command.extend(["--skill", skill])
    command.append("--continuity")
    return run(command)


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

    if not arguments.skip_update_check:
        created_update = reconcile_job(
            hermes,
            existing.stdout,
            UPDATE_JOB_NAME,
            UPDATE_SCHEDULE,
            UPDATE_PROMPT,
            "controller-update",
        )
        if created_update.returncode != 0:
            print(created_update.stderr.strip(), file=sys.stderr)
            return created_update.returncode

    created_watchdog = reconcile_job(
        hermes,
        existing.stdout,
        WATCHDOG_JOB_NAME,
        WATCHDOG_SCHEDULE,
        WATCHDOG_PROMPT,
    )
    if created_watchdog.returncode != 0:
        print(created_watchdog.stderr.strip(), file=sys.stderr)
        return created_watchdog.returncode

    if arguments.status_file:
        try:
            validate_status_path(arguments.status_file, "controller")
            verified = run([hermes, "cron", "list", "--all"])
            expected = [WATCHDOG_JOB_NAME]
            if not arguments.skip_update_check:
                expected.append(UPDATE_JOB_NAME)
            if verified.returncode != 0 or any(
                name not in verified.stdout for name in expected
            ):
                raise OnboardingError(
                    "default cron jobs could not be verified after reconciliation"
                )
            update_status(
                arguments.status_file,
                update_check=not arguments.skip_update_check,
            )
        except (OSError, OnboardingError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    print("Default Aidee cron jobs are active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
