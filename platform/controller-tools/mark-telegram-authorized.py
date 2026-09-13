#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--confirmed", action="store_true")
    arguments = parser.parse_args()

    if not arguments.confirmed:
        print("error: Telegram authorization confirmation is required", file=sys.stderr)
        return 1

    try:
        status = json.loads(arguments.status_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    status["telegram_owner_authorized"] = True
    temporary = arguments.status_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, indent=2) + "\n")
    os.chmod(temporary, 0o640)
    temporary.replace(arguments.status_file)
    print("Telegram owner access marked as verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
