#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--dashboard-url-file", required=True, type=Path)
    parser.add_argument("--confirmed", action="store_true")
    arguments = parser.parse_args()

    if not arguments.confirmed:
        print("error: owner confirmation is required; pass --confirmed", file=sys.stderr)
        return 1

    try:
        dashboard_url = arguments.dashboard_url_file.read_text().strip()
        allowed_url = dashboard_url.startswith("https://") or (
            dashboard_url == "http://127.0.0.1:9119"
        )
        if not allowed_url:
            raise ValueError("dashboard URL is not an approved private address")
        status = json.loads(arguments.status_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    status["dashboard_verified"] = True
    temporary = arguments.status_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, indent=2) + "\n")
    os.chmod(temporary, 0o640)
    temporary.replace(arguments.status_file)
    print("Dashboard phone access marked as verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
