import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

try:
    from fastapi import APIRouter, HTTPException
except ImportError:
    APIRouter = None
    HTTPException = None

try:
    import yaml
except ImportError:
    yaml = None


MAX_MEMORY_BYTES = 65536
MAX_RUNTIME_ITEMS = 16
LANGFUSE_PLUGIN = "observability/langfuse"
OPENCODE_TOOL = "opencode"
BUNDLED_PLUGIN_NAMES = frozenset({LANGFUSE_PLUGIN})
PLUGIN_SKIP_NAMES = frozenset(
    {"__pycache__", "node_modules", "src", "dashboard", "dist"}
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
LANGFUSE_ENV_NAME_KEYS = (LANGFUSE_ENV_KEY, OPENCODE_LANGFUSE_ENV_NAME_KEY)
LANGFUSE_ENVIRONMENT_MAX = 40
LANGFUSE_ENVIRONMENT_RE = re.compile(r"^(?!langfuse)[a-z0-9_-]+$")
OPENCODE_SKILL_PATHS = (
    "skills/autonomous-ai-agents/opencode/SKILL.md",
    "skills/opencode/SKILL.md",
)
OPENCODE_DESIRED_RELATIVE = Path("aidee/opencode.json")
OPENCODE_RUNTIME_SKILL = Path("skills/opencode/SKILL.md")
OPENCODE_DIR_RELATIVE = Path(".config/opencode")
OPENCODE_CONFIG_RELATIVE = OPENCODE_DIR_RELATIVE / "opencode.json"
OPENCODE_CREDENTIALS_RELATIVE = OPENCODE_DIR_RELATIVE / "opencode-langfuse.json"
OPENCODE_CONFIG_ENV = "OPENCODE_CONFIG"
OPENCODE_LANGFUSE_PLUGIN = "@langfuse/opencode-observability-plugin@latest"
OPENCODE_LANGFUSE_ENV_KEYS = (
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASEURL",
    OPENCODE_LANGFUSE_ENV_NAME_KEY,
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
router = APIRouter() if APIRouter is not None else None


def data_root(root=None):
    if root is not None:
        return Path(root)
    return Path(os.environ.get("HERMES_HOME", "/opt/data"))


def read_fixed_text(path, limit=MAX_MEMORY_BYTES):
    if path.is_symlink():
        return {
            "present": False,
            "content": "",
            "truncated": False,
            "bytes": 0,
            "error": "memory file must not be a symlink",
        }
    if not path.is_file():
        return {"present": False, "content": "", "truncated": False, "bytes": 0}
    data = path.read_bytes()
    truncated = len(data) > limit
    text = data[:limit].decode("utf-8", errors="replace")
    return {
        "present": True,
        "content": text,
        "truncated": truncated,
        "bytes": min(len(data), limit),
    }


def load_profile(root):
    path = root / "aidee" / "profile.json"
    if path.is_symlink():
        return None, "assistant profile must not be a symlink"
    if not path.is_file():
        return None, "assistant profile is missing"
    try:
        profile = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None, "assistant profile is malformed"
    if not isinstance(profile, dict):
        return None, "assistant profile is malformed"
    allowed = {
        "schema_version",
        "id",
        "name",
        "kind",
        "purpose",
        "projects",
        "capabilities",
    }
    return {key: profile[key] for key in allowed if key in profile}, None


def env_assignment_value(text, key):
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
    value = env_assignment_value(text, key)
    return bool(value and value.strip())


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


def installed_plugin_names(plugins_dir):
    names = []
    if plugins_dir is None or not plugins_dir.is_dir():
        return names
    try:
        children = sorted(plugins_dir.iterdir(), key=lambda item: item.name)
    except OSError:
        return names
    for child in children:
        if child.name in PLUGIN_SKIP_NAMES or child.name.startswith("."):
            continue
        if not child.is_dir():
            continue
        if (child / "plugin.yaml").is_file():
            names.append(child.name)
            continue
        try:
            nested = sorted(child.iterdir(), key=lambda item: item.name)
        except OSError:
            continue
        for inner in nested:
            if inner.name in PLUGIN_SKIP_NAMES or inner.name.startswith("."):
                continue
            if inner.is_dir() and (inner / "plugin.yaml").is_file():
                names.append(f"{child.name}/{inner.name}")
        if len(names) >= MAX_RUNTIME_ITEMS:
            break
    return names[:MAX_RUNTIME_ITEMS]


def load_hermes_config(path):
    if path.is_symlink():
        return None, "Hermes config.yaml must not be a symlink"
    if not path.is_file():
        return None, "Hermes config.yaml is missing"
    if yaml is None:
        return None, "Hermes config.yaml parser is unavailable"
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError):
        return None, "Hermes config.yaml is malformed"
    if not isinstance(data, dict):
        return None, "Hermes config.yaml is malformed"
    return data, None


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
    return stripped.rstrip("/")


def public_langfuse_base_url(text):
    for key in LANGFUSE_HOST_KEYS:
        value = env_assignment_value(text, key)
        if not value or not value.strip():
            continue
        try:
            return validate_langfuse_base_url(value)
        except ValueError:
            continue
    return None


def langfuse_from_files(config, config_error, env_path):
    env_text = None
    env_error = None
    if env_path.is_symlink():
        env_error = "Hermes env file must not be a symlink"
    else:
        try:
            env_text = env_path.read_text()
        except FileNotFoundError:
            env_error = "Hermes env file is missing"
        except OSError:
            env_error = "Hermes env file is unreadable"
    keys_set = False
    host_set = False
    base_url = None
    if env_text is not None:
        keys_set = any(
            env_key_present(env_text, key) for key in LANGFUSE_PUBLIC_KEYS
        ) and any(env_key_present(env_text, key) for key in LANGFUSE_SECRET_KEYS)
        base_url = public_langfuse_base_url(env_text)
        host_set = bool(base_url)
    environment = None
    if env_text is not None:
        for key in LANGFUSE_ENV_NAME_KEYS:
            value = env_assignment_value(env_text, key)
            if not value or not value.strip():
                continue
            name = value.strip().lower()
            if len(name) > LANGFUSE_ENVIRONMENT_MAX:
                name = name[:LANGFUSE_ENVIRONMENT_MAX].rstrip("-_")
            if name and LANGFUSE_ENVIRONMENT_RE.fullmatch(name):
                environment = name
                break
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


def load_opencode_desired(path):
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    desired = data.get("desired")
    return desired if desired in {"installed", "absent"} else None


def opencode_is_present(root):
    if shutil.which("opencode"):
        return True
    for relative in OPENCODE_SKILL_PATHS:
        if (root / relative).is_file():
            return True
        if (Path("/opt/hermes") / relative).is_file():
            return True
    return False


def opencode_tool_item(root, present):
    desired = load_opencode_desired(root / OPENCODE_DESIRED_RELATIVE)
    source = "image" if present else "missing"
    enabled = False if desired == "absent" else bool(present or desired == "installed")
    if present:
        note = (
            "OpenCode is pinned in this assistant image. Hermes plans and "
            "investigates, then delegates coding to OpenCode. Disable removes "
            "that instruction and the skill. The CLI stays in the image."
        )
        can_install = desired == "absent"
        can_uninstall = True
    else:
        note = (
            "This assistant image does not include OpenCode. "
            "Update the image to install the CLI."
        )
        can_install = False
        can_uninstall = False
    if present and desired == "absent":
        note = (
            "The OpenCode CLI stays in the assistant image. Coding delegation "
            "is off until you enable OpenCode."
        )
    return {
        "name": OPENCODE_TOOL,
        "kind": "tool",
        "enabled": enabled,
        "present": bool(present),
        "source": source,
        "desired": desired or ("installed" if present else "absent"),
        "can_install": can_install,
        "can_uninstall": can_uninstall,
        "note": note,
        "scope": "image",
    }


def tools_from_files(config, installed, root, opencode_present):
    enabled, disabled = plugin_name_lists(config)
    items = [
        opencode_tool_item(root, opencode_present),
        {
            "name": LANGFUSE_PLUGIN,
            "kind": "plugin",
            "enabled": plugin_is_enabled(LANGFUSE_PLUGIN, enabled, disabled),
            "present": LANGFUSE_PLUGIN in installed
            or LANGFUSE_PLUGIN in BUNDLED_PLUGIN_NAMES,
        },
    ]
    seen = {OPENCODE_TOOL, LANGFUSE_PLUGIN}
    for name in enabled:
        if name in seen or name in disabled:
            continue
        items.append(
            {
                "name": name,
                "kind": "plugin",
                "enabled": True,
                "present": name in installed or name in BUNDLED_PLUGIN_NAMES,
            }
        )
        seen.add(name)
        if len(items) >= MAX_RUNTIME_ITEMS:
            return items[:MAX_RUNTIME_ITEMS]
    for name in installed:
        if name in seen:
            continue
        items.append(
            {
                "name": name,
                "kind": "plugin",
                "enabled": plugin_is_enabled(name, enabled, disabled),
                "present": True,
            }
        )
        seen.add(name)
        if len(items) >= MAX_RUNTIME_ITEMS:
            break
    return items[:MAX_RUNTIME_ITEMS]


def load_runtime_status(root):
    config, config_error = load_hermes_config(root / "config.yaml")
    installed = installed_plugin_names(root / "plugins")
    bundled = Path("/opt/hermes/plugins")
    if bundled.is_dir():
        for name in installed_plugin_names(bundled):
            if name not in installed:
                installed.append(name)
    present = opencode_is_present(root)
    return {
        "langfuse": langfuse_from_files(config, config_error, root / ".env"),
        "tools": tools_from_files(config, installed, root, present),
    }


ONBOARDING_UNAVAILABLE = {
    "status": "unavailable",
    "required_remaining": None,
    "optional_remaining": None,
    "required_steps": [],
    "optional_steps": [],
    "error": None,
}


def step_ids(items):
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, str) and item]


def onboarding_from_files(root):
    path = root / "aidee" / "onboarding-status.json"
    view = dict(ONBOARDING_UNAVAILABLE)
    if path.is_symlink():
        view["error"] = "onboarding status must not be a symlink"
        return view
    if not path.is_file():
        view["error"] = "onboarding status is missing"
        return view
    try:
        status = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        view["error"] = "onboarding status is malformed"
        return view
    if not isinstance(status, dict):
        view["error"] = "onboarding status is malformed"
        return view
    rollup = status.get("rollup")
    if not isinstance(rollup, dict):
        view["error"] = "onboarding status is malformed"
        return view
    required = rollup.get("incomplete_required")
    optional = rollup.get("incomplete_optional")
    if not isinstance(required, list) or not isinstance(optional, list):
        view["error"] = "onboarding status is malformed"
        return view
    label = rollup.get("status")
    if label not in {"pending", "in_progress", "complete"}:
        view["error"] = "onboarding status is malformed"
        return view
    return {
        "status": label,
        "required_remaining": len(required),
        "optional_remaining": len(optional),
        "required_steps": step_ids(required),
        "optional_steps": step_ids(optional),
        "error": None,
    }


def load_home(root=None):
    base = data_root(root)
    memories = base / "memories"
    profile, profile_error = load_profile(base)
    runtime = load_runtime_status(base)
    return {
        "profile": profile,
        "profile_error": profile_error,
        "user_md": read_fixed_text(memories / "USER.md"),
        "memory_md": read_fixed_text(memories / "MEMORY.md"),
        "onboarding": onboarding_from_files(base),
        "langfuse": runtime["langfuse"],
        "tools": runtime["tools"],
    }


def write_text(path, text, mode=0o660):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"managed file must not be a symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


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
    plugins["disabled"] = current_disabled
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


def first_env_value(text, keys):
    for key in keys:
        value = env_assignment_value(text, key)
        if value and value.strip():
            return value.strip()
    return None


def resolved_langfuse_credentials(env_text):
    public = first_env_value(env_text, LANGFUSE_PUBLIC_KEYS)
    secret = first_env_value(env_text, LANGFUSE_SECRET_KEYS)
    host = public_langfuse_base_url(env_text) or DEFAULT_LANGFUSE_URL
    if not public or not secret:
        return None
    return public, secret, host


def apply_opencode_instruction(text, enabled):
    current = text if isinstance(text, str) else ""
    stripped = OPENCODE_INSTRUCTION_RE.sub("\n", current).rstrip() + "\n"
    if not enabled:
        return stripped
    return stripped + "\n" + OPENCODE_INSTRUCTION_BLOCK


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


def opencode_langfuse_env_updates(
    public_key, secret_key, base_url, environment, config_path=None
):
    return {
        "LANGFUSE_PUBLIC_KEY": public_key,
        "LANGFUSE_SECRET_KEY": secret_key,
        "LANGFUSE_BASEURL": base_url,
        OPENCODE_LANGFUSE_ENV_NAME_KEY: environment,
    }


def opencode_langfuse_keys_to_remove(env_text):
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
    env_name = environment
    if env_name is None and isinstance(env_text, str):
        for key in LANGFUSE_ENV_NAME_KEYS:
            value = env_assignment_value(env_text, key)
            if value and value.strip():
                env_name = value.strip().lower()
                break
    if not env_name:
        raise ValueError("Langfuse environment name is required")
    next_env = upsert_env(
        env_text if isinstance(env_text, str) else "",
        opencode_langfuse_env_updates(public, secret, host, env_name, config_path),
    )
    leftover = list(OPENCODE_OTEL_ENV_KEYS)
    leftover.append(OPENCODE_CONFIG_ENV)
    return remove_env_keys(next_env, leftover)


def opencode_langfuse_credentials_document(env_text, environment=None, user_id=None):
    credentials = resolved_langfuse_credentials(env_text)
    if credentials is None:
        return None
    public, secret, host = credentials
    env_name = environment
    if env_name is None and isinstance(env_text, str):
        for key in LANGFUSE_ENV_NAME_KEYS:
            value = env_assignment_value(env_text, key)
            if value and value.strip():
                env_name = value.strip().lower()
                break
    if not env_name:
        raise ValueError("Langfuse environment name is required")
    document = {
        "publicKey": public,
        "secretKey": secret,
        "baseUrl": host,
        "environment": env_name,
    }
    if user_id:
        document["userId"] = user_id
    return document


def strip_opencode_langfuse_env(env_text):
    current = env_text if isinstance(env_text, str) else ""
    return remove_env_keys(current, opencode_langfuse_keys_to_remove(current))


def write_opencode_config_file(root, tracing):
    path = root / OPENCODE_CONFIG_RELATIVE
    if not tracing and not path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    current = {}
    if path.is_file() and not path.is_symlink():
        try:
            loaded = json.loads(path.read_text())
            if isinstance(loaded, dict):
                current = loaded
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            current = {}
    write_text(path, json.dumps(apply_opencode_config(current, tracing), indent=2) + "\n")


def remove_managed_file(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"managed file must not be a symlink: {path}")
    if path.is_file():
        path.unlink()


def write_opencode_credentials_file(root, tracing, env_text, environment=None):
    path = Path(root) / OPENCODE_CREDENTIALS_RELATIVE
    if not tracing:
        remove_managed_file(path)
        return
    document = opencode_langfuse_credentials_document(
        env_text, environment=environment
    )
    if document is None:
        remove_managed_file(path)
        return
    write_text(path, json.dumps(document, indent=2) + "\n", 0o600)


def patch_soul_opencode(root, enabled):
    path = root / "SOUL.md"
    if path.is_symlink() or not path.is_file():
        return
    current = path.read_text()
    next_text = apply_opencode_instruction(current, enabled)
    if next_text != current:
        write_text(path, next_text)


def opencode_enabled_from_root(root, present):
    desired = load_opencode_desired(root / OPENCODE_DESIRED_RELATIVE)
    if desired == "absent":
        return False
    if desired == "installed":
        return True
    return bool(present)


def save_langfuse(root, payload):
    raise ValueError("Langfuse keys are set on the controller dashboard")


def save_opencode(root, payload):
    if not isinstance(payload, dict):
        raise ValueError("OpenCode request is invalid")
    action = payload.get("action")
    if action not in {"install", "uninstall"}:
        raise ValueError("OpenCode action is invalid")
    present = opencode_is_present(root)
    desired_path = root / OPENCODE_DESIRED_RELATIVE
    skill_path = root / OPENCODE_RUNTIME_SKILL
    config_file = root / OPENCODE_CONFIG_RELATIVE
    env_path = root / ".env"
    if action == "install":
        if not present:
            raise ValueError(
                "This assistant image does not include OpenCode. "
                "Update the image to install the CLI."
            )
        write_text(skill_path, OPENCODE_SKILL_BODY)
        write_text(
            desired_path,
            json.dumps({"desired": "installed"}, indent=2) + "\n",
        )
        patch_soul_opencode(root, True)
        note = (
            "OpenCode is usable for this assistant. The CLI stays in the image. "
            "Hermes will plan and investigate, then delegate coding to OpenCode."
        )
        enabled = True
    else:
        if skill_path.is_symlink():
            raise ValueError("managed file must not be a symlink")
        if skill_path.is_file():
            skill_path.unlink()
        write_text(
            desired_path,
            json.dumps({"desired": "absent"}, indent=2) + "\n",
        )
        patch_soul_opencode(root, False)
        if present:
            note = (
                "The OpenCode CLI stays in the assistant image. "
                "The coding-delegation instruction and skill are off until you enable OpenCode again."
            )
        else:
            note = "OpenCode is not in this assistant image."
        enabled = False
    runtime = load_runtime_status(root)
    tracing = enabled and runtime["langfuse"].get("status") == "enabled"
    current = env_path.read_text() if env_path.is_file() else ""
    environment = None
    if tracing:
        environment = runtime["langfuse"].get("environment")
        if not environment:
            profile, _ = load_profile(root)
            if profile and profile.get("id"):
                environment = profile["id"]
        next_env = apply_opencode_langfuse_env(
            current, config_file, environment=environment
        )
    else:
        next_env = strip_opencode_langfuse_env(current)
    if next_env != current:
        write_text(env_path, next_env, 0o600)
    write_opencode_config_file(root, tracing)
    write_opencode_credentials_file(root, tracing, next_env, environment=environment)
    runtime = load_runtime_status(root)
    return {
        "status": "updated",
        "action": action,
        "note": note,
        "tools": runtime["tools"],
    }


def home():
    return load_home()


def _http_error(status, detail):
    if HTTPException is None:
        raise ValueError(detail)
    raise HTTPException(status_code=status, detail=detail)


if router is not None:
    router.add_api_route("/home", home, methods=["GET"])

    @router.post("/langfuse")
    def langfuse(payload: dict):
        try:
            return save_langfuse(data_root(), payload)
        except ValueError as error:
            _http_error(400, str(error))

    @router.post("/opencode")
    def opencode(payload: dict):
        try:
            return save_opencode(data_root(), payload)
        except ValueError as error:
            _http_error(400, str(error))
