#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


COMPLETE_PROFILE_STATUS = {"applied", "deferred", "skipped"}


def is_complete(status):
    return (
        status.get("telegram_owner_authorized") is True
        and status.get("telegram_profile_status") in COMPLETE_PROFILE_STATUS
        and status.get("update_check_status") in {"active", "disabled"}
        and status.get("dashboard_verified") is True
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("status_file", type=Path)
    arguments = parser.parse_args()

    try:
        status = json.loads(arguments.status_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if not is_complete(status):
        return 1
    print("Controller onboarding is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
