#!/usr/bin/env python3
"""Add durable assistant onboarding references to legacy fleet registries."""

import os
import shutil
import tempfile
from pathlib import Path

import yaml


def apply(state_root: Path, backup_root: Path):
    registry_path = state_root / "fleet/registry.yaml"
    if not registry_path.is_file():
        return
    if registry_path.is_symlink():
        raise RuntimeError("fleet registry must not be a symlink")
    registry = yaml.safe_load(registry_path.read_text())
    if not isinstance(registry, dict):
        raise RuntimeError("fleet registry is not an object")
    assistants = registry.get("assistants")
    if not isinstance(assistants, list):
        raise RuntimeError("fleet registry assistants is not a list")

    backup_root.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_root, 0o700)
    backup = backup_root / "registry.yaml"
    if not backup.exists():
        shutil.copy2(registry_path, backup)
        os.chmod(backup, 0o600)

    for assistant in assistants:
        if not isinstance(assistant, dict):
            continue
        assistant.setdefault(
            "onboarding",
            {
                "status": "pending",
                "status_path": "aidee/onboarding-status.json",
            },
        )

    metadata = registry_path.stat()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".registry.yaml.", dir=registry_path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(yaml.safe_dump(registry, sort_keys=False))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, metadata.st_mode & 0o777)
        os.chown(temporary, metadata.st_uid, metadata.st_gid)
        temporary.replace(registry_path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
