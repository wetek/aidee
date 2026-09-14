#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "setup"))
from onboarding_state import (  # noqa: E402
    OnboardingError,
    locked_status,
    mark_step,
    validate_status_path,
)

JOB_NAME = "Aidee daily update check"
SCHEDULE = "every 24h"
PROMPT = """Check for a newer tagged Aidee release.

Read https://raw.githubusercontent.com/wetek/aidee/main/LATEST.
Compare it with ~/.hermes/aidee-upstream/SYNCED_RELEASE and the installed
host release at /opt/aidee/source.

If no newer release exists and no host update is pending, respond with
[SILENT].

If a newer release exists, use the controller-update skill. Compose one
short notice in this shape. Do not run sudo on this first message.

✨ Aidee <tag> is ready

You're on <installed>.

What's new
• at most 3 short owner-facing bullets from the release notes

Preview first. Apply updates the host, controller, image, and assistants
and can take several minutes.

Cron runs cannot use the Telegram clarify tool. Never write Options or
numbered choices in the notice. Pipe the notice to
/opt/aidee/source/platform/controller-tools/send-telegram-choices.py
with --choice "Start update" and --choice "Not now", then respond with
[SILENT]. Do not include SSH commands. Do not apply, use sudo, or modify
root-owned files until the owner sends Start update.

If the owner sends Start update in this chat, run preview with sudo,
summarize, then use the Telegram clarify tool for Apply now or Cancel.
If they send Apply now, run apply --approved and report the result."""


def update_status(status_path, all_default_crons_verified):
    with locked_status(status_path, "controller"):
        pass
    if all_default_crons_verified:
        mark_step(
            status_path,
            "controller",
            "default_crons",
            "completed",
            evidence_source="reconciler",
            evidence_detail="health watchdog and daily update crons verified",
        )


def run(command):
    return subprocess.run(command, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", required=False, default=None, type=Path)
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

    if arguments.status_file:
        try:
            validate_status_path(arguments.status_file, "controller")
            verified = run([hermes, "cron", "list", "--all"])
            update_status(
                arguments.status_file,
                verified.returncode == 0
                and JOB_NAME in verified.stdout
                and "Aidee fleet health watchdog" in verified.stdout,
            )
        except (OSError, OnboardingError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    print("Daily Aidee update check is active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
