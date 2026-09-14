#!/usr/bin/env python3
"""Inspect or atomically decide whether to offer resumable onboarding."""

import argparse
import json
import sys
from pathlib import Path

from onboarding_state import OnboardingError, gate, validate_status_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--role", required=True, choices=("controller", "assistant"))
    parser.add_argument("--assistant-kind")
    parser.add_argument(
        "--mode",
        required=True,
        choices=("inspect", "decide", "resume-now", "not-now", "reopen"),
    )
    parser.add_argument("--telegram-disabled", action="store_true")
    parser.add_argument("--menu-disabled", action="store_true")
    arguments = parser.parse_args()
    action = arguments.mode.replace("-", "_")
    config = None
    if arguments.telegram_disabled or arguments.menu_disabled:
        config = {
            "telegram_enabled": not arguments.telegram_disabled,
            "dashboard_menu_enabled": not arguments.menu_disabled,
        }
    try:
        validate_status_path(arguments.status_file, arguments.role)
        result = gate(
            arguments.status_file,
            arguments.role,
            arguments.assistant_kind,
            config,
            action,
        )
    except (OSError, OnboardingError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
