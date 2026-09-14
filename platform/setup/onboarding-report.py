#!/usr/bin/env python3
"""Print non-secret controller and fleet onboarding rollups."""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ASSISTANT_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
STATUS_RELATIVE = Path("aidee/onboarding-status.json")


def safe_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe onboarding status path: {relative}")
    target = root / path
    current = root
    if current.is_symlink():
        raise ValueError(f"unsafe onboarding state root: {root}")
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"unsafe onboarding status symlink: {current}")
    return target


def public_rollup(status):
    if not isinstance(status, dict):
        raise ValueError("onboarding status is invalid")
    rollup = status.get("rollup")
    if not isinstance(rollup, dict):
        raise ValueError("onboarding status has no rollup")
    required = rollup.get("incomplete_required")
    optional = rollup.get("incomplete_optional")
    if not isinstance(required, list) or not isinstance(optional, list):
        raise ValueError("onboarding rollup is invalid")
    state = rollup.get("status")
    complete = rollup.get("complete")
    if state not in {"pending", "in_progress", "complete"}:
        raise ValueError("onboarding rollup status is invalid")
    if not isinstance(complete, bool):
        raise ValueError("onboarding rollup completion is invalid")
    return {
        "status": state,
        "complete": complete,
        "required_remaining": len(required),
        "optional_remaining": len(optional),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, default=Path("/var/lib/aidee"))
    arguments = parser.parse_args()
    try:
        controller_path = (
            arguments.state_root
            / "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json"
        )
        safe_path(arguments.state_root, "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json")
        controller = json.loads(controller_path.read_text())
        registry = yaml.safe_load(
            (arguments.state_root / "fleet/registry.yaml").read_text()
        )
        if not isinstance(registry, dict) or not isinstance(
            registry.get("assistants"), list
        ):
            raise ValueError("fleet registry is invalid")
        assistants = []
        for assistant in registry["assistants"]:
            if not isinstance(assistant, dict):
                raise ValueError("fleet registry assistant is invalid")
            assistant_id = assistant["id"]
            if not isinstance(assistant_id, str) or not ASSISTANT_ID.fullmatch(
                assistant_id
            ):
                raise ValueError("fleet registry has an invalid assistant ID")
            onboarding = assistant.get("onboarding") or {}
            if not isinstance(onboarding, dict):
                raise ValueError("fleet registry onboarding entry is invalid")
            relative = onboarding.get("status_path", str(STATUS_RELATIVE))
            if relative != str(STATUS_RELATIVE):
                raise ValueError("fleet registry has an unsafe onboarding status path")
            runtime = arguments.state_root / f"runtime/assistants/{assistant_id}/data"
            status = json.loads(safe_path(runtime, relative).read_text())
            assistants.append(
                {
                    "id": assistant_id,
                    "status_path": relative,
                    "rollup": public_rollup(status),
                }
            )
        report = {
            "controller": {
                "status_path": str(controller_path),
                "rollup": public_rollup(controller),
            },
            "assistants": assistants,
        }
    except (KeyError, OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
