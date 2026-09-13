#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

CONTAINER_UID = 10000


def build_soul_document(name: str, owner: str, purpose: str, kind: str) -> str:
    sections = [
        f"# {name}",
        "",
        f"You are {name}, a Hermes assistant owned by {owner}.",
        "",
        f"Purpose: {purpose}",
        "",
        "You run in an isolated Aidee container. Use only your approved files, tools,",
        "repositories, and services. Never expose credentials or another assistant's",
        "data.",
        "",
        "## Communication Standards (Unslop)",
        "- Concise response budget: default to 120 words or fewer. Expand only when safety, a decision, or an error requires it.",
        "- Plain direct speech: communicate plainly without preamble, conversational filler, sycophancy, or generic cheerleading.",
        "- Real deliverables: produce working artifacts backed by actual tool execution; never substitute summaries or promises for real execution.",
        "- Interactive Telegram Choices: When communicating over Telegram and presenting choices, decisions, next steps, or confirmation requests, always use the interactive clarify tool with clickable options so the user can select an option directly rather than typing.",
    ]
    if kind in {"coding", "project"}:
        sections.extend(
            [
                "",
                "## Software Engineering Standards",
                "- Test-driven verification: enforce TDD and execute real tests (tsc, pytest, vitest) before completing tasks. Never finish without test evidence.",
                "- Systematic debugging: follow 4-phase root-cause analysis (understand, reproduce, isolate, fix) before modifying code.",
                "- Pre-commit code review: enforce quality gates, automated linting, type checks, and keep diffs atomic and minimal.",
                "- Clean documentation: write structured commit messages, clear PR descriptions linking issues, and cited action items.",
            ]
        )
    return "\n".join(sections) + "\n"


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


def sync_fleet_assistants(
    state_root: Path,
    registry_path: Path,
    owner_record_path: Path,
    owner_name_override: str | None,
    dry_run: bool,
) -> int:
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

        if not purpose:
            purpose = f"Operate as {name} assistant."

        soul_content = build_soul_document(
            name=name, owner=owner, purpose=purpose, kind=kind
        )

        fleet_soul = fleet_dir / "SOUL.md"
        runtime_soul = runtime_dir / "SOUL.md"

        if dry_run:
            print(
                f"[dry-run] Would update SOUL.md for assistant '{assistant_id}' "
                f"(fleet: {fleet_soul}, runtime: {runtime_soul})"
            )
        else:
            if fleet_dir.is_dir():
                write_file(fleet_soul, soul_content, mode=0o660)
            if runtime_dir.is_dir():
                write_file(
                    runtime_soul,
                    soul_content,
                    mode=0o660,
                    uid=CONTAINER_UID,
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
    )


if __name__ == "__main__":
    raise SystemExit(main())
