#!/usr/bin/env python3
"""Shared desired-state generation for assistant creation and fleet repair."""

import json
import os
import tempfile
from pathlib import Path

import yaml


CONTAINER_UID = 10000
CONTAINER_REPOS_ROOT = "/opt/data/aidee/repos"
ONBOARDING_RELATIVE_PATH = Path("aidee/onboarding-status.json")
ONBOARDING_STEPS = ("identity", "dashboard", "model", "telegram", "repository")
COMPLETE_STEP_STATES = {"complete", "deferred", "not_applicable"}
STEP_STATES = COMPLETE_STEP_STATES | {"pending", "in_progress"}


def build_soul_document(assistant, owner):
    name = assistant["name"]
    purpose = assistant.get("purpose") or f"Operate as {name} assistant."
    kind = assistant.get("kind", "personal")
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
        f"Store every coding-task repository under {CONTAINER_REPOS_ROOT}.",
        "",
        "## First-run onboarding",
        f"Read `/opt/data/{ONBOARDING_RELATIVE_PATH}` before operational work.",
        "On every later interaction, resume the first incomplete onboarding step.",
        "Cover identity, dashboard access, model setup, Telegram setup, and repository",
        "access. Record a step as complete only after the owner or a direct check",
        "confirms it. Preserve existing credentials and configuration.",
        "",
        "## Communication standards",
        "- Default to 120 words or fewer. Expand when safety, a decision, or an error requires it.",
        "- Use plain direct speech without preamble, filler, sycophancy, or generic cheerleading.",
        "- Produce working artifacts backed by tool execution. Do not replace work with promises.",
        "- On Telegram, present choices, decisions, next steps, and confirmations with interactive clarify tool with clickable options.",
        "- For command approvals on Telegram, give a one or two line explanation of purpose and effects. The platform already shows the command and action buttons.",
        "",
        "## Repository workspace",
        f"- Clone and work on repositories only below `{CONTAINER_REPOS_ROOT}`.",
        "- Prefer a repository-scoped deploy key or fine-grained token. Do not request credentials in chat.",
    ]
    if kind in {"coding", "project"}:
        sections.extend(
            [
                "",
                "## Software engineering standards",
                "- Run relevant tests and type checks before completing work.",
                "- Use `diagnosing-bugs` for root-cause analysis before changing code.",
                "- Use the requirements and specification skills before ambiguous work.",
                "- Use `codebase-design` and `domain-modeling` for architecture decisions.",
                "- Use `code-review` before handoff and keep changes reviewable.",
                "- Use `handoff` to preserve verified state across sessions.",
            ]
        )
    return "\n".join(sections) + "\n"


def default_assistant_config(assistant):
    return {
        "schema_version": 1,
        "assistant": {
            "id": assistant["id"],
            "name": assistant["name"],
            "kind": assistant.get("kind", "personal"),
            "purpose": assistant.get("purpose")
            or f"Operate as {assistant['name']} assistant.",
        },
        "projects": [],
        "approvals": {"mode": "hermes_default"},
    }


def default_onboarding_status():
    return {
        "schema_version": 1,
        "steps": {step: {"status": "pending"} for step in ONBOARDING_STEPS},
    }


def onboarding_complete(status):
    steps = status.get("steps") if isinstance(status, dict) else None
    return isinstance(steps, dict) and all(
        isinstance(steps.get(step), dict)
        and steps[step].get("status") in COMPLETE_STEP_STATES
        for step in ONBOARDING_STEPS
    )


def merge_onboarding_status(current):
    desired = default_onboarding_status()
    if not isinstance(current, dict):
        return desired
    desired["schema_version"] = 1
    current_steps = current.get("steps")
    if isinstance(current_steps, dict):
        for step in ONBOARDING_STEPS:
            value = current_steps.get(step)
            if isinstance(value, dict):
                desired["steps"][step].update(value)
                if desired["steps"][step].get("status") not in STEP_STATES:
                    desired["steps"][step]["status"] = "pending"
    return desired


def atomic_write(path, content, uid=None, gid=None, mode=0o660):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"refusing to replace managed symlink: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        if uid is not None or gid is not None:
            try:
                os.chown(
                    temporary,
                    uid if uid is not None else -1,
                    gid if gid is not None else -1,
                )
            except PermissionError:
                pass
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def ensure_directory(path, uid=None, gid=None, mode=0o770):
    if path.is_symlink():
        raise RuntimeError(f"managed directory must not be a symlink: {path}")
    if path.exists() and not path.is_dir():
        raise RuntimeError(f"managed directory path is not a directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, mode)
    except PermissionError:
        pass
    if uid is not None or gid is not None:
        try:
            os.chown(
                path,
                uid if uid is not None else -1,
                gid if gid is not None else -1,
            )
        except PermissionError:
            pass


def ensure_file_metadata(path, uid=None, gid=None, mode=0o660):
    if path.is_symlink():
        raise RuntimeError(f"managed file must not be a symlink: {path}")
    if not path.is_file():
        raise RuntimeError(f"managed file path is not a regular file: {path}")
    try:
        os.chmod(path, mode)
        if uid is not None or gid is not None:
            os.chown(
                path,
                uid if uid is not None else -1,
                gid if gid is not None else -1,
            )
    except PermissionError:
        pass


def reconcile_assistant_files(
    assistant,
    owner,
    fleet_dir,
    runtime_dir,
    uid=CONTAINER_UID,
    gid=None,
    fleet_uid=None,
):
    """Converge generated files while preserving user-owned config and credentials."""
    changed = []
    ensure_directory(fleet_dir / "memories", uid=fleet_uid, gid=gid)
    for directory in (
        runtime_dir,
        runtime_dir / "memories",
        runtime_dir / "skins",
        runtime_dir / "aidee",
    ):
        ensure_directory(directory, uid=uid, gid=gid)
    soul = build_soul_document(assistant, owner)
    for path, owner_uid in (
        (fleet_dir / "SOUL.md", fleet_uid),
        (runtime_dir / "SOUL.md", uid),
    ):
        if not path.is_file() or path.read_text() != soul:
            atomic_write(path, soul, uid=owner_uid, gid=gid)
            changed.append(str(path))
        ensure_file_metadata(path, uid=owner_uid, gid=gid)

    assistant_config = fleet_dir / "assistant.yaml"
    if not assistant_config.is_file():
        atomic_write(
            assistant_config,
            yaml.safe_dump(default_assistant_config(assistant), sort_keys=False),
            uid=fleet_uid,
            gid=gid,
        )
        changed.append(str(assistant_config))
    ensure_file_metadata(assistant_config, uid=fleet_uid, gid=gid)

    for path, content, owner_uid in (
        (
            fleet_dir / "memories/USER.md",
            f"# User\n\n{owner} owns and directs this assistant.\n",
            fleet_uid,
        ),
        (fleet_dir / "memories/MEMORY.md", "# Memory\n", fleet_uid),
        (
            runtime_dir / "memories/USER.md",
            f"# User\n\n{owner} owns and directs this assistant.\n",
            uid,
        ),
        (runtime_dir / "memories/MEMORY.md", "# Memory\n", uid),
    ):
        if not path.is_file():
            atomic_write(path, content, uid=owner_uid, gid=gid)
            changed.append(str(path))
        ensure_file_metadata(path, uid=owner_uid, gid=gid)

    runtime_config = runtime_dir / "config.yaml"
    if not runtime_config.is_file():
        dashboard_url = (assistant.get("dashboard") or {}).get("url")
        config = {
            "dashboard": {"public_url": dashboard_url},
            "display": {"skin": assistant["id"]},
            "platforms": {"telegram": {"enabled": True}},
        }
        atomic_write(
            runtime_config,
            yaml.safe_dump(config, sort_keys=False),
            uid=uid,
            gid=gid,
        )
        changed.append(str(runtime_config))
    ensure_file_metadata(runtime_config, uid=uid, gid=gid)

    skin = runtime_dir / "skins" / f"{assistant['id']}.yaml"
    if not skin.is_file():
        skin_config = {
            "branding": {
                "agent_name": assistant["name"],
                "response_label": f" ⚕ {assistant['name']} ",
            }
        }
        atomic_write(
            skin,
            yaml.safe_dump(skin_config, sort_keys=False),
            uid=uid,
            gid=gid,
        )
        changed.append(str(skin))
    ensure_file_metadata(skin, uid=uid, gid=gid)

    repos = runtime_dir / "aidee" / "repos"
    ensure_directory(repos, uid=uid, gid=gid)

    status_path = runtime_dir / ONBOARDING_RELATIVE_PATH
    try:
        current = json.loads(status_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        current = {}
    merged = merge_onboarding_status(current)
    rendered = json.dumps(merged, indent=2) + "\n"
    if not status_path.is_file() or status_path.read_text() != rendered:
        atomic_write(status_path, rendered, uid=uid, gid=gid, mode=0o660)
        changed.append(str(status_path))
    ensure_file_metadata(status_path, uid=uid, gid=gid)
    return changed
