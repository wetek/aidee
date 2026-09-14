#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "setup"))
from onboarding_state import (  # noqa: E402
    OnboardingError,
    locked_status,
    mark_step,
    validate_status_path,
)


ALLOWED_STATUS = {"deferred", "skipped"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--status", required=True, choices=sorted(ALLOWED_STATUS))
    parser.add_argument("--confirmed", action="store_true")
    arguments = parser.parse_args()

    if not arguments.confirmed:
        print("error: owner confirmation is required", file=sys.stderr)
        return 1

    target = "pending" if arguments.status == "deferred" else "skipped"
    try:
        validate_status_path(arguments.status_file, "controller")
        with locked_status(arguments.status_file, "controller") as state:
            menu_applicable = state["steps"]["telegram_menu_button"]["applicable"]
        step_ids = ["telegram_profile_avatar"]
        if menu_applicable:
            step_ids.append("telegram_menu_button")
        for step_id in step_ids:
            mark_step(
                arguments.status_file,
                "controller",
                step_id,
                target,
                evidence_source=(
                    "owner_confirmation" if target == "skipped" else None
                ),
                evidence_detail=(
                    "owner chose to keep the current Telegram profile setup"
                    if target == "skipped"
                    else None
                ),
                reason=(
                    "Owner chose to keep the current Telegram profile setup"
                    if target == "skipped"
                    else None
                ),
                allowed_from=(
                    {"pending", "in_progress", "skipped"}
                    if target == "skipped"
                    else {"pending", "in_progress"}
                ),
            )
    except (OSError, OnboardingError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Telegram profile setup marked as {arguments.status}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
