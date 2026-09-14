#!/usr/bin/env python3
"""Shared desired-state generation for assistant creation and fleet repair."""

import errno
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

def _onboarding_module_directories():
    here = Path(__file__).resolve().parent
    source_setup = Path(
        os.environ.get("AIDEE_SOURCE_ROOT", "/opt/aidee/source")
    ) / "platform" / "setup"
    candidates = [here, here.parent / "setup", source_setup]
    return candidates


def _load_onboarding_directory():
    for directory in _onboarding_module_directories():
        if (directory / "onboarding_state.py").is_file():
            path = str(directory)
            if path not in sys.path:
                sys.path.insert(0, path)
            return directory
    raise ImportError(
        "onboarding_state.py is not installed with the administration helper"
    )


_load_onboarding_directory()
from onboarding_state import (
    default_status,
    mark_step,
    migrate_status,
    onboarding_complete as status_is_complete,
)

CONTAINER_UID = 10000
CONTAINER_REPOS_ROOT = "/opt/data/aidee/repos"
ONBOARDING_RELATIVE_PATH = Path("aidee/onboarding-status.json")
ONBOARDING_PLUGIN = "aidee-onboarding"
HOME_RESERVED_DIRECTORIES = {
    "aidee",
    "cache",
    "cron",
    "crons",
    "knowledge",
    "logs",
    "memories",
    "plugins",
    "profiles",
    "sessions",
    "skills",
    "skins",
}
COMPLETE_STEP_STATES = {"completed", "skipped"}
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
        "On every user message, including greetings, run",
        "`/opt/aidee/onboarding/onboarding-gate.py`",
        f"with `--status-file /opt/data/{ONBOARDING_RELATIVE_PATH}`,",
        f"`--role assistant --assistant-kind {kind} --mode decide`",
        "before any other reply. If it returns `offer`, that reply must be only",
        "one interactive clarify with `Resume now` and `Not now`. Do not greet",
        "first. Record the answer with the gate. Resume the first incomplete",
        "required step only after `Resume now`, then resolve optional steps in the",
        "same flow. Use `/opt/aidee/onboarding/mark-onboarding-step.py` for every",
        "completed or explicitly skipped step. Never infer external completion.",
        "When the gate returns `silent` or `complete`, do not ask again.",
        "If required steps remain after `Resume now`, continue the first",
        "incomplete required step. Do not greet.",
        "The Telegram dashboard menu URL must equal `dashboard.public_url`",
        "in `/opt/data/config.yaml`. Do not invent a Tailscale URL. Do not put",
        "dashboard URLs in Telegram descriptions. Set descriptions for the",
        "default profile and `language_code=en`.",
        "Preserve existing credentials and configuration.",
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


def onboarding_plugin_source():
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "hermes-plugins" / ONBOARDING_PLUGIN,
        Path(os.environ.get("AIDEE_SOURCE_ROOT", "/opt/aidee/source"))
        / "platform/hermes-plugins"
        / ONBOARDING_PLUGIN,
    ]
    for path in candidates:
        if (path / "plugin.yaml").is_file():
            return path
    return None


def install_onboarding_plugin_files(runtime_dir, uid=None, gid=None):
    """Install the onboarding plugin under the assistant Hermes home."""
    source = onboarding_plugin_source()
    if source is None:
        return []
    destination = runtime_dir / "plugins" / ONBOARDING_PLUGIN
    ensure_directory(destination, uid=uid, gid=gid)
    changed = []
    for item in sorted(source.iterdir()):
        if not item.is_file() or item.name.endswith(".pyc"):
            continue
        target = destination / item.name
        content = item.read_text()
        if not target.is_file() or target.read_text() != content:
            atomic_write(target, content, uid=uid, gid=gid)
            changed.append(str(target))
        ensure_file_metadata(target, uid=uid, gid=gid)
    return changed


def normalize_dashboard_url(url):
    """Return an https origin with no path, query, or trailing slash."""
    if not isinstance(url, str) or not url.strip():
        raise RuntimeError("dashboard URL is required")
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("dashboard URL must be an https origin")
    if parsed.username or parsed.password:
        raise RuntimeError("dashboard URL must not include user information")
    if parsed.query or parsed.fragment:
        raise RuntimeError("dashboard URL must not include query or fragment")
    path = parsed.path or ""
    if path not in {"", "/"}:
        raise RuntimeError("dashboard URL must not include a path")
    host = parsed.hostname.lower()
    if parsed.port:
        return f"https://{host}:{parsed.port}"
    return f"https://{host}"


def dashboard_hostname(url):
    return urlparse(normalize_dashboard_url(url)).hostname


def published_dashboard_url(assistant):
    raw = (assistant.get("dashboard") or {}).get("url")
    if not raw:
        return None
    return normalize_dashboard_url(raw)


def apply_published_dashboard_url(config, url):
    """Set dashboard.public_url. Return True when the file needs a write."""
    if not isinstance(config, dict):
        raise RuntimeError("assistant config is not a mapping")
    normalized = normalize_dashboard_url(url)
    dashboard = config.get("dashboard")
    if not isinstance(dashboard, dict):
        dashboard = {}
        config["dashboard"] = dashboard
    if dashboard.get("public_url") == normalized:
        return False
    dashboard["public_url"] = normalized
    return True


def enable_onboarding_plugin(config):
    """Add the onboarding plugin to plugins.enabled without dropping others."""
    if not isinstance(config, dict):
        raise RuntimeError("assistant config is not a mapping")
    plugins = config.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
        config["plugins"] = plugins
    enabled = plugins.get("enabled")
    if not isinstance(enabled, list):
        enabled = []
        plugins["enabled"] = enabled
    if ONBOARDING_PLUGIN not in enabled:
        enabled.append(ONBOARDING_PLUGIN)
        return True
    return False


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


def default_onboarding_status(assistant_kind="personal", config=None):
    return default_status("assistant", assistant_kind, config)


def merge_onboarding_status(current, assistant_kind="personal", config=None):
    return migrate_status(current, "assistant", assistant_kind, config)


def onboarding_complete(status):
    return status_is_complete(status)


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


def _is_git_checkout(path):
    return path.is_dir() and not path.is_symlink() and (path / ".git").exists()


def _lexists(path):
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError as error:
        if error.errno == errno.ENOTDIR:
            return False
        raise


def _unique_directory(parent, name):
    candidate = parent / name
    if not _lexists(candidate):
        return candidate
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = parent / f"{name}.{stamp}"
    if not _lexists(candidate):
        return candidate
    index = 2
    while True:
        candidate = parent / f"{name}.{stamp}.{index}"
        if not _lexists(candidate):
            return candidate
        index += 1


def _remove_empty_parents(path, stop):
    current = path
    while current != stop:
        if not current.is_dir() or current.is_symlink():
            return
        try:
            next(current.iterdir())
            return
        except StopIteration:
            parent = current.parent
            current.rmdir()
            current = parent


def legacy_home_git_checkouts(runtime_dir):
    """Return git checkouts that do not belong in the assistant Hermes home."""
    found = []
    if not runtime_dir.is_dir():
        return found
    for item in sorted(runtime_dir.iterdir()):
        if item.name.startswith(".") or item.name in HOME_RESERVED_DIRECTORIES:
            continue
        if item.is_symlink() or not item.is_dir():
            continue
        if _is_git_checkout(item):
            found.append(item)
            continue
        try:
            children = sorted(item.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_symlink() or not child.is_dir():
                continue
            if _is_git_checkout(child):
                found.append(child)
    return found


def relocate_legacy_home_repos(runtime_dir, uid=None, gid=None):
    """Move leftover home-directory clones under aidee/repos without deleting them."""
    changed = []
    repos = runtime_dir / "aidee" / "repos"
    ensure_directory(repos, uid=uid, gid=gid)
    for source in legacy_home_git_checkouts(runtime_dir):
        if source.is_symlink():
            raise RuntimeError(f"refusing to relocate symlink checkout: {source}")
        destination = repos / source.name
        if destination == source:
            continue
        if _lexists(destination):
            legacy = runtime_dir / "aidee" / "legacy-home-repos"
            ensure_directory(legacy, uid=uid, gid=gid)
            occupant_is_checkout = (
                not destination.is_symlink() and destination.is_dir()
            )
            if occupant_is_checkout:
                destination = _unique_directory(legacy, source.name)
            else:
                aside = _unique_directory(legacy, source.name)
                destination.rename(aside)
                changed.append(str(aside))
        parent = source.parent
        source.rename(destination)
        _remove_empty_parents(parent, runtime_dir)
        changed.append(str(destination))
    return changed


def reconcile_dashboard_branding(assistant, runtime_dir, uid=None, gid=None):
    """Converge local display configuration without replacing owner settings."""
    changed = []
    config_path = runtime_dir / "config.yaml"
    try:
        config = yaml.safe_load(config_path.read_text()) or {}
    except FileNotFoundError:
        config = {}
    except yaml.YAMLError as error:
        raise RuntimeError(f"assistant config is invalid: {config_path}") from error
    if not isinstance(config, dict):
        raise RuntimeError(f"assistant config is not a mapping: {config_path}")
    display = config.setdefault("display", {})
    if not isinstance(display, dict):
        display = {}
        config["display"] = display
    plugin_changed = enable_onboarding_plugin(config)
    display_changed = display.get("skin") != assistant["id"]
    if display_changed:
        display["skin"] = assistant["id"]
    published = published_dashboard_url(assistant)
    origin_changed = False
    if published:
        origin_changed = apply_published_dashboard_url(config, published)
    if display_changed or plugin_changed or origin_changed:
        atomic_write(
            config_path,
            yaml.safe_dump(config, sort_keys=False),
            uid=uid,
            gid=gid,
        )
        changed.append(str(config_path))

    profile_config = runtime_dir / "profiles/default/config.yaml"
    if profile_config.is_file():
        try:
            profile = yaml.safe_load(profile_config.read_text()) or {}
        except yaml.YAMLError as error:
            raise RuntimeError(
                f"assistant profile config is invalid: {profile_config}"
            ) from error
        profile_changed = False
        if isinstance(profile, dict):
            profile_changed = enable_onboarding_plugin(profile)
            if published and apply_published_dashboard_url(profile, published):
                profile_changed = True
        if profile_changed:
            atomic_write(
                profile_config,
                yaml.safe_dump(profile, sort_keys=False),
                uid=uid,
                gid=gid,
            )
            changed.append(str(profile_config))

    skin_path = runtime_dir / "skins" / f"{assistant['id']}.yaml"
    try:
        skin = yaml.safe_load(skin_path.read_text()) or {}
    except FileNotFoundError:
        skin = {}
    except yaml.YAMLError as error:
        raise RuntimeError(f"assistant skin is invalid: {skin_path}") from error
    if not isinstance(skin, dict):
        raise RuntimeError(f"assistant skin is not a mapping: {skin_path}")
    branding = skin.setdefault("branding", {})
    if not isinstance(branding, dict):
        branding = {}
        skin["branding"] = branding
    expected = {
        "agent_name": assistant["name"],
        "response_label": f" ⚕ {assistant['name']} ",
    }
    if any(branding.get(key) != value for key, value in expected.items()):
        branding.update(expected)
        atomic_write(
            skin_path,
            yaml.safe_dump(skin, sort_keys=False),
            uid=uid,
            gid=gid,
        )
        changed.append(str(skin_path))
    return changed, config


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
            "plugins": {"enabled": [ONBOARDING_PLUGIN]},
        }
        atomic_write(
            runtime_config,
            yaml.safe_dump(config, sort_keys=False),
            uid=uid,
            gid=gid,
        )
        changed.append(str(runtime_config))
    ensure_file_metadata(runtime_config, uid=uid, gid=gid)

    branding_changes, runtime_values = reconcile_dashboard_branding(
        assistant, runtime_dir, uid=uid, gid=gid
    )
    changed.extend(branding_changes)
    changed.extend(
        install_onboarding_plugin_files(runtime_dir, uid=uid, gid=gid)
    )
    skin = runtime_dir / "skins" / f"{assistant['id']}.yaml"
    ensure_file_metadata(skin, uid=uid, gid=gid)

    repos = runtime_dir / "aidee" / "repos"
    ensure_directory(repos, uid=uid, gid=gid)
    changed.extend(relocate_legacy_home_repos(runtime_dir, uid=uid, gid=gid))

    status_path = runtime_dir / ONBOARDING_RELATIVE_PATH
    try:
        current = json.loads(status_path.read_text())
    except FileNotFoundError:
        current = {}
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"assistant onboarding status is invalid: {status_path}"
        ) from error
    telegram = (runtime_values.get("platforms") or {}).get("telegram") or {}
    dashboard = runtime_values.get("dashboard") or {}
    onboarding_config = {
        "telegram_enabled": bool(telegram.get("enabled", True)),
        "dashboard_menu_enabled": bool(dashboard.get("public_url")),
    }
    assistant_kind = assistant.get("kind", "personal")
    merged = merge_onboarding_status(current, assistant_kind, onboarding_config)
    rendered = json.dumps(merged, indent=2) + "\n"
    if not status_path.is_file() or status_path.read_text() != rendered:
        atomic_write(status_path, rendered, uid=uid, gid=gid, mode=0o660)
        changed.append(str(status_path))
    if merged["steps"]["dashboard_branding"]["status"] != "completed":
        mark_step(
            status_path,
            "assistant",
            "dashboard_branding",
            "completed",
            assistant_kind=assistant_kind,
            config=onboarding_config,
            evidence_source="reconciler",
            evidence_detail="display skin and branding match assistant identity",
        )
        if str(status_path) not in changed:
            changed.append(str(status_path))
    ensure_file_metadata(status_path, uid=uid, gid=gid)
    return changed
