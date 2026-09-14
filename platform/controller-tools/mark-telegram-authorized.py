#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "setup"))
from onboarding_state import (  # noqa: E402
    OnboardingError,
    mark_step,
    validate_status_path,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--confirmed", action="store_true")
    arguments = parser.parse_args()

    if not arguments.confirmed:
        print("error: Telegram authorization confirmation is required", file=sys.stderr)
        return 1

    try:
        validate_status_path(arguments.status_file, "controller")
        mark_step(
            arguments.status_file,
            "controller",
            "owner_authorization",
            "completed",
            evidence_source="verified_tool",
            evidence_detail="authorized Telegram access verified",
        )
    except (OSError, OnboardingError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print("Telegram owner access marked as verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
