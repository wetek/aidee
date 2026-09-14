#!/usr/bin/env python3
"""Mark an onboarding step with bounded, non-secret evidence."""

import argparse
import json
import os
import sys
from pathlib import Path

from onboarding_state import OnboardingError, mark_step, validate_status_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--role", required=True, choices=("controller", "assistant"))
    parser.add_argument("--assistant-kind")
    parser.add_argument("--step", required=True)
    parser.add_argument(
        "--status",
        required=True,
        choices=("pending", "in_progress", "completed", "skipped"),
    )
    parser.add_argument(
        "--evidence-source",
        choices=("owner_confirmation", "verified_tool", "reconciler"),
    )
    parser.add_argument("--evidence-detail")
    parser.add_argument("--reason")
    parser.add_argument("--note")
    parser.add_argument("--telegram-disabled", action="store_true")
    parser.add_argument("--menu-disabled", action="store_true")
    arguments = parser.parse_args()
    config = None
    if arguments.telegram_disabled or arguments.menu_disabled:
        config = {
            "telegram_enabled": not arguments.telegram_disabled,
            "dashboard_menu_enabled": not arguments.menu_disabled,
        }
    try:
        if arguments.evidence_source == "reconciler" and os.geteuid() != 0:
            raise OnboardingError("reconciler evidence requires trusted root authority")
        validate_status_path(arguments.status_file, arguments.role)
        rollup = mark_step(
            arguments.status_file,
            arguments.role,
            arguments.step,
            arguments.status,
            assistant_kind=arguments.assistant_kind,
            config=config,
            evidence_source=arguments.evidence_source,
            evidence_detail=arguments.evidence_detail,
            reason=arguments.reason,
            note=arguments.note,
        )
    except (OSError, OnboardingError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"step": arguments.step, "status": arguments.status, "rollup": rollup}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
