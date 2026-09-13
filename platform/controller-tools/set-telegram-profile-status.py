#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path


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

    try:
        status = json.loads(arguments.status_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    current = status.get("telegram_profile_status")
    if current not in {"pending", "deferred"}:
        print(
            f"error: cannot change Telegram profile status from {current}",
            file=sys.stderr,
        )
        return 1

    status["telegram_profile_status"] = arguments.status
    temporary = arguments.status_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, indent=2) + "\n")
    os.chmod(temporary, 0o640)
    temporary.replace(arguments.status_file)
    print(f"Telegram profile setup marked as {arguments.status}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
