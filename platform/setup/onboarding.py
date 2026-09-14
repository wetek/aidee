#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from onboarding_state import (
    OnboardingError,
    locked_status,
    onboarding_complete,
    validate_status_path,
)

def is_complete(status):
    return onboarding_complete(status)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("status_file", type=Path)
    arguments = parser.parse_args()

    try:
        validate_status_path(arguments.status_file, "controller")
        with locked_status(arguments.status_file, "controller") as status:
            complete = is_complete(status)
    except (OSError, OnboardingError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if not complete:
        return 1
    print("Controller onboarding is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
