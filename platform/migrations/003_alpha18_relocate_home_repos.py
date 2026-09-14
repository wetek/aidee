#!/usr/bin/env python3
"""Move leftover Hermes-home git checkouts under aidee/repos."""

import json
import os
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))
from assistant_state import relocate_legacy_home_repos

ASSISTANT_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def apply(state_root: Path, backup_root: Path):
    registry_path = state_root / "fleet/registry.yaml"
    if not registry_path.is_file():
        return
    if registry_path.is_symlink() or not registry_path.is_file():
        raise RuntimeError("fleet registry must be a regular file")
    try:
        registry = yaml.safe_load(registry_path.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise RuntimeError("fleet registry is invalid") from error
    assistants = registry.get("assistants") if isinstance(registry, dict) else None
    if not isinstance(assistants, list):
        raise RuntimeError("fleet registry assistants is not a list")

    backup_root.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_root, 0o700)
    moves = []
    for assistant in assistants:
        assistant_id = assistant.get("id") if isinstance(assistant, dict) else None
        if not isinstance(assistant_id, str) or not ASSISTANT_ID.fullmatch(
            assistant_id
        ):
            raise RuntimeError("fleet registry has an invalid assistant ID")
        runtime_dir = (
            state_root / f"runtime/assistants/{assistant_id}/data"
        )
        if runtime_dir.is_symlink():
            raise RuntimeError(f"assistant runtime must not be a symlink: {runtime_dir}")
        relocated = relocate_legacy_home_repos(runtime_dir)
        if relocated:
            moves.append(
                {"assistant_id": assistant_id, "destinations": relocated}
            )
    if moves:
        report = backup_root / "relocated-repos.json"
        report.write_text(json.dumps(moves, indent=2) + "\n")
        os.chmod(report, 0o600)
