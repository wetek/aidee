#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

ADMIN_DIR = Path(__file__).resolve().parents[1] / "admin"
sys.path.insert(0, str(ADMIN_DIR))
from assistant_state import (  # noqa: E402
    CONTAINER_UID,
    reconcile_assistant_files,
)


def resolve_owner(
    owner_name_arg: str | None, owner_record_path: Path, state_root: Path
) -> str:
    if owner_name_arg and owner_name_arg.strip():
        return owner_name_arg.strip()
    if owner_record_path.is_file():
        try:
            owner_data = json.loads(owner_record_path.read_text())
            name = owner_data.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        except (json.JSONDecodeError, OSError):
            pass

    controller_user_md = (
        state_root / "fleet" / "controller" / "memories" / "USER.md"
    )
    if controller_user_md.is_file():
        try:
            text = controller_user_md.read_text()
            match = re.search(
                r"^([^\n#]+?)\s+owns\s+and\s+directs", text, re.MULTILINE
            )
            if match:
                return match.group(1).strip()
        except OSError:
            pass

    return "Owner"


def write_file(path: Path, content: str, mode: int = 0o660, uid: int | None = None):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content)
    try:
        os.chmod(temporary, mode)
    except OSError:
        pass
    if uid is not None:
        try:
            os.chown(temporary, uid, -1)
        except OSError:
            pass
    temporary.replace(path)
    if uid is not None:
        try:
            os.chown(path, uid, -1)
        except OSError:
            pass


def sync_shared_skills(
    source_root: Path, runtime_dir: Path, dry_run: bool = False
) -> list[str]:
    shared_skills_dir = source_root / "platform" / "shared-skills"
    if not shared_skills_dir.is_dir():
        return []
    synced_skills = []
    target_skills_dir = runtime_dir / "skills"
    for item in sorted(shared_skills_dir.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        skill_file = item / "SKILL.md"
        if not skill_file.is_file():
            continue
        synced_skills.append(item.name)
        if not dry_run:
            dest_dir = target_skills_dir / item.name
            dest_dir.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(dest_dir, 0o770)
            except OSError:
                pass
            try:
                os.chown(dest_dir, CONTAINER_UID, -1)
            except OSError:
                pass
            for subpath in item.rglob("*"):
                rel_path = subpath.relative_to(item)
                dest_subpath = dest_dir / rel_path
                if subpath.is_dir():
                    dest_subpath.mkdir(parents=True, exist_ok=True)
                    try:
                        os.chmod(dest_subpath, 0o770)
                    except OSError:
                        pass
                    try:
                        os.chown(dest_subpath, CONTAINER_UID, -1)
                    except OSError:
                        pass
                elif subpath.is_file():
                    write_file(
                        dest_subpath,
                        subpath.read_text(),
                        mode=0o660,
                        uid=CONTAINER_UID,
                    )
    if not dry_run and synced_skills:
        try:
            os.chmod(target_skills_dir, 0o770)
        except OSError:
            pass
        try:
            os.chown(target_skills_dir, CONTAINER_UID, -1)
        except OSError:
            pass
    return synced_skills


def sync_fleet_assistants(
    state_root: Path,
    registry_path: Path,
    owner_record_path: Path,
    owner_name_override: str | None,
    dry_run: bool,
    source_root: Path | None = None,
) -> int:
    if source_root is None:
        source_root = Path(
            os.environ.get(
                "AIDEE_SOURCE_ROOT", str(Path(__file__).resolve().parents[2])
            )
        )
    if not registry_path.is_file():
        print(f"Fleet registry not found: {registry_path}", file=sys.stderr)
        return 0

    try:
        registry_data = yaml.safe_load(registry_path.read_text())
    except Exception as error:
        print(f"error reading registry: {error}", file=sys.stderr)
        return 1

    if not isinstance(registry_data, dict):
        print(f"error: invalid registry content in {registry_path}", file=sys.stderr)
        return 1

    assistants = registry_data.get("assistants", [])
    if not isinstance(assistants, list) or len(assistants) == 0:
        print("No assistants found in fleet registry.")
        return 0

    owner = resolve_owner(owner_name_override, owner_record_path, state_root)
    synced_count = 0

    for item in assistants:
        if not isinstance(item, dict):
            continue
        assistant_id = item.get("id")
        if not assistant_id:
            continue

        name = item.get("name", assistant_id.capitalize())
        kind = item.get("kind", "personal")
        purpose = item.get("purpose")

        state_path = item.get("state_path", f"assistants/{assistant_id}")
        fleet_dir = state_root / "fleet" / state_path
        runtime_dir = state_root / "runtime" / f"assistants/{assistant_id}/data"

        assistant_yaml_path = fleet_dir / "assistant.yaml"
        if assistant_yaml_path.is_file():
            try:
                cfg = yaml.safe_load(assistant_yaml_path.read_text())
                if isinstance(cfg, dict):
                    asst_cfg = cfg.get("assistant", {})
                    if isinstance(asst_cfg, dict):
                        name = asst_cfg.get("name", name)
                        kind = asst_cfg.get("kind", kind)
                        if not purpose:
                            purpose = asst_cfg.get("purpose")
            except Exception as error:
                print(
                    f"warning: failed to read {assistant_yaml_path}: {error}",
                    file=sys.stderr,
                )

        fleet_soul = fleet_dir / "SOUL.md"
        if not purpose and fleet_soul.is_file():
            try:
                match = re.search(
                    r"^Purpose:\s*(.+)$",
                    fleet_soul.read_text(),
                    re.MULTILINE,
                )
                if match:
                    purpose = match.group(1).strip()
            except OSError:
                pass

        if not purpose:
            purpose = f"Operate as {name} assistant."

        assistant = {
            "id": assistant_id,
            "name": name,
            "kind": kind,
            "purpose": purpose,
        }
        runtime_soul = runtime_dir / "SOUL.md"

        if dry_run:
            print(
                f"[dry-run] Would update SOUL.md for assistant '{assistant_id}' "
                f"(fleet: {fleet_soul}, runtime: {runtime_soul})"
            )
            skills = sync_shared_skills(source_root, runtime_dir, dry_run=True)
            if skills:
                print(
                    f"[dry-run] Would sync {len(skills)} shared skill(s) for '{assistant_id}': "
                    f"{', '.join(skills)}"
                )
        else:
            if fleet_dir.is_dir() and runtime_dir.is_dir():
                reconcile_assistant_files(
                    assistant,
                    owner,
                    fleet_dir,
                    runtime_dir,
                    uid=CONTAINER_UID,
                )
                skills = sync_shared_skills(source_root, runtime_dir, dry_run=False)
                if skills:
                    print(
                        f"Synced {len(skills)} shared skill(s) for '{assistant_id}'"
                    )
            print(f"Updated SOUL.md for assistant '{assistant_id}'")

        synced_count += 1

    if dry_run:
        print(f"[dry-run] Checked {synced_count} assistant(s).")
    else:
        print(f"Synced {synced_count} assistant(s) successfully.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Sync fleet assistants runtime and configuration standards."
    )
    parser.add_argument(
        "--approved",
        action="store_true",
        help="Apply updates to assistant fleet state and runtime.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview updates without modifying files.",
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        default=Path(os.environ.get("AIDEE_STATE_ROOT", "/var/lib/aidee")),
        help="Path to Aidee state root directory.",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="Path to fleet registry.yaml (defaults to <state-root>/fleet/registry.yaml).",
    )
    parser.add_argument(
        "--owner-record",
        type=Path,
        default=Path(os.environ.get("AIDEE_OWNER_RECORD", "/etc/aidee/owner.json")),
        help="Path to owner record JSON file.",
    )
    parser.add_argument(
        "--owner-name",
        type=str,
        default=None,
        help="Override owner name for generated SOUL documents.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="Path to Aidee source root directory (defaults to $AIDEE_SOURCE_ROOT).",
    )

    arguments = parser.parse_args()

    if not arguments.approved and not arguments.dry_run:
        print(
            "error: owner approval is required; pass --approved (or --dry-run for preview)",
            file=sys.stderr,
        )
        return 1

    state_root = arguments.state_root
    registry_path = (
        arguments.registry
        if arguments.registry is not None
        else (state_root / "fleet" / "registry.yaml")
    )
    owner_record_path = arguments.owner_record

    return sync_fleet_assistants(
        state_root=state_root,
        registry_path=registry_path,
        owner_record_path=owner_record_path,
        owner_name_override=arguments.owner_name,
        dry_run=arguments.dry_run,
        source_root=arguments.source_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
