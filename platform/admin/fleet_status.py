#!/usr/bin/env python3
"""Non-secret fleet overview for the controller dashboard."""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    yaml = None

SECRET_KEY_MARKERS = (
    "password",
    "secret",
    "token",
    "credential",
    "api_key",
    "authorization",
    "private_key",
    "publickey",
    "public_key",
)
MEMORY_UNITS = {
    "b": 1,
    "k": 1024,
    "kb": 1024,
    "kib": 1024,
    "m": 1024 ** 2,
    "mb": 1024 ** 2,
    "mib": 1024 ** 2,
    "g": 1024 ** 3,
    "gb": 1024 ** 3,
    "gib": 1024 ** 3,
}
ONBOARDING_UNAVAILABLE = {
    "status": "unavailable",
    "required_remaining": None,
    "optional_remaining": None,
    "required_steps": [],
    "optional_steps": [],
    "error": None,
}
LANGFUSE_PLUGIN = "observability/langfuse"
OPENCODE_TOOL = "opencode"
MAX_RUNTIME_ITEMS = 16
BUNDLED_PLUGIN_NAMES = frozenset({LANGFUSE_PLUGIN})
PLUGIN_SKIP_NAMES = frozenset(
    {
        "__pycache__",
        "node_modules",
        "src",
        "dashboard",
        "dist",
    }
)
LANGFUSE_PUBLIC_KEYS = ("HERMES_LANGFUSE_PUBLIC_KEY", "LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEYS = ("HERMES_LANGFUSE_SECRET_KEY", "LANGFUSE_SECRET_KEY")
LANGFUSE_HOST_KEYS = (
    "HERMES_LANGFUSE_BASE_URL",
    "LANGFUSE_BASE_URL",
    "HERMES_LANGFUSE_HOST",
    "LANGFUSE_HOST",
)
DEFAULT_LANGFUSE_URL = "https://cloud.langfuse.com"
LANGFUSE_KEY_MIN = 8
LANGFUSE_KEY_MAX = 256
LANGFUSE_ENV_KEY = "HERMES_LANGFUSE_ENV"
OPENCODE_LANGFUSE_ENV_NAME_KEY = "LANGFUSE_ENVIRONMENT"
CONTROLLER_LANGFUSE_ENVIRONMENT = "controller"
LANGFUSE_ENVIRONMENT_MAX = 40
LANGFUSE_ENVIRONMENT_RE = re.compile(r"^(?!langfuse)[a-z0-9_-]+$")
LANGFUSE_ENV_NAME_KEYS = (LANGFUSE_ENV_KEY, OPENCODE_LANGFUSE_ENV_NAME_KEY)
LANGFUSE_INSTALL_KEYS = (
    *LANGFUSE_PUBLIC_KEYS,
    *LANGFUSE_SECRET_KEYS,
    *LANGFUSE_HOST_KEYS,
    LANGFUSE_ENV_KEY,
    OPENCODE_LANGFUSE_ENV_NAME_KEY,
    "LANGFUSE_BASEURL",
)
OPENCODE_PACKAGE = "opencode-ai"
OPENCODE_VERSION = "1.18.3"
OPENCODE_DESIRED_RELATIVE = Path("aidee/opencode.json")
OPENCODE_SKILL_PATHS = (
    "skills/autonomous-ai-agents/opencode/SKILL.md",
    "skills/opencode/SKILL.md",
)
OPENCODE_RUNTIME_SKILL = Path("skills/opencode/SKILL.md")
# Hermes image: `useradd -u 10000 -m -d /opt/data hermes` and HERMES_HOME=/opt/data.
# Aidee Dockerfile and create_containers do not set HOME. OpenCode reads
# $HOME/.config/opencode/, which is the same bind-mounted /opt/data tree.
ASSISTANT_CONTAINER_HOME = Path("/opt/data")
ASSISTANT_CONTAINER_HERMES_HOME = Path("/opt/data")
OPENCODE_DIR_RELATIVE = Path(".config/opencode")
OPENCODE_CONFIG_RELATIVE = OPENCODE_DIR_RELATIVE / "opencode.json"
OPENCODE_CREDENTIALS_RELATIVE = OPENCODE_DIR_RELATIVE / "opencode-langfuse.json"
OPENCODE_CONFIG_ENV = "OPENCODE_CONFIG"
OPENCODE_LANGFUSE_PLUGIN = "@langfuse/opencode-observability-plugin@latest"
# Hermes GET /api/env lists unrecognized HERMES_HOME/.env keys as Custom Keys.
# These OpenCode plugin names are not in OPTIONAL_ENV_VARS, so they show there.
OPENCODE_LANGFUSE_ENV_KEYS = (
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASEURL",
    OPENCODE_LANGFUSE_ENV_NAME_KEY,
)
TRACING_INSTRUCTION_BEGIN = "<!-- AIDEE:AIDEE-AGENT-TRACING:BEGIN -->"
TRACING_INSTRUCTION_END = "<!-- AIDEE:AIDEE-AGENT-TRACING:END -->"
TRACING_INSTRUCTION_BODY = (
    "## Aidee agent tracing\n"
    "\n"
    "Aidee agent tracing is the Langfuse project configured for this Aidee install. "
    "It records how this Hermes agent behaves, and how OpenCode behaves when OpenCode "
    "is enabled. Aidee developers and the owner use those traces.\n"
    "\n"
    "It is not a repository's own Langfuse. Repository or app keys, a repo `.env`, "
    "and product telemetry stay in that repository.\n"
    "\n"
    "If the owner says Langfuse without naming a repository, app, or project product, "
    "they mean Aidee agent tracing.\n"
    "\n"
    "Do not copy Aidee install keys into a repository. Do not treat repository "
    "`LANGFUSE_*` files as this install's keys.\n"
    "\n"
    "`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASEURL` in this "
    "Hermes `.env` are Aidee OpenCode tracing aliases for the same install project. "
    "They are not a repository's keys.\n"
)
TRACING_INSTRUCTION_BLOCK = (
    f"{TRACING_INSTRUCTION_BEGIN}\n"
    f"{TRACING_INSTRUCTION_BODY}"
    f"{TRACING_INSTRUCTION_END}\n"
)
TRACING_INSTRUCTION_RE = re.compile(
    r"\n*"
    + re.escape(TRACING_INSTRUCTION_BEGIN)
    + r".*?"
    + re.escape(TRACING_INSTRUCTION_END)
    + r"\n*",
    re.DOTALL,
)
OPENCODE_INSTRUCTION_BEGIN = "<!-- AIDEE:OPENCODE-DELEGATION:BEGIN -->"
OPENCODE_INSTRUCTION_END = "<!-- AIDEE:OPENCODE-DELEGATION:END -->"
OPENCODE_INSTRUCTION_BODY = (
    "## Coding delegation\n"
    "\n"
    "You research, observe, and plan. When work reaches coding, do not write or "
    "edit the code yourself. Delegate coding to OpenCode. Review OpenCode's result "
    "and report the evidence.\n"
)
OPENCODE_INSTRUCTION_BLOCK = (
    f"{OPENCODE_INSTRUCTION_BEGIN}\n"
    f"{OPENCODE_INSTRUCTION_BODY}"
    f"{OPENCODE_INSTRUCTION_END}\n"
)
OPENCODE_INSTRUCTION_RE = re.compile(
    r"\n*"
    + re.escape(OPENCODE_INSTRUCTION_BEGIN)
    + r".*?"
    + re.escape(OPENCODE_INSTRUCTION_END)
    + r"\n*",
    re.DOTALL,
)
OPENCODE_SKILL_BODY = (
    "# OpenCode\n"
    "\n"
    "Use the OpenCode CLI for implementation. Hermes researches, observes, and "
    "plans. When work reaches coding, do not write or edit the code yourself. "
    "Delegate that work to OpenCode, then review the result.\n"
)
OPENCODE_OTEL_ENV_KEYS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_HEADERS",
    "OTEL_EXPORTER_OTLP_PROTOCOL",
)


def step_ids(items):
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, str) and item]


def is_secret_key(key):
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(marker in lowered for marker in SECRET_KEY_MARKERS)


def public_payload(value):
    """Drop secret-looking keys from a JSON-compatible value."""
    if isinstance(value, dict):
        return {
            key: public_payload(child)
            for key, child in value.items()
            if not is_secret_key(key)
        }
    if isinstance(value, list):
        return [public_payload(item) for item in value]
    return value


def parse_meminfo(text):
    totals = {}
    if not isinstance(text, str) or not text.strip():
        return {"error": "host memory is unavailable"}
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        parts = rest.split()
        if not parts:
            continue
        try:
            totals[name] = int(parts[0]) // 1024
        except (TypeError, ValueError):
            continue
    total_mb = totals.get("MemTotal")
    if not isinstance(total_mb, int) or total_mb <= 0:
        return {"error": "host memory is unavailable"}
    snapshot = {"total_mb": total_mb, "available_mb": totals.get("MemAvailable")}
    return snapshot


def parse_disk_usage(total_bytes, available_bytes, path):
    try:
        total = int(total_bytes)
        available = int(available_bytes)
    except (TypeError, ValueError):
        return {"path": str(path), "error": "host disk is unavailable"}
    if total <= 0:
        return {"path": str(path), "error": "host disk is unavailable"}
    return {
        "path": str(path),
        "total_gb": round(total / (1024 ** 3), 2),
        "available_gb": round(available / (1024 ** 3), 2),
    }


def parse_memory_quantity(text):
    if not isinstance(text, str) or not text.strip():
        return None
    match = re.fullmatch(
        r"([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)?",
        text.strip(),
    )
    if match is None:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "b").lower()
    multiplier = MEMORY_UNITS.get(unit)
    if multiplier is None:
        return None
    return round((number * multiplier) / (1024 ** 2), 2)


def parse_cpu_percent(text):
    if not isinstance(text, str) or not text.strip():
        return None
    stripped = text.strip().rstrip("%")
    try:
        return round(float(stripped), 2)
    except ValueError:
        return None


def parse_docker_inspect(payload):
    """Return live fields from one docker inspect object. Never copies Env."""
    if isinstance(payload, list):
        payload = payload[0] if payload else {}
    if not isinstance(payload, dict):
        return {
            "health_status": "unknown",
            "running": False,
            "image_version": None,
            "error": "container inspect is invalid",
        }
    state = payload.get("State") if isinstance(payload.get("State"), dict) else {}
    running = bool(state.get("Running"))
    status = state.get("Status")
    health = state.get("Health") if isinstance(state.get("Health"), dict) else {}
    health_label = health.get("Status")
    if health_label == "healthy":
        health_status = "healthy"
    elif running:
        health_status = "running"
    elif status in {"exited", "dead", "created", "paused"}:
        health_status = "stopped"
    elif isinstance(status, str) and status:
        health_status = status
    else:
        health_status = "unknown"
    labels = {}
    config = payload.get("Config")
    if isinstance(config, dict) and isinstance(config.get("Labels"), dict):
        labels = config["Labels"]
    version = labels.get("org.opencontainers.image.version")
    if not isinstance(version, str) or not version:
        version = None
    return {
        "health_status": health_status,
        "running": running,
        "image_version": version,
        "error": None,
    }


def parse_docker_stats(payload):
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {"cpu_percent": None, "memory_mb": None, "error": "container stats are invalid"}
    if not isinstance(payload, dict):
        return {"cpu_percent": None, "memory_mb": None, "error": "container stats are invalid"}
    usage = payload.get("MemUsage")
    used = usage.split("/", 1)[0].strip() if isinstance(usage, str) else None
    return {
        "cpu_percent": parse_cpu_percent(payload.get("CPUPerc")),
        "memory_mb": parse_memory_quantity(used),
        "error": None,
    }


def onboarding_summary(status, error=None):
    summary = dict(ONBOARDING_UNAVAILABLE)
    if error:
        summary["error"] = error
        return summary
    if not isinstance(status, dict):
        summary["error"] = "onboarding status is unavailable"
        return summary
    rollup = status.get("rollup")
    if not isinstance(rollup, dict):
        summary["error"] = "onboarding status is malformed"
        return summary
    required = rollup.get("incomplete_required")
    optional = rollup.get("incomplete_optional")
    if not isinstance(required, list) or not isinstance(optional, list):
        summary["error"] = "onboarding status is malformed"
        return summary
    label = rollup.get("status")
    if label not in {"pending", "in_progress", "complete"}:
        if rollup.get("complete") is True:
            label = "complete"
        elif any(
            isinstance(step, dict) and step.get("status") == "in_progress"
            for step in (status.get("steps") or {}).values()
        ):
            label = "in_progress"
        else:
            label = "pending"
    return {
        "status": label,
        "required_remaining": len(required),
        "optional_remaining": len(optional),
        "required_steps": step_ids(required),
        "optional_steps": step_ids(optional),
        "error": None,
    }


def env_assignment_value(text, key):
    """Return the assigned value for KEY, or None. Caller must drop secrets."""
    if not isinstance(text, str) or not isinstance(key, str) or not key:
        return None
    assignments = (f"{key}=", f"export {key}=")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        value = None
        for prefix in assignments:
            if line.startswith(prefix):
                value = line[len(prefix) :]
                break
        if value is None:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value
    return None


def env_key_present(text, key):
    """Return True when KEY has a non-empty value. Never returns the value."""
    value = env_assignment_value(text, key)
    return bool(value and value.strip())


def env_has_any_key(text, keys):
    return any(env_key_present(text, key) for key in keys)


def public_langfuse_base_url(text):
    """Return a non-secret Langfuse URL if one is set. Never returns keys."""
    for key in LANGFUSE_HOST_KEYS:
        value = env_assignment_value(text, key)
        if not value or not value.strip():
            continue
        try:
            return validate_langfuse_base_url(value)
        except ValueError:
            continue
    return None


def plugin_name_lists(config):
    if not isinstance(config, dict):
        return [], []
    plugins = config.get("plugins")
    if not isinstance(plugins, dict):
        return [], []
    enabled = [
        name
        for name in (plugins.get("enabled") or [])
        if isinstance(name, str) and name
    ]
    disabled = [
        name
        for name in (plugins.get("disabled") or [])
        if isinstance(name, str) and name
    ]
    return enabled, disabled


def plugin_is_enabled(name, enabled, disabled):
    if name in disabled:
        return False
    return name in enabled


def installed_plugin_names(plugins_dir, limit=MAX_RUNTIME_ITEMS):
    names = []
    if plugins_dir is None:
        return names
    root = Path(plugins_dir)
    if not root.is_dir():
        return names
    try:
        children = sorted(root.iterdir(), key=lambda item: item.name)
    except OSError:
        return names
    for child in children:
        if child.name in PLUGIN_SKIP_NAMES or child.name.startswith("."):
            continue
        if not child.is_dir():
            continue
        if (child / "plugin.yaml").is_file():
            names.append(child.name)
        else:
            try:
                nested = sorted(child.iterdir(), key=lambda item: item.name)
            except OSError:
                nested = []
            for inner in nested:
                if inner.name in PLUGIN_SKIP_NAMES or inner.name.startswith("."):
                    continue
                if inner.is_dir() and (inner / "plugin.yaml").is_file():
                    names.append(f"{child.name}/{inner.name}")
        if len(names) >= limit:
            break
    return names[:limit]


def opencode_paths_present(paths):
    for path in paths or []:
        candidate = Path(path)
        try:
            if candidate.is_file() or candidate.is_dir():
                return True
        except OSError:
            continue
    return False


def image_has_opencode(record):
    if not isinstance(record, dict):
        return False
    version = record.get("opencode_version")
    return isinstance(version, str) and bool(version)


def load_yaml_mapping(path, missing="Hermes config.yaml is missing"):
    if path is None:
        return None, missing
    candidate = Path(path)
    if candidate.is_symlink():
        return None, "Hermes config.yaml must not be a symlink"
    try:
        text = candidate.read_text()
    except FileNotFoundError:
        return None, missing
    except OSError:
        return None, "Hermes config.yaml is unreadable"
    if yaml is None:
        return None, "Hermes config.yaml parser is unavailable"
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None, "Hermes config.yaml is malformed"
    if not isinstance(data, dict):
        return None, "Hermes config.yaml is malformed"
    return data, None


def load_env_text(path):
    """Read an env file for key-presence checks. Caller must drop the text."""
    if path is None:
        return None, "Hermes env file is missing"
    candidate = Path(path)
    if candidate.is_symlink():
        return None, "Hermes env file must not be a symlink"
    try:
        return candidate.read_text(), None
    except FileNotFoundError:
        return None, "Hermes env file is missing"
    except OSError:
        return None, "Hermes env file is unreadable"


def langfuse_environment_name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Langfuse environment name is required")
    name = value.strip().lower()
    if len(name) > LANGFUSE_ENVIRONMENT_MAX:
        name = name[:LANGFUSE_ENVIRONMENT_MAX].rstrip("-_")
    if not name or not LANGFUSE_ENVIRONMENT_RE.fullmatch(name):
        raise ValueError("Langfuse environment name is invalid")
    return name


def public_langfuse_environment(text):
    for key in LANGFUSE_ENV_NAME_KEYS:
        value = env_assignment_value(text, key)
        if not value or not value.strip():
            continue
        try:
            return langfuse_environment_name(value)
        except ValueError:
            continue
    return None


def langfuse_view(config, env_text, config_error=None, env_error=None):
    keys_set = False
    host_set = False
    base_url = None
    environment = None
    if env_text is not None:
        keys_set = env_has_any_key(env_text, LANGFUSE_PUBLIC_KEYS) and env_has_any_key(
            env_text, LANGFUSE_SECRET_KEYS
        )
        base_url = public_langfuse_base_url(env_text)
        host_set = bool(base_url)
        environment = public_langfuse_environment(env_text)
    snapshot = {
        "status": "unknown",
        "reason": None,
        "keys_set": keys_set,
        "host_set": host_set,
        "base_url": base_url,
        "environment": environment,
        "source": "controller",
    }
    if config_error:
        snapshot["reason"] = config_error
        return snapshot
    if not isinstance(config, dict):
        snapshot["reason"] = "Hermes config.yaml is unavailable"
        return snapshot
    enabled, disabled = plugin_name_lists(config)
    if not plugin_is_enabled(LANGFUSE_PLUGIN, enabled, disabled):
        snapshot["status"] = "disabled"
        return snapshot
    if env_error:
        snapshot["reason"] = env_error
        return snapshot
    if keys_set:
        snapshot["status"] = "enabled"
        return snapshot
    snapshot["reason"] = "Langfuse plugin is enabled but keys are not set"
    return snapshot


def hermes_runtime_view(
    config=None,
    env_text=None,
    *,
    config_error=None,
    env_error=None,
    installed_plugins=None,
    opencode_present=False,
    opencode_source="missing",
    opencode_desired=None,
    opencode_scope="host",
):
    enabled, disabled = plugin_name_lists(config)
    installed = []
    for name in installed_plugins or []:
        if isinstance(name, str) and name and name not in installed:
            installed.append(name)
    items = []

    def add_item(name, kind, present, is_enabled, extra=None):
        item = {
            "name": name,
            "kind": kind,
            "enabled": bool(is_enabled),
            "present": bool(present),
        }
        if extra:
            item.update(extra)
        items.append(item)

    add_item(
        OPENCODE_TOOL,
        "tool",
        bool(opencode_present),
        opencode_is_enabled(opencode_present, opencode_desired),
        opencode_tool_extra(
            present=bool(opencode_present),
            source=opencode_source,
            desired=opencode_desired,
            scope=opencode_scope,
        ),
    )
    add_item(
        LANGFUSE_PLUGIN,
        "plugin",
        LANGFUSE_PLUGIN in installed or LANGFUSE_PLUGIN in BUNDLED_PLUGIN_NAMES,
        plugin_is_enabled(LANGFUSE_PLUGIN, enabled, disabled),
    )
    seen = {OPENCODE_TOOL, LANGFUSE_PLUGIN}
    for name in enabled:
        if name in seen or name in disabled:
            continue
        add_item(
            name,
            "plugin",
            name in installed or name in BUNDLED_PLUGIN_NAMES,
            True,
        )
        seen.add(name)
        if len(items) >= MAX_RUNTIME_ITEMS:
            break
    if len(items) < MAX_RUNTIME_ITEMS:
        for name in installed:
            if name in seen:
                continue
            add_item(
                name,
                "plugin",
                True,
                plugin_is_enabled(name, enabled, disabled),
            )
            seen.add(name)
            if len(items) >= MAX_RUNTIME_ITEMS:
                break
    return {
        "langfuse": langfuse_view(
            config,
            env_text,
            config_error=config_error,
            env_error=env_error,
        ),
        "tools": items[:MAX_RUNTIME_ITEMS],
    }


def inspect_hermes_runtime(
    *,
    config_path=None,
    env_path=None,
    plugins_dirs=None,
    opencode_paths=None,
    opencode_present=False,
    opencode_source="missing",
    opencode_desired_path=None,
    opencode_scope="host",
):
    config, config_error = load_yaml_mapping(config_path)
    env_text, env_error = load_env_text(env_path)
    installed = []
    for directory in plugins_dirs or []:
        for name in installed_plugin_names(directory):
            if name not in installed:
                installed.append(name)
    present = bool(opencode_present) or opencode_paths_present(opencode_paths)
    if opencode_source == "missing" and present:
        opencode_source = "skill"
    view = hermes_runtime_view(
        config,
        env_text,
        config_error=config_error,
        env_error=env_error,
        installed_plugins=installed,
        opencode_present=present,
        opencode_source=opencode_source,
        opencode_desired=load_opencode_desired(opencode_desired_path),
        opencode_scope=opencode_scope,
    )
    return view


def assistant_card(item, live=None):
    if not isinstance(item, dict):
        return None
    assistant_id = item.get("id")
    if not isinstance(assistant_id, str) or not assistant_id:
        return None
    dashboard = item.get("dashboard") if isinstance(item.get("dashboard"), dict) else {}
    resources = item.get("resources") if isinstance(item.get("resources"), dict) else {}
    image = item.get("image") if isinstance(item.get("image"), dict) else {}
    live = live if isinstance(live, dict) else {}
    usage = live.get("usage") if isinstance(live.get("usage"), dict) else {}
    onboarding = item.get("onboarding")
    if isinstance(onboarding, dict) and "rollup" not in onboarding:
        onboarding_view = {
            "status": onboarding.get("status") or "unavailable",
            "required_remaining": onboarding.get("required_remaining"),
            "optional_remaining": onboarding.get("optional_remaining"),
            "required_steps": step_ids(onboarding.get("required_steps")),
            "optional_steps": step_ids(onboarding.get("optional_steps")),
            "error": None,
        }
        if onboarding_view["status"] not in {"pending", "in_progress", "complete"}:
            onboarding_view["status"] = "unavailable"
            onboarding_view["error"] = "onboarding status is unavailable"
    else:
        onboarding_view = onboarding_summary(onboarding, live.get("onboarding_error"))
    health_status = live.get("health_status") or "unknown"
    if health_status not in {"healthy", "running", "stopped", "missing", "unknown"}:
        health_status = "unknown"
    desired_version = image.get("aidee_version")
    if not isinstance(desired_version, str):
        desired_version = None
    installed_version = live.get("image_version")
    if not isinstance(installed_version, str):
        installed_version = desired_version
    return {
        "id": assistant_id,
        "name": item.get("name") or assistant_id,
        "kind": item.get("kind"),
        "registry_status": item.get("status"),
        "dashboard_url": dashboard.get("url"),
        "health": {
            "status": health_status,
            "running": bool(live.get("running")),
            "error": live.get("error"),
        },
        "resources": {
            "limits": {
                "cpu_limit": resources.get("cpu_limit"),
                "memory_mb": resources.get("memory_mb"),
                "pids_limit": resources.get("pids_limit"),
            },
            "usage": {
                "cpu_percent": usage.get("cpu_percent"),
                "memory_mb": usage.get("memory_mb"),
                "error": usage.get("error"),
            },
        },
        "image": {
            "desired_version": desired_version,
            "installed_version": installed_version,
            "image_id": image.get("image_id") if isinstance(image.get("image_id"), str) else None,
        },
        "onboarding": onboarding_view,
        "langfuse": live.get("langfuse")
        if isinstance(live.get("langfuse"), dict)
        else {"status": "unknown", "reason": "Hermes runtime status is unavailable"},
        "tools": live.get("tools") if isinstance(live.get("tools"), list) else [],
    }


def build_overview(
    registry,
    *,
    host,
    release,
    controller_onboarding,
    live_by_id=None,
    warnings=None,
    controller_runtime=None,
):
    """Assemble the Fleet overview payload from already-probed inputs."""
    notes = list(warnings or [])
    assistants = []
    live_by_id = live_by_id if isinstance(live_by_id, dict) else {}
    if not isinstance(registry, dict):
        notes.append("fleet registry is unavailable")
        registry = {}
    raw_assistants = registry.get("assistants")
    if raw_assistants is None:
        raw_assistants = []
    elif not isinstance(raw_assistants, list):
        notes.append("fleet registry assistants are malformed")
        raw_assistants = []
    for item in raw_assistants:
        card = assistant_card(item, live_by_id.get((item or {}).get("id")))
        if card is None:
            notes.append("skipped a malformed assistant registry entry")
            continue
        assistants.append(card)
    platform = registry.get("platform") if isinstance(registry.get("platform"), dict) else {}
    release_view = dict(release or {})
    if not release_view.get("desired"):
        desired = platform.get("desired_release")
        if isinstance(desired, str) and desired:
            release_view["desired"] = desired
    host_view = host if isinstance(host, dict) else {"error": "host capacity is unavailable"}
    runtime = controller_runtime if isinstance(controller_runtime, dict) else {}
    return public_payload(
        {
            "host": host_view,
            "release": release_view,
            "controller": {
                "onboarding": onboarding_summary(controller_onboarding),
                "langfuse": runtime.get("langfuse")
                if isinstance(runtime.get("langfuse"), dict)
                else {
                    "status": "unknown",
                    "reason": "Hermes runtime status is unavailable",
                },
                "tools": runtime.get("tools")
                if isinstance(runtime.get("tools"), list)
                else [],
            },
            "assistants": assistants,
            "warnings": notes,
        }
    )


def validate_langfuse_key(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label} is required")
    stripped = value.strip()
    if "\n" in stripped or "\r" in stripped:
        raise ValueError(f"{label} is invalid")
    if len(stripped) < LANGFUSE_KEY_MIN or len(stripped) > LANGFUSE_KEY_MAX:
        raise ValueError(f"{label} is invalid")
    return stripped


def validate_langfuse_base_url(url):
    if url is None or (isinstance(url, str) and not url.strip()):
        return DEFAULT_LANGFUSE_URL
    if not isinstance(url, str) or "\n" in url or "\r" in url:
        raise ValueError("Langfuse URL is invalid")
    stripped = url.strip()
    parsed = urlparse(stripped)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Langfuse URL must be https")
    if parsed.username or parsed.password:
        raise ValueError("Langfuse URL must not include credentials")
    if parsed.netloc.startswith("[") or " " in stripped:
        raise ValueError("Langfuse URL is invalid")
    return stripped.rstrip("/")


def set_plugin_enabled(config, name, enabled):
    if not isinstance(config, dict):
        config = {}
    plugins = config.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
        config["plugins"] = plugins
    current_enabled = [
        item for item in (plugins.get("enabled") or []) if isinstance(item, str) and item
    ]
    current_disabled = [
        item
        for item in (plugins.get("disabled") or [])
        if isinstance(item, str) and item
    ]
    if enabled:
        if name not in current_enabled:
            current_enabled.append(name)
        current_disabled = [item for item in current_disabled if item != name]
    else:
        current_enabled = [item for item in current_enabled if item != name]
        if name not in current_disabled:
            current_disabled.append(name)
    plugins["enabled"] = current_enabled
    if current_disabled:
        plugins["disabled"] = current_disabled
    elif "disabled" in plugins:
        plugins["disabled"] = []
    return config


def upsert_env(text, updates):
    seen = set()
    lines = []
    current = text if isinstance(text, str) else ""
    for line in current.splitlines():
        replaced = False
        for key, value in updates.items():
            if line.startswith(f"{key}="):
                lines.append(f"{key}={value}")
                seen.add(key)
                replaced = True
                break
        if not replaced:
            lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def remove_env_keys(text, keys):
    names = {key for key in keys if isinstance(key, str) and key}
    if not names:
        return text if isinstance(text, str) else ""
    lines = []
    current = text if isinstance(text, str) else ""
    for line in current.splitlines():
        skip = False
        for key in names:
            if line.startswith(f"{key}=") or line.startswith(f"export {key}="):
                skip = True
                break
        if not skip:
            lines.append(line)
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def langfuse_env_updates(public_key, secret_key, base_url, environment):
    return {
        "HERMES_LANGFUSE_PUBLIC_KEY": public_key,
        "HERMES_LANGFUSE_SECRET_KEY": secret_key,
        "HERMES_LANGFUSE_BASE_URL": base_url,
        LANGFUSE_ENV_KEY: environment,
    }


def first_env_value(text, keys):
    for key in keys:
        value = env_assignment_value(text, key)
        if value and value.strip():
            return value.strip()
    return None


def resolved_langfuse_credentials(env_text):
    """Read stored Hermes Langfuse values. Caller must not return them."""
    public = first_env_value(env_text, LANGFUSE_PUBLIC_KEYS)
    secret = first_env_value(env_text, LANGFUSE_SECRET_KEYS)
    host = public_langfuse_base_url(env_text) or DEFAULT_LANGFUSE_URL
    if not public or not secret:
        return None
    return public, secret, host


def opencode_langfuse_env_updates(
    public_key, secret_key, base_url, environment, config_path=None
):
    return {
        "LANGFUSE_PUBLIC_KEY": public_key,
        "LANGFUSE_SECRET_KEY": secret_key,
        "LANGFUSE_BASEURL": base_url,
        OPENCODE_LANGFUSE_ENV_NAME_KEY: environment,
    }


def opencode_langfuse_credentials_document(env_text, environment=None, user_id=None):
    """Build the official OpenCode credentials file. Caller must not return it."""
    credentials = resolved_langfuse_credentials(env_text)
    if credentials is None:
        return None
    public, secret, host = credentials
    env_name = environment or public_langfuse_environment(env_text)
    if env_name is None:
        raise ValueError("Langfuse environment name is required")
    document = {
        "publicKey": public,
        "secretKey": secret,
        "baseUrl": host,
        "environment": langfuse_environment_name(env_name),
    }
    if user_id:
        document["userId"] = user_id
    return document


def assistant_opencode_host_dir(runtime, container_home=None):
    """Host directory for the OpenCode files the container process reads.

    When HOME is unset or is /opt/data, that is the runtime mount. One copy
    is enough. If HOME is a path under /opt/data, map that relative path.
    """
    runtime = Path(runtime)
    if container_home in (None, ""):
        home = ASSISTANT_CONTAINER_HOME
    else:
        home = Path(container_home)
    if home == ASSISTANT_CONTAINER_HERMES_HOME:
        return runtime / OPENCODE_DIR_RELATIVE
    try:
        relative = home.relative_to(ASSISTANT_CONTAINER_HERMES_HOME)
    except ValueError:
        return runtime / OPENCODE_DIR_RELATIVE
    if not relative.parts:
        return runtime / OPENCODE_DIR_RELATIVE
    return runtime / relative / OPENCODE_DIR_RELATIVE


def opencode_langfuse_keys_to_remove(env_text):
    # Drop OpenCode aliases and older OTEL / OPENCODE_CONFIG copies from the same .env.
    # Keep LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY when they are the only stored credentials.
    keys = ["LANGFUSE_BASEURL", OPENCODE_CONFIG_ENV, OPENCODE_LANGFUSE_ENV_NAME_KEY]
    keys.extend(OPENCODE_OTEL_ENV_KEYS)
    if env_key_present(env_text, "HERMES_LANGFUSE_PUBLIC_KEY"):
        keys.append("LANGFUSE_PUBLIC_KEY")
    if env_key_present(env_text, "HERMES_LANGFUSE_SECRET_KEY"):
        keys.append("LANGFUSE_SECRET_KEY")
    return keys


def apply_opencode_langfuse_env(env_text, config_path=None, environment=None):
    credentials = resolved_langfuse_credentials(env_text)
    if credentials is None:
        return env_text if isinstance(env_text, str) else ""
    public, secret, host = credentials
    env_name = environment or public_langfuse_environment(env_text)
    if env_name is None:
        raise ValueError("Langfuse environment name is required")
    env_name = langfuse_environment_name(env_name)
    next_env = upsert_env(
        env_text if isinstance(env_text, str) else "",
        {
            LANGFUSE_ENV_KEY: env_name,
            **opencode_langfuse_env_updates(
                public, secret, host, env_name, config_path
            ),
        },
    )
    leftover = list(OPENCODE_OTEL_ENV_KEYS)
    leftover.append(OPENCODE_CONFIG_ENV)
    return remove_env_keys(next_env, leftover)


def strip_opencode_langfuse_env(env_text):
    current = env_text if isinstance(env_text, str) else ""
    return remove_env_keys(current, opencode_langfuse_keys_to_remove(current))


def apply_langfuse_settings(
    config,
    env_text,
    *,
    enabled,
    public_key=None,
    secret_key=None,
    base_url=None,
    environment=None,
    opencode_enabled=False,
    opencode_config_path=None,
    keep_keys=True,
):
    next_config = set_plugin_enabled(dict(config or {}), LANGFUSE_PLUGIN, enabled)
    current = env_text if isinstance(env_text, str) else ""
    if not enabled:
        next_env = strip_opencode_langfuse_env(current)
        next_env = remove_env_keys(next_env, LANGFUSE_ENV_NAME_KEYS)
        if not keep_keys:
            next_env = remove_env_keys(next_env, LANGFUSE_INSTALL_KEYS)
        return next_config, next_env
    stored = resolved_langfuse_credentials(current)
    if public_key or secret_key:
        public = validate_langfuse_key(public_key, "Langfuse public key")
        secret = validate_langfuse_key(secret_key, "Langfuse secret key")
        host = validate_langfuse_base_url(base_url)
    elif stored is not None:
        public, secret, host = stored
        if base_url:
            host = validate_langfuse_base_url(base_url)
    else:
        raise ValueError("Langfuse public key and secret key are required")
    env_name = langfuse_environment_name(
        environment or public_langfuse_environment(current)
    )
    next_env = upsert_env(current, langfuse_env_updates(public, secret, host, env_name))
    if opencode_enabled:
        next_env = apply_opencode_langfuse_env(
            next_env, opencode_config_path, environment=env_name
        )
    else:
        next_env = strip_opencode_langfuse_env(next_env)
    return next_config, next_env


def apply_install_langfuse(
    config,
    env_text,
    *,
    enabled,
    credentials=None,
    environment,
    opencode_enabled=False,
    opencode_config_path=None,
    keep_keys=True,
):
    public = secret = host = None
    if credentials:
        public, secret, host = credentials
    return apply_langfuse_settings(
        config,
        env_text,
        enabled=enabled,
        public_key=public,
        secret_key=secret,
        base_url=host,
        environment=environment,
        opencode_enabled=opencode_enabled,
        opencode_config_path=opencode_config_path,
        keep_keys=keep_keys,
    )


def load_install_langfuse(config, env_text, config_error=None, env_error=None):
    view = langfuse_view(
        config, env_text, config_error=config_error, env_error=env_error
    )
    credentials = (
        resolved_langfuse_credentials(env_text) if env_text is not None else None
    )
    enabled = view.get("status") == "enabled" and credentials is not None
    return {
        "enabled": enabled,
        "credentials": credentials,
        "view": view,
    }


def controller_langfuse_paths(state_root):
    root = Path(state_root)
    preferred = root / "controller-home" / ".hermes"
    fallback = root / "controller"
    home = (
        preferred
        if preferred.is_dir() or (preferred / "config.yaml").is_file()
        else fallback
    )
    return home / "config.yaml", home / ".env"


def load_controller_install_langfuse(state_root):
    config_path, env_path = controller_langfuse_paths(state_root)
    config, config_error = load_yaml_mapping(config_path)
    env_text, env_error = load_env_text(env_path)
    return load_install_langfuse(
        config, env_text, config_error=config_error, env_error=env_error
    )


def apply_opencode_instruction(text, enabled):
    current = text if isinstance(text, str) else ""
    stripped = OPENCODE_INSTRUCTION_RE.sub("\n", current).rstrip() + "\n"
    if not enabled:
        return stripped
    return stripped + "\n" + OPENCODE_INSTRUCTION_BLOCK


def apply_tracing_instruction(text, enabled):
    current = text if isinstance(text, str) else ""
    stripped = TRACING_INSTRUCTION_RE.sub("\n", current).rstrip() + "\n"
    if not enabled:
        return stripped
    return stripped + "\n" + TRACING_INSTRUCTION_BLOCK


def load_opencode_config(path):
    if path is None:
        return {}
    candidate = Path(path)
    try:
        data = json.loads(candidate.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def apply_opencode_config(data, tracing):
    config = dict(data) if isinstance(data, dict) else {}
    experimental = config.get("experimental")
    if not isinstance(experimental, dict):
        experimental = {}
    else:
        experimental = dict(experimental)
    experimental["openTelemetry"] = bool(tracing)
    config["experimental"] = experimental
    plugins = [
        name
        for name in (config.get("plugin") or [])
        if isinstance(name, str)
        and "opencode-observability-plugin" not in name
        and name != "opencode-plugin-langfuse"
    ]
    if tracing:
        plugins.append(OPENCODE_LANGFUSE_PLUGIN)
    config["plugin"] = plugins
    return config


def load_opencode_desired(path):
    if path is None:
        return None
    candidate = Path(path)
    try:
        data = json.loads(candidate.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    desired = data.get("desired")
    if desired in {"installed", "absent"}:
        return desired
    return None


def opencode_desired_document(desired):
    if desired not in {"installed", "absent"}:
        raise ValueError("OpenCode desired state is invalid")
    return {"desired": desired}


def opencode_is_enabled(present, desired):
    if desired == "absent":
        return False
    if desired == "installed":
        return True
    return bool(present)


def opencode_tool_extra(*, present, source, desired, scope):
    source = source if source in {"host", "image", "skill", "missing"} else "missing"
    desired = desired if desired in {"installed", "absent"} else None
    enabled = opencode_is_enabled(present, desired)
    if scope == "image":
        can_install = not present or desired == "absent"
        can_uninstall = bool(present) or desired != "absent"
        if not present:
            note = (
                "This assistant image does not include OpenCode. "
                "Update to an image that pins OpenCode."
            )
        elif enabled:
            note = (
                "OpenCode is pinned in the assistant image. Hermes plans and "
                "investigates, then delegates coding to OpenCode. Disable removes "
                "that instruction and the skill. The CLI stays in the image."
            )
        else:
            note = (
                "The OpenCode CLI stays in the assistant image. Coding delegation "
                "is off until you enable OpenCode."
            )
    else:
        can_install = not present or desired == "absent"
        can_uninstall = bool(present) or desired == "installed"
        if enabled:
            note = (
                "OpenCode is on the controller PATH. Hermes plans and investigates, "
                "then delegates coding to OpenCode."
            )
        else:
            note = (
                "Install OpenCode on the controller host with the pinned npm package. "
                "Hermes will then delegate coding to it."
            )
    return {
        "source": source,
        "desired": desired or ("installed" if present else "absent"),
        "can_install": can_install,
        "can_uninstall": can_uninstall,
        "note": note,
        "scope": scope,
    }
