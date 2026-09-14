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
    parser.add_argument("--dashboard-url-file", required=True, type=Path)
    parser.add_argument("--confirmed", action="store_true")
    arguments = parser.parse_args()

    if not arguments.confirmed:
        print("error: owner confirmation is required; pass --confirmed", file=sys.stderr)
        return 1

    try:
        validate_status_path(arguments.status_file, "controller")
        dashboard_url = arguments.dashboard_url_file.read_text().strip()
        allowed_url = dashboard_url.startswith("https://") or (
            dashboard_url == "http://127.0.0.1:9119"
        )
        if not allowed_url:
            raise ValueError("dashboard URL is not an approved private address")
        mark_step(
            arguments.status_file,
            "controller",
            "dashboard_phone_access",
            "completed",
            evidence_source="owner_confirmation",
            evidence_detail="owner confirmed the private dashboard loaded on phone",
        )
    except (OSError, OnboardingError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print("Dashboard phone access marked as verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
