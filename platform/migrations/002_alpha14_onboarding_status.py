#!/usr/bin/env python3
"""Back up legacy onboarding documents before Alpha 14 reconciliation."""

import json
import os
import re
import shutil
from pathlib import Path

import yaml


ASSISTANT_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def _reject_symlink_components(root, path):
    current = root
    if current.is_symlink():
        raise RuntimeError(f"state root must not be a symlink: {root}")
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"state path contains a symlink: {current}")


def _backup(state_root, source, destination):
    _reject_symlink_components(state_root, source)
    if not source.exists():
        return
    if source.is_symlink() or not source.is_file():
        raise RuntimeError(f"onboarding status must be a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    created = False
    if not destination.exists():
        shutil.copy2(source, destination)
        os.chmod(destination, 0o600)
        created = True
    try:
        current = json.loads(source.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"onboarding status is invalid: {source}") from error
    if current.get("schema_version") == 2:
        if created:
            destination.unlink()
        return


def apply(state_root: Path, backup_root: Path):
    backup_root.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_root, 0o700)
    _backup(
        state_root,
        state_root / "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json",
        backup_root / "controller/CONTROLLER_ONBOARDING_STATUS.json",
    )

    registry_path = state_root / "fleet/registry.yaml"
    if not registry_path.exists():
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
    for assistant in assistants:
        assistant_id = assistant.get("id") if isinstance(assistant, dict) else None
        if not isinstance(assistant_id, str) or not ASSISTANT_ID.fullmatch(
            assistant_id
        ):
            raise RuntimeError("fleet registry has an invalid assistant ID")
        _backup(
            state_root,
            state_root
            / f"runtime/assistants/{assistant_id}/data/aidee/onboarding-status.json",
            backup_root / f"assistants/{assistant_id}/onboarding-status.json",
        )
