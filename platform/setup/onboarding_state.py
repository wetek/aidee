#!/usr/bin/env python3
"""Durable onboarding state, migration, gating, and evidence policy."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


SCHEMA_VERSION = 2
PROMPT_VERSION = 1
STATUSES = {"pending", "in_progress", "completed", "skipped"}
RESOLVED_STATUSES = {"completed", "skipped"}
ASSISTANT_KINDS = {"personal", "coding", "client", "project"}
CONTROLLER_STATUS_RELATIVE = Path(
    "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json"
)
ASSISTANT_STATUS_PATH = Path("/opt/data/aidee/onboarding-status.json")
MAX_NOTE_LENGTH = 500
MAX_EVIDENCE_ITEMS = 8
MAX_EVIDENCE_DETAIL_LENGTH = 500
SECRET_WORDS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
}
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:bearer|basic)\s+\S+"),
    re.compile(r"\b[0-9]{6,12}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:sk-|gh[opusr]_|github_pat_)[A-Za-z0-9_-]{16,}\b"),
    re.compile(
        r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"
    ),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
)

CONTROLLER_STEPS = (
    ("owner_authorization", True, "external"),
    ("default_crons", True, "local"),
    ("identity_skin", False, "local"),
    ("telegram_profile_avatar", False, "external"),
    ("telegram_menu_button", False, "external"),
    ("dashboard_phone_access", True, "external"),
    ("model_messaging", True, "external"),
)

ASSISTANT_STEPS = (
    ("identity", True, "external"),
    ("dashboard_branding", True, "local"),
    ("model_messaging", True, "external"),
    ("telegram_profile_avatar", False, "external"),
    ("telegram_menu_button", False, "external"),
    ("owner_authorization", True, "external"),
    ("repositories", True, "external"),
    ("coding_tools_scripts", True, "local"),
)

LEGACY_ASSISTANT_STEPS = {
    "identity": ("identity",),
    "dashboard": ("dashboard_branding",),
    "model": ("model_messaging",),
    "repository": ("repositories",),
}


class OnboardingError(RuntimeError):
    """Raised when onboarding state or evidence violates policy."""


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_status_path(path, role):
    """Restrict command-line state writes to the configured Aidee state file."""
    path = Path(path)
    if role == "controller":
        state_root = Path(os.environ.get("AIDEE_STATE_DIR", "/var/lib/aidee"))
        expected = state_root / CONTROLLER_STATUS_RELATIVE
    elif role == "assistant":
        state_root = ASSISTANT_STATUS_PATH.parent
        expected = ASSISTANT_STATUS_PATH
    else:
        raise OnboardingError(f"unsupported onboarding role: {role}")
    if not path.is_absolute():
        raise OnboardingError("onboarding status path must be absolute")
    if os.path.normpath(path) != os.path.normpath(expected):
        raise OnboardingError(
            f"onboarding status path is outside the approved {role} state root"
        )
    _reject_symlink_components(path, state_root)
    return path


def _reject_symlink_components(path, root=None):
    path = Path(path)
    if root is None:
        for candidate in (path.parent, path):
            if candidate.is_symlink():
                raise OnboardingError(
                    f"onboarding status path contains a symlink: {candidate}"
                )
        return
    root = Path(root)
    if root.is_symlink():
        raise OnboardingError(
            f"onboarding status path contains a symlink: {root}"
        )
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise OnboardingError(
                f"onboarding status path contains a symlink: {current}"
            )


def _clean_text(value, field, limit):
    if value is None:
        return None
    if not isinstance(value, str):
        raise OnboardingError(f"{field} must be text")
    value = value.strip()
    if not value or len(value) > limit or any(ord(char) < 32 for char in value):
        raise OnboardingError(f"{field} is empty, too long, or contains control characters")
    lowered = value.lower()
    if any(word in lowered for word in SECRET_WORDS) or any(
        pattern.search(value) for pattern in SECRET_PATTERNS
    ):
        raise OnboardingError(f"{field} may contain secret material")
    return value


def step_definitions(role, assistant_kind=None, config=None):
    """Return ordered step policy derived only from non-secret configuration."""
    config = config if isinstance(config, dict) else {}
    telegram_enabled = bool(config.get("telegram_enabled", True))
    menu_enabled = telegram_enabled and bool(config.get("dashboard_menu_enabled", True))
    identity_skin_enabled = bool(config.get("identity_skin_enabled", True))
    if role == "controller":
        source = CONTROLLER_STEPS
    elif role == "assistant":
        if assistant_kind not in ASSISTANT_KINDS:
            raise OnboardingError("assistant kind is required for assistant onboarding")
        source = ASSISTANT_STEPS
    else:
        raise OnboardingError(f"unsupported onboarding role: {role}")

    definitions = []
    for step_id, required, evidence_policy in source:
        applicable = True
        reason = None
        if step_id in {
            "owner_authorization",
            "telegram_profile_avatar",
            "telegram_menu_button",
        } and not telegram_enabled:
            applicable = False
            reason = "Telegram is disabled"
        elif step_id == "telegram_menu_button" and not menu_enabled:
            applicable = False
            reason = "Dashboard menu button is disabled"
        elif step_id == "identity_skin" and not identity_skin_enabled:
            applicable = False
            reason = "Controller identity skin is not configured"
        if role == "assistant" and step_id in {"repositories", "coding_tools_scripts"}:
            required = assistant_kind in {"coding", "project"}
        definitions.append(
            {
                "id": step_id,
                "required": required,
                "applicable": applicable,
                "evidence_policy": evidence_policy,
                "skip_reason": reason,
            }
        )
    return definitions


def _new_step(definition, now):
    if definition["applicable"]:
        status = "pending"
        reason = None
    else:
        status = "skipped"
        reason = definition["skip_reason"]
    return {
        "required": definition["required"],
        "applicable": definition["applicable"],
        "evidence_policy": definition["evidence_policy"],
        "status": status,
        "updated_at": now,
        "reason": reason,
        "note": None,
        "evidence": [],
    }


def default_status(role, assistant_kind=None, config=None, now=None):
    now = now or utc_now()
    config = config if isinstance(config, dict) else {}
    context = {
        "telegram_enabled": bool(config.get("telegram_enabled", True)),
        "dashboard_menu_enabled": bool(
            config.get("dashboard_menu_enabled", True)
        ),
        "identity_skin_enabled": bool(config.get("identity_skin_enabled", True)),
    }
    state = {
        "schema_version": SCHEMA_VERSION,
        "role": role,
        "assistant_kind": assistant_kind if role == "assistant" else None,
        "context": context,
        "created_at": now,
        "updated_at": now,
        "prompt": {
            "version": PROMPT_VERSION,
            "last_prompted_at": None,
            "required_fingerprint": None,
            "response": None,
            "responded_at": None,
        },
        "steps": {
            definition["id"]: _new_step(definition, now)
            for definition in step_definitions(role, assistant_kind, config)
        },
        "rollup": {},
    }
    return recompute_rollup(state)


def _map_legacy_status(value):
    return {
        "applied": "completed",
        "active": "completed",
        "complete": "completed",
        "completed": "completed",
        "deferred": "pending",
        "disabled": "skipped",
        "in_progress": "in_progress",
        "not_applicable": "skipped",
        "pending": "pending",
        "skipped": "skipped",
    }.get(value, "pending")


def _copy_legacy_step(target, source, now):
    if not isinstance(source, dict):
        return
    if not target["applicable"]:
        if source.get("applicable") is False and source.get("status") == "skipped":
            timestamp = source.get("updated_at")
            if isinstance(timestamp, str):
                target["updated_at"] = timestamp
            try:
                target["note"] = _clean_text(
                    source.get("note"), "note", MAX_NOTE_LENGTH
                )
            except OnboardingError:
                target["note"] = None
        return
    if source.get("applicable") is False:
        return
    mapped = _map_legacy_status(source.get("status"))
    target["status"] = mapped
    if mapped == "skipped":
        candidate = (
            source.get("reason")
            or source.get("note")
            or "Migrated legacy skip choice"
        )
        try:
            target["reason"] = _clean_text(
                candidate, "skip reason", MAX_NOTE_LENGTH
            )
        except OnboardingError:
            target["reason"] = "Migrated legacy skip choice"
    elif mapped == "completed":
        target["reason"] = None
    try:
        target["note"] = _clean_text(source.get("note"), "note", MAX_NOTE_LENGTH)
    except OnboardingError:
        target["note"] = None
    timestamp = (
        source.get("updated_at")
        or source.get("completed_at")
        or source.get("confirmed_at")
    )
    target["updated_at"] = timestamp if isinstance(timestamp, str) else now
    evidence = source.get("evidence")
    if isinstance(evidence, list):
        safe_evidence = []
        for item in evidence:
            if not isinstance(item, dict):
                continue
            try:
                safe_evidence.append(
                    _evidence_item(
                        item.get("source"),
                        item.get("detail"),
                        item.get("recorded_at") or now,
                    )
                )
            except OnboardingError:
                continue
        target["evidence"] = safe_evidence[-MAX_EVIDENCE_ITEMS:]
    if mapped == "completed" and not target["evidence"]:
        target["evidence"] = [
            _evidence_item(
                "verified_tool", "migrated verified legacy completion", now
            )
        ]
    elif mapped == "skipped" and not target["evidence"]:
        target["evidence"] = [
            _evidence_item(
                "owner_confirmation", "migrated legacy owner choice", now
            )
        ]


def migrate_status(current, role, assistant_kind=None, config=None, now=None):
    """Idempotently migrate controller flat state or assistant schema version 1."""
    now = now or utc_now()
    if isinstance(current, dict):
        current_role = current.get("role")
        if current_role not in {None, role}:
            raise OnboardingError(
                f"onboarding role mismatch: expected {role}, found {current_role}"
            )
        if role == "assistant" and assistant_kind is None:
            assistant_kind = current.get("assistant_kind")
    if (
        config is None
        and isinstance(current, dict)
        and isinstance(current.get("context"), dict)
    ):
        config = current["context"]
    desired = default_status(role, assistant_kind, config, now)
    if not isinstance(current, dict):
        return desired

    if current.get("schema_version") == SCHEMA_VERSION:
        desired["created_at"] = current.get("created_at", desired["created_at"])
        current_prompt = (
            current.get("prompt") if isinstance(current.get("prompt"), dict) else {}
        )
        for field in desired["prompt"]:
            if field in current_prompt:
                desired["prompt"][field] = current_prompt[field]
        current_steps = current.get("steps")
        if isinstance(current_steps, dict):
            for step_id, target in desired["steps"].items():
                _copy_legacy_step(target, current_steps.get(step_id), now)
        desired["updated_at"] = current.get("updated_at", now)
        return recompute_rollup(desired)

    current_steps = current.get("steps")
    if role == "controller" and isinstance(current_steps, dict):
        for step_id, target in desired["steps"].items():
            _copy_legacy_step(target, current_steps.get(step_id), now)
    elif role == "controller":
        crons_verified = (
            current.get("health_watchdog_status") == "active"
            and current.get("update_check_status") in {"active", "disabled"}
        )
        mappings = {
            "owner_authorization": (
                "completed" if current.get("telegram_owner_authorized") is True else "pending"
            ),
            "default_crons": "completed" if crons_verified else "pending",
            "telegram_profile_avatar": _map_legacy_status(
                current.get("telegram_profile_status")
            ),
            "dashboard_phone_access": (
                "completed" if current.get("dashboard_verified") is True else "pending"
            ),
        }
        for step_id, mapped in mappings.items():
            step = desired["steps"][step_id]
            step["status"] = mapped
            if mapped == "skipped":
                step["reason"] = "Migrated verified legacy owner choice"
                step["evidence"] = [
                    _evidence_item(
                        "owner_confirmation",
                        "migrated verified legacy owner choice",
                        now,
                    )
                ]
            elif mapped == "completed":
                step["evidence"] = [
                    _evidence_item(
                        "verified_tool",
                        "migrated verified legacy completion",
                        now,
                    )
                ]
    else:
        if isinstance(current_steps, dict):
            for step_id, target in desired["steps"].items():
                _copy_legacy_step(target, current_steps.get(step_id), now)
            for old_id, new_ids in LEGACY_ASSISTANT_STEPS.items():
                source = current_steps.get(old_id)
                for new_id in new_ids:
                    _copy_legacy_step(desired["steps"][new_id], source, now)
            legacy_telegram = current_steps.get("telegram")
            if isinstance(legacy_telegram, dict):
                _copy_legacy_step(
                    desired["steps"]["owner_authorization"],
                    legacy_telegram,
                    now,
                )

    desired["created_at"] = current.get("created_at", now)
    desired["updated_at"] = now
    return recompute_rollup(desired)


def required_fingerprint(state):
    required = [
        step_id
        for step_id, step in state["steps"].items()
        if step["required"] and step["applicable"]
    ]
    payload = json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "prompt_version": PROMPT_VERSION,
            "required": required,
        },
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _step_resolved(step):
    return step["status"] == "completed" or (
        step["status"] == "skipped"
        and isinstance(step.get("reason"), str)
        and bool(step["reason"].strip())
    )


def recompute_rollup(state):
    incomplete_required = []
    incomplete_optional = []
    has_in_progress = False
    for step_id, step in state["steps"].items():
        if step["status"] == "in_progress":
            has_in_progress = True
        if not _step_resolved(step):
            target = incomplete_required if step["required"] else incomplete_optional
            target.append(step_id)
    if not incomplete_required and not incomplete_optional:
        status = "complete"
    elif has_in_progress:
        status = "in_progress"
    else:
        status = "pending"
    state["rollup"] = {
        "status": status,
        "incomplete_required": incomplete_required,
        "incomplete_optional": incomplete_optional,
        "complete": status == "complete",
    }
    return state


def onboarding_complete(state):
    return bool(recompute_rollup(state)["rollup"]["complete"])


def _render(state):
    return json.dumps(state, indent=2, sort_keys=False) + "\n"


def _atomic_write(path, state, mode):
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(_render(state))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        if path.exists():
            metadata = path.stat()
            try:
                os.chown(temporary, metadata.st_uid, metadata.st_gid)
            except PermissionError:
                pass
        temporary.replace(path)
        directory_fd = os.open(path.parent, getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


@contextmanager
def locked_status(path, role, assistant_kind=None, config=None, now=None):
    """Lock, migrate, mutate, and atomically replace one status document."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(path)
    lock_path = path.with_name(f".{path.name}.lock")
    lock_flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    lock_fd = os.open(lock_path, lock_flags, 0o660)
    if path.exists():
        metadata = path.stat()
        try:
            os.fchown(lock_fd, metadata.st_uid, metadata.st_gid)
        except PermissionError:
            pass
    with os.fdopen(lock_fd, "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            current = json.loads(path.read_text())
        except FileNotFoundError:
            current = {}
        except json.JSONDecodeError as error:
            raise OnboardingError(f"invalid onboarding status: {path}") from error
        state = migrate_status(current, role, assistant_kind, config, now)
        before = _render(current) if isinstance(current, dict) else ""
        yield state
        state["schema_version"] = SCHEMA_VERSION
        recompute_rollup(state)
        rendered = _render(state)
        if rendered != before:
            state["updated_at"] = now or utc_now()
            mode = path.stat().st_mode & 0o777 if path.exists() else 0o640
            _atomic_write(path, state, mode)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def gate(path, role, assistant_kind=None, config=None, action="decide", now=None):
    """Return offer, silent, or complete and atomically apply prompt decisions."""
    if action not in {"inspect", "decide", "resume_now", "not_now", "reopen"}:
        raise OnboardingError(f"unsupported gate action: {action}")
    with locked_status(path, role, assistant_kind, config, now) as state:
        prompt = state["prompt"]
        fingerprint = required_fingerprint(state)
        if action == "reopen":
            prompt.update(
                {
                    "last_prompted_at": None,
                    "required_fingerprint": None,
                    "response": None,
                    "responded_at": None,
                }
            )
        elif action in {"resume_now", "not_now"}:
            if prompt.get("last_prompted_at") is None:
                raise OnboardingError("no onboarding offer is awaiting a response")
            prompt["response"] = action
            prompt["responded_at"] = now or utc_now()
            if action == "resume_now":
                first = next(
                    (
                        step
                        for step in state["steps"].values()
                        if step["required"] and not _step_resolved(step)
                    ),
                    None,
                )
                if first is not None:
                    first["status"] = "in_progress"
                    first["updated_at"] = now or utc_now()

        recompute_rollup(state)
        incomplete_required = state["rollup"]["incomplete_required"]
        if state["rollup"]["complete"]:
            decision = "complete"
        elif (
            action in {"inspect", "decide"}
            and incomplete_required
            and (
                prompt.get("last_prompted_at") is None
                or prompt.get("required_fingerprint") != fingerprint
                or prompt.get("version") != PROMPT_VERSION
            )
        ):
            decision = "offer"
            if action == "decide":
                prompt.update(
                    {
                        "version": PROMPT_VERSION,
                        "last_prompted_at": now or utc_now(),
                        "required_fingerprint": fingerprint,
                        "response": None,
                        "responded_at": None,
                    }
                )
        else:
            decision = "silent"
        return {
            "decision": decision,
            "rollup": state["rollup"],
            "first_incomplete_required": (
                incomplete_required[0] if incomplete_required else None
            ),
            "prompt": dict(prompt),
        }


def _evidence_item(source, detail, now):
    allowed = {"owner_confirmation", "verified_tool", "reconciler"}
    if source not in allowed:
        raise OnboardingError(f"unsupported evidence source: {source}")
    cleaned = _clean_text(detail, "evidence detail", MAX_EVIDENCE_DETAIL_LENGTH)
    if cleaned is None:
        raise OnboardingError("evidence detail is required")
    return {
        "source": source,
        "detail": cleaned,
        "recorded_at": now,
    }


def mark_step(
    path,
    role,
    step_id,
    status,
    *,
    assistant_kind=None,
    config=None,
    evidence_source=None,
    evidence_detail=None,
    reason=None,
    note=None,
    allowed_from=None,
    now=None,
):
    """Mark one step through the evidence and owner-skip policy."""
    now = now or utc_now()
    if status not in STATUSES:
        raise OnboardingError(f"unsupported step status: {status}")
    with locked_status(path, role, assistant_kind, config, now) as state:
        if step_id not in state["steps"]:
            raise OnboardingError(f"unknown onboarding step: {step_id}")
        step = state["steps"][step_id]
        if allowed_from is not None and step["status"] not in set(allowed_from):
            raise OnboardingError(
                f"cannot change {step_id} from {step['status']}"
            )
        if status == "completed" and not step["applicable"]:
            raise OnboardingError(f"{step_id} is not applicable")
        if status == "skipped":
            if evidence_source != "owner_confirmation":
                raise OnboardingError("skipping a step requires owner confirmation")
            reason = _clean_text(reason, "skip reason", MAX_NOTE_LENGTH)
            if reason is None:
                raise OnboardingError("skipping a step requires a reason")
        elif status == "completed":
            allowed = {"owner_confirmation", "verified_tool"}
            if step["evidence_policy"] == "local":
                allowed.add("reconciler")
            if evidence_source not in allowed:
                raise OnboardingError(
                    f"{step_id} completion requires accepted evidence"
                )
            reason = None
        elif evidence_source is not None:
            raise OnboardingError("pending and in-progress updates do not accept evidence")

        evidence = list(step.get("evidence") or [])
        item = None
        if evidence_source is not None:
            item = _evidence_item(evidence_source, evidence_detail, now)
        cleaned_note = _clean_text(note, "note", MAX_NOTE_LENGTH)
        if (
            step["status"] == status
            and step.get("reason") == reason
            and step.get("note") == cleaned_note
            and item is not None
            and evidence
            and evidence[-1].get("source") == item["source"]
            and evidence[-1].get("detail") == item["detail"]
        ):
            return recompute_rollup(state)["rollup"].copy()
        if item is not None:
            evidence.append(item)
        step.update(
            {
                "status": status,
                "updated_at": now,
                "reason": reason,
                "note": cleaned_note,
                "evidence": evidence[-MAX_EVIDENCE_ITEMS:],
            }
        )
        return recompute_rollup(state)["rollup"].copy()
