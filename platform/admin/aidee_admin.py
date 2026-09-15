#!/usr/bin/env python3
import hashlib
import json
import os
import pwd
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from assistant_state import (
    CONTAINER_UID,
    PROFILE_RELATIVE_PATH,
    USER_PLUGINS,
    apply_install_langfuse_files,
    apply_published_dashboard_url,
    build_assistant_profile,
    build_soul_document,
    dashboard_hostname,
    default_assistant_config,
    default_onboarding_status,
    install_assistant_plugins,
    mark_step,
    normalize_dashboard_url,
)
from fleet_status import (
    ASSISTANT_CONTAINER_HOME,
    CONTROLLER_LANGFUSE_ENVIRONMENT,
    OPENCODE_CONFIG_RELATIVE,
    OPENCODE_CREDENTIALS_RELATIVE,
    OPENCODE_DESIRED_RELATIVE,
    OPENCODE_PACKAGE,
    OPENCODE_RUNTIME_SKILL,
    OPENCODE_SKILL_BODY,
    OPENCODE_SKILL_PATHS,
    OPENCODE_VERSION,
    apply_langfuse_settings,
    apply_opencode_config,
    apply_opencode_instruction,
    apply_opencode_langfuse_env,
    apply_tracing_instruction,
    assistant_opencode_host_dir,
    build_overview,
    image_has_opencode,
    inspect_hermes_runtime,
    langfuse_environment_name,
    load_controller_install_langfuse,
    load_opencode_config,
    load_opencode_desired,
    opencode_desired_document,
    opencode_is_enabled,
    opencode_langfuse_credentials_document,
    parse_disk_usage,
    parse_docker_inspect,
    parse_docker_stats,
    parse_meminfo,
    public_payload,
    strip_opencode_langfuse_env,
    upsert_env,
)


SOURCE_ROOT = Path(os.environ.get("AIDEE_SOURCE_ROOT", "/opt/aidee/source"))
STATE_ROOT = Path(os.environ.get("AIDEE_STATE_ROOT", "/var/lib/aidee"))
IMAGE_RECORD_ROOT = Path(
    os.environ.get("AIDEE_IMAGE_RECORD_ROOT", "/etc/aidee/images")
)
OWNER_RECORD = Path(os.environ.get("AIDEE_OWNER_RECORD", "/etc/aidee/owner.json"))
SOCKET_PATH = Path(os.environ.get("AIDEE_ADMIN_SOCKET", "/run/aidee/admin.sock"))
CONTROLLER_USER = os.environ.get("AIDEE_CONTROLLER_USER", "aidee-controller")
MAX_REQUEST_BYTES = 65536
ASSISTANT_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
DASHBOARD_USERNAME = "aidee"
DASHBOARD_USERNAME_KEY = "HERMES_DASHBOARD_BASIC_AUTH_USERNAME"
DASHBOARD_PASSWORD_KEY = "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD"
DASHBOARD_PASSWORD_HASH_KEY = "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH"
DASHBOARD_SECRET_KEY = "HERMES_DASHBOARD_BASIC_AUTH_SECRET"
DASHBOARD_TTL_KEY = "HERMES_DASHBOARD_BASIC_AUTH_TTL_SECONDS"
DASHBOARD_TTL_SECONDS = 2592000
DASHBOARD_USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
GATEWAY_SERVICE = "hermes-gateway.service"
HASHED_REQUEST_KEYS = ("public_key", "secret_key", "publicKey", "secretKey")


class AdminError(RuntimeError):
    pass


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise AdminError(f"{command[0]} failed: {detail}")
    return result.stdout.strip()


def controller_identity():
    account = pwd.getpwnam(CONTROLLER_USER)
    return account.pw_uid, account.pw_gid


def load_json(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as error:
        raise AdminError(f"required file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise AdminError(f"invalid JSON file: {path}") from error


def validate_request(request):
    schema = load_json(SOURCE_ROOT / "platform/schemas/assistant-request.schema.json")
    try:
        jsonschema.validate(request, schema)
    except jsonschema.ValidationError as error:
        raise AdminError(f"invalid request: {error.message}") from error
    return request


def safe_assistant_id(assistant_id):
    if not isinstance(assistant_id, str) or not ASSISTANT_ID.fullmatch(assistant_id):
        raise AdminError("invalid assistant ID")
    return assistant_id


def ensure_directory(path, uid, gid, mode):
    if path.is_symlink():
        raise AdminError(f"managed directory must not be a symlink: {path}")
    if path.exists() and not path.is_dir():
        raise AdminError(f"managed directory path is not a directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, mode)
    os.chown(path, uid, gid)


def write_text(path, text, uid, gid, mode=0o660):
    if path.is_symlink():
        raise AdminError(f"managed file must not be a symlink: {path}")
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
        os.chown(temporary, uid, gid)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def env_value(text, key):
    prefix = f"{key}="
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    return None


def controller_dashboard_credentials():
    candidates = []
    override_env = os.environ.get("AIDEE_CONTROLLER_ENV")
    if override_env:
        candidates.append(Path(override_env))
    override_home = os.environ.get("AIDEE_CONTROLLER_HOME")
    if override_home:
        candidates.append(Path(override_home) / ".hermes" / ".env")
    candidates.append(STATE_ROOT / "controller-home" / ".hermes" / ".env")
    candidates.append(STATE_ROOT / "controller" / ".env")

    for candidate in candidates:
        if candidate.is_file():
            try:
                content = candidate.read_text()
            except OSError:
                continue
            username = env_value(content, DASHBOARD_USERNAME_KEY)
            password = env_value(content, DASHBOARD_PASSWORD_KEY)
            password_hash = env_value(content, DASHBOARD_PASSWORD_HASH_KEY)
            secret = env_value(content, DASHBOARD_SECRET_KEY)
            ttl = env_value(content, DASHBOARD_TTL_KEY)
            if username and (password or password_hash):
                creds = {"username": username}
                if password:
                    creds["password"] = password
                if password_hash:
                    creds["password_hash"] = password_hash
                if secret:
                    creds["secret"] = secret
                if ttl:
                    creds["ttl"] = ttl
                return creds
    return None


def controller_telegram_home_channel():
    candidates = []
    override_config = os.environ.get("AIDEE_CONTROLLER_CONFIG")
    if override_config:
        candidates.append(Path(override_config))
    override_home = os.environ.get("AIDEE_CONTROLLER_HOME")
    if override_home:
        candidates.append(Path(override_home) / ".hermes" / "config.yaml")
    candidates.append(STATE_ROOT / "controller-home" / ".hermes" / "config.yaml")
    candidates.append(STATE_ROOT / "controller" / "config.yaml")

    for candidate in candidates:
        if candidate.is_file():
            try:
                data = yaml.safe_load(candidate.read_text())
                if isinstance(data, dict):
                    home_chan = (
                        data.get("platforms", {})
                        .get("telegram", {})
                        .get("home_channel")
                    )
                    if home_chan and isinstance(home_chan, dict):
                        return home_chan
            except Exception:
                continue

    try:
        owner = load_json(OWNER_RECORD)
        if isinstance(owner, dict):
            if "home_channel" in owner and isinstance(owner["home_channel"], dict):
                return owner["home_channel"]
            tid = (
                owner.get("telegram_id")
                or owner.get("telegram_user_id")
                or owner.get("chat_id")
            )
            if tid:
                name = owner.get("name") or "Owner"
                return {
                    "platform": "telegram",
                    "chat_id": str(tid),
                    "name": name,
                    "user_id": str(tid),
                }
    except Exception:
        pass

    return None


def ensure_runtime_tree_permissions(root_path, uid, gid):
    for dirpath, dirnames, filenames in os.walk(root_path):
        current_dir = Path(dirpath)
        try:
            os.chmod(current_dir, 0o770)
            os.chown(current_dir, uid, gid)
        except OSError:
            pass
        for filename in filenames:
            file_path = current_dir / filename
            try:
                os.chown(file_path, uid, gid)
            except OSError:
                pass


def image_record(version):
    record = load_json(IMAGE_RECORD_ROOT / f"{version}.json")
    image_id = record.get("image_id")
    if not isinstance(image_id, str) or not re.fullmatch(
        r"sha256:[a-f0-9]{64}", image_id
    ):
        raise AdminError("approved image record has an invalid image ID")
    if record.get("validation") != "validated":
        raise AdminError("approved image has not passed validation")
    actual_version = run(
        [
            "docker",
            "image",
            "inspect",
            image_id,
            "--format",
            '{{index .Config.Labels "org.opencontainers.image.version"}}',
        ]
    )
    if actual_version != version:
        raise AdminError("approved image label does not match requested version")
    installed_commit = run(["git", "-C", str(SOURCE_ROOT), "rev-parse", "HEAD"])
    if record.get("source_commit") != installed_commit:
        raise AdminError("approved image record does not match installed source")
    actual_commit = run(
        [
            "docker",
            "image",
            "inspect",
            image_id,
            "--format",
            '{{index .Config.Labels "org.opencontainers.image.revision"}}',
        ]
    )
    if actual_commit != installed_commit:
        raise AdminError("approved image label does not match installed source")
    return record


def owner_name():
    owner = load_json(OWNER_RECORD)
    name = owner.get("name")
    if not isinstance(name, str) or not name.strip():
        raise AdminError("owner record is invalid")
    return name


def sync_shared_skills(source_root, runtime_dir, uid, gid):
    shared_skills_dir = source_root / "platform" / "shared-skills"
    if not shared_skills_dir.is_dir():
        return
    skills_dir = runtime_dir / "skills"
    ensure_directory(skills_dir, uid, gid, 0o770)
    for item in sorted(shared_skills_dir.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        if not (item / "SKILL.md").is_file():
            continue
        dest_dir = skills_dir / item.name
        ensure_directory(dest_dir, uid, gid, 0o770)
        for subpath in item.rglob("*"):
            rel_path = subpath.relative_to(item)
            dest_subpath = dest_dir / rel_path
            if subpath.is_dir():
                ensure_directory(dest_subpath, uid, gid, 0o770)
            elif subpath.is_file():
                write_text(dest_subpath, subpath.read_text(), uid, gid, 0o660)


def create_assistant_state(assistant, image_id, dashboard_url):
    controller_uid, controller_gid = controller_identity()
    assistant_id = safe_assistant_id(assistant["id"])
    fleet_dir = STATE_ROOT / f"fleet/assistants/{assistant_id}"
    runtime_dir = STATE_ROOT / f"runtime/assistants/{assistant_id}/data"
    secret_dir = STATE_ROOT / f"secrets/assistants/{assistant_id}"

    if fleet_dir.exists():
        raise AdminError(f"assistant state already exists: {assistant_id}")

    ensure_directory(fleet_dir, controller_uid, controller_gid, 0o770)
    ensure_directory(
        fleet_dir / "memories", controller_uid, controller_gid, 0o770
    )
    ensure_directory(runtime_dir, CONTAINER_UID, controller_gid, 0o770)
    ensure_directory(runtime_dir / "skins", CONTAINER_UID, controller_gid, 0o770)
    ensure_directory(runtime_dir / "memories", CONTAINER_UID, controller_gid, 0o770)
    ensure_directory(runtime_dir / "skills", CONTAINER_UID, controller_gid, 0o770)
    ensure_directory(
        runtime_dir / "aidee" / "repos", CONTAINER_UID, controller_gid, 0o770
    )
    ensure_directory(secret_dir, 0, 0, 0o700)

    sync_shared_skills(SOURCE_ROOT, runtime_dir, CONTAINER_UID, controller_gid)

    image = assistant.get("image") if isinstance(assistant.get("image"), dict) else {}
    opencode_enabled = image_has_opencode(
        load_image_record(image.get("aidee_version"))
    )
    install_tracing = load_controller_install_langfuse(STATE_ROOT)
    soul = build_soul_document(
        assistant,
        owner_name(),
        opencode_enabled=opencode_enabled,
        tracing_enabled=bool(install_tracing.get("enabled")),
    )
    write_text(
        fleet_dir / "SOUL.md",
        soul,
        controller_uid,
        controller_gid,
    )
    write_text(
        runtime_dir / "SOUL.md",
        soul,
        CONTAINER_UID,
        controller_gid,
    )
    user_memory = f"# User\n\n{owner_name()} owns and directs this assistant.\n"
    memory_content = "# Memory\n"
    write_text(
        fleet_dir / "memories/USER.md",
        user_memory,
        controller_uid,
        controller_gid,
    )
    write_text(
        fleet_dir / "memories/MEMORY.md",
        memory_content,
        controller_uid,
        controller_gid,
    )
    write_text(
        runtime_dir / "memories/USER.md",
        user_memory,
        CONTAINER_UID,
        controller_gid,
    )
    write_text(
        runtime_dir / "memories/MEMORY.md",
        memory_content,
        CONTAINER_UID,
        controller_gid,
    )

    config = default_assistant_config(assistant)
    write_text(
        fleet_dir / "assistant.yaml",
        yaml.safe_dump(config, sort_keys=False),
        controller_uid,
        controller_gid,
    )
    runtime_config = {
        "dashboard": {"public_url": dashboard_url},
        "display": {"skin": assistant_id},
        "platforms": {
            "telegram": {
                "enabled": True,
            }
        },
        "plugins": {"enabled": list(USER_PLUGINS)},
    }
    home_channel = controller_telegram_home_channel()
    if home_channel:
        runtime_config["platforms"]["telegram"]["home_channel"] = home_channel

    write_text(
        runtime_dir / "config.yaml",
        yaml.safe_dump(runtime_config, sort_keys=False),
        CONTAINER_UID,
        controller_gid,
    )
    install_assistant_plugins(
        runtime_dir, uid=CONTAINER_UID, gid=controller_gid
    )
    write_text(
        runtime_dir / PROFILE_RELATIVE_PATH,
        json.dumps(build_assistant_profile(assistant, config), indent=2) + "\n",
        CONTAINER_UID,
        controller_gid,
    )
    write_text(
        runtime_dir / "aidee/onboarding-status.json",
        json.dumps(
            default_onboarding_status(
                assistant.get("kind", "personal"),
                {
                    "telegram_enabled": True,
                    "dashboard_menu_enabled": bool(dashboard_url),
                },
            ),
            indent=2,
        )
        + "\n",
        CONTAINER_UID,
        controller_gid,
    )
    skin_content = {
        "branding": {
            "agent_name": assistant["name"],
            "response_label": f" ⚕ {assistant['name']} ",
        }
    }
    write_text(
        runtime_dir / "skins" / f"{assistant_id}.yaml",
        yaml.safe_dump(skin_content, sort_keys=False),
        CONTAINER_UID,
        controller_gid,
    )
    mark_step(
        runtime_dir / "aidee/onboarding-status.json",
        "assistant",
        "dashboard_branding",
        "completed",
        assistant_kind=assistant.get("kind", "personal"),
        config={
            "telegram_enabled": True,
            "dashboard_menu_enabled": bool(dashboard_url),
        },
        evidence_source="reconciler",
        evidence_detail="display skin and branding match assistant identity",
    )
    inherited_creds = controller_dashboard_credentials()
    if inherited_creds:
        dashboard_username = inherited_creds.get("username") or DASHBOARD_USERNAME
        dashboard_password = inherited_creds.get("password")
        dashboard_password_hash = inherited_creds.get("password_hash")
        dashboard_session_secret = (
            inherited_creds.get("secret") or secrets.token_hex(32)
        )
        dashboard_ttl = inherited_creds.get("ttl") or str(DASHBOARD_TTL_SECONDS)
        env_lines = [
            f"{DASHBOARD_USERNAME_KEY}={dashboard_username}",
        ]
        if dashboard_password:
            env_lines.append(f"{DASHBOARD_PASSWORD_KEY}={dashboard_password}")
        if dashboard_password_hash:
            env_lines.append(
                f"{DASHBOARD_PASSWORD_HASH_KEY}={dashboard_password_hash}"
            )
        env_lines.append(f"{DASHBOARD_SECRET_KEY}={dashboard_session_secret}")
        env_lines.append(f"{DASHBOARD_TTL_KEY}={dashboard_ttl}")
        write_text(
            runtime_dir / ".env",
            "\n".join(env_lines) + "\n",
            CONTAINER_UID,
            controller_gid,
            0o600,
        )
        if dashboard_password:
            write_text(
                secret_dir / "dashboard-initial-password",
                dashboard_password + "\n",
                0,
                0,
                0o600,
            )
        else:
            write_text(
                secret_dir / "dashboard-initial-password",
                "inherited from controller dashboard\n",
                0,
                0,
                0o600,
            )
    else:
        dashboard_password = secrets.token_urlsafe(24)
        dashboard_session_secret = secrets.token_hex(32)
        write_text(
            runtime_dir / ".env",
            (
                f"{DASHBOARD_USERNAME_KEY}={DASHBOARD_USERNAME}\n"
                f"{DASHBOARD_PASSWORD_KEY}={dashboard_password}\n"
                f"{DASHBOARD_SECRET_KEY}={dashboard_session_secret}\n"
                f"{DASHBOARD_TTL_KEY}={DASHBOARD_TTL_SECONDS}\n"
            ),
            CONTAINER_UID,
            controller_gid,
            0o600,
        )
        write_text(
            secret_dir / "dashboard-initial-password",
            dashboard_password + "\n",
            0,
            0,
            0o600,
        )

    if opencode_enabled:
        write_opencode_skill(runtime_dir, True, CONTAINER_UID, controller_gid)
        write_opencode_desired(
            runtime_dir / OPENCODE_DESIRED_RELATIVE,
            "installed",
            CONTAINER_UID,
            controller_gid,
        )

    apply_install_langfuse_files(
        runtime_dir,
        assistant_id,
        install_tracing,
        opencode_enabled=opencode_enabled,
        uid=CONTAINER_UID,
        gid=controller_gid,
    )

    ensure_runtime_tree_permissions(runtime_dir, CONTAINER_UID, controller_gid)
    return fleet_dir, runtime_dir, secret_dir


def update_registry(assistant, image_id, dashboard_url):
    registry_path = STATE_ROOT / "fleet/registry.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    if any(item["id"] == assistant["id"] for item in registry["assistants"]):
        raise AdminError(f"assistant is already registered: {assistant['id']}")
    status_path = (
        STATE_ROOT
        / f"runtime/assistants/{assistant['id']}/data/aidee/onboarding-status.json"
    )
    try:
        onboarding = json.loads(status_path.read_text())["rollup"]
    except (KeyError, OSError, json.JSONDecodeError) as error:
        raise AdminError(
            f"assistant onboarding status is unavailable: {status_path}"
        ) from error
    registry["assistants"].append(
        {
            "id": assistant["id"],
            "name": assistant["name"],
            "kind": assistant["kind"],
            "status": "provisioning",
            "platform_version": "0.1.0",
            "state_path": f"assistants/{assistant['id']}",
            "container_name": f"aidee-{assistant['id']}",
            "dashboard": {
                "hostname": None,
                "host_port": assistant["dashboard"]["host_port"],
                "tailscale_https_port": assistant["dashboard"][
                    "tailscale_https_port"
                ],
                "url": dashboard_url,
            },
            "telegram": {"username": None, "configured": False},
            "resources": {
                "cpu_limit": assistant["resources"]["cpu_limit"],
                "memory_mb": assistant["resources"]["memory_mb"],
                "storage_gb": 20,
                "pids_limit": assistant["resources"]["pids_limit"],
            },
            "image": {
                "aidee_version": assistant["image_version"],
                "image_id": image_id,
            },
            "onboarding": {
                "status": "pending",
                "status_path": "aidee/onboarding-status.json",
                "required_remaining": len(onboarding["incomplete_required"]),
                "optional_remaining": len(onboarding["incomplete_optional"]),
            },
        }
    )
    controller_uid, controller_gid = controller_identity()
    write_text(
        registry_path,
        yaml.safe_dump(registry, sort_keys=False),
        controller_uid,
        controller_gid,
    )


def validate_capacity_and_ports(assistant):
    registry = yaml.safe_load((STATE_ROOT / "fleet/registry.yaml").read_text())
    active = [
        item
        for item in (registry.get("assistants") or [])
        if item.get("status") not in {"retired", "failed"}
        and item.get("id") != assistant.get("id")
    ]
    requested_host_port = assistant["dashboard"]["host_port"]
    requested_https_port = assistant["dashboard"]["tailscale_https_port"]
    for item in active:
        dashboard = item.get("dashboard") or {}
        if dashboard.get("host_port") == requested_host_port:
            raise AdminError("assistant dashboard host port is already allocated")
        if dashboard.get("tailscale_https_port") == requested_https_port:
            raise AdminError("assistant Tailscale HTTPS port is already allocated")

    used_cpu = sum(item["resources"]["cpu_limit"] for item in active)
    used_memory = sum(item["resources"]["memory_mb"] for item in active)
    host_cpu = os.cpu_count() or 1
    try:
        meminfo = Path("/proc/meminfo").read_text()
        host_memory = int(
            next(
                line.split()[1]
                for line in meminfo.splitlines()
                if line.startswith("MemTotal:")
            )
        ) // 1024
    except Exception:
        host_memory = 4096
    cpu_budget = max(0.25, host_cpu - 0.5)
    memory_budget = max(1024, host_memory - 2048)
    if used_cpu + assistant["resources"]["cpu_limit"] > cpu_budget:
        raise AdminError(
            f"assistant CPU allocation exceeds host budget of {cpu_budget}"
        )
    if used_memory + assistant["resources"]["memory_mb"] > memory_budget:
        raise AdminError(
            f"assistant memory allocation exceeds host budget of {memory_budget} MB"
        )


def tailscale_dashboard_url(https_port):
    status = json.loads(run(["tailscale", "status", "--json"]))
    dns_name = status["Self"]["DNSName"].rstrip(".")
    return f"https://{dns_name}:{https_port}"


def create_containers(assistant, image_id, fleet_dir, runtime_dir):
    assistant_id = assistant["id"]
    container_name = f"aidee-{assistant_id}"
    proxy_name = f"{container_name}-dashboard-proxy"
    host_port = assistant["dashboard"]["host_port"]
    resources = assistant["resources"]
    _, controller_gid = controller_identity()

    if run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"name=^{container_name}$",
            "--format",
            "{{.Names}}",
        ]
    ):
        raise AdminError(f"container already exists: {container_name}")

    run(
        [
            "docker",
            "create",
            "--name",
            container_name,
            "--restart",
            "unless-stopped",
            "--cpus",
            str(resources["cpu_limit"]),
            "--memory",
            f"{resources['memory_mb']}m",
            "--pids-limit",
            str(resources["pids_limit"]),
            "--read-only",
            "--security-opt",
            "no-new-privileges:true",
            "--tmpfs",
            "/run:rw,exec,nosuid,nodev,size=64m",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,noexec,size=256m",
            "--publish",
            f"127.0.0.1:{host_port}:9121",
            "--volume",
            f"{runtime_dir}:/opt/data",
            "--volume",
            f"{fleet_dir / 'SOUL.md'}:/opt/data/SOUL.md",
            "--env",
            f"HERMES_GID={controller_gid}",
            "--env",
            "HERMES_DASHBOARD=1",
            "--env",
            "HERMES_DASHBOARD_HOST=127.0.0.1",
            "--env",
            "HERMES_DASHBOARD_PORT=9119",
            # HOME is unset on purpose. The Hermes image user home is /opt/data,
            # the same bind mount as HERMES_HOME. OpenCode reads that HOME.
            image_id,
            "gateway",
            "run",
        ]
    )
    try:
        run(
            [
                "docker",
                "create",
                "--name",
                proxy_name,
                "--restart",
                "unless-stopped",
                "--network",
                f"container:{container_name}",
                "--read-only",
                "--security-opt",
                "no-new-privileges:true",
                "--tmpfs",
                "/run:rw,exec,nosuid,nodev,size=64m",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,noexec,size=64m",
                "--entrypoint",
                "socat",
                image_id,
                "TCP-LISTEN:9121,fork,reuseaddr",
                "TCP:127.0.0.1:9119",
            ]
        )
        run(["docker", "start", container_name])
        run(["docker", "start", proxy_name])
    except AdminError:
        subprocess.run(["docker", "rm", "-f", proxy_name], capture_output=True)
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        raise

    return container_name, proxy_name


def configure_tailscale_route(assistant):
    host_port = assistant["dashboard"]["host_port"]
    https_port = assistant["dashboard"]["tailscale_https_port"]
    run(
        [
            "tailscale",
            "serve",
            "--bg",
            f"--https={https_port}",
            f"http://127.0.0.1:{host_port}",
        ]
    )
    return tailscale_dashboard_url(https_port)


def build_image():
    build_output = run(
        [str(SOURCE_ROOT / "platform/scripts/build-assistant-image.sh")]
    )
    validation_output = run(
        [str(SOURCE_ROOT / "platform/scripts/validate-assistant-image.sh")]
    )
    return {
        "status": "ready",
        "build_output": build_output,
        "validation_output": validation_output,
    }


def create_assistant(request):
    assistant = request["assistant"]
    validate_capacity_and_ports(assistant)
    record = image_record(assistant["image_version"])
    image_id = record["image_id"]
    dashboard_url = tailscale_dashboard_url(
        assistant["dashboard"]["tailscale_https_port"]
    )
    fleet_dir, runtime_dir, secret_dir = create_assistant_state(
        assistant, image_id, dashboard_url
    )
    container_name = f"aidee-{assistant['id']}"
    proxy_name = f"{container_name}-dashboard-proxy"
    try:
        container_name, proxy_name = create_containers(
            assistant, image_id, fleet_dir, runtime_dir
        )
        configured_url = configure_tailscale_route(assistant)
        if configured_url != dashboard_url:
            raise AdminError("configured dashboard URL does not match planned URL")
        update_registry(assistant, image_id, dashboard_url)
    except Exception:
        subprocess.run(["docker", "rm", "-f", proxy_name], capture_output=True)
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        shutil.rmtree(fleet_dir, ignore_errors=True)
        shutil.rmtree(runtime_dir.parent, ignore_errors=True)
        shutil.rmtree(secret_dir, ignore_errors=True)
        raise
    inherited_creds = controller_dashboard_credentials()
    if inherited_creds:
        dashboard_username = inherited_creds.get("username") or DASHBOARD_USERNAME
        next_action = (
            "Open the assistant dashboard and sign in using your controller dashboard "
            "credentials. Then configure model and messaging credentials in the "
            "assistant dashboard."
        )
    else:
        dashboard_username = DASHBOARD_USERNAME
        next_action = (
            "Open the controller dashboard Fleet page to reveal the initial "
            "password. Then configure model and messaging credentials in the "
            "assistant dashboard."
        )
    return {
        "status": "provisioning",
        "assistant_id": assistant["id"],
        "container_name": container_name,
        "proxy_container_name": proxy_name,
        "image_id": image_id,
        "dashboard_url": dashboard_url,
        "dashboard_username": dashboard_username,
        "dashboard_password_command": (
            "sudo /opt/aidee/source/platform/scripts/"
            f"show-assistant-dashboard-password.sh {assistant['id']}"
        ),
        "next_action": next_action,
    }


def lifecycle(operation, assistant_id):
    assistant_id = safe_assistant_id(assistant_id)
    container_name = f"aidee-{assistant_id}"
    proxy_name = f"{container_name}-dashboard-proxy"
    if operation == "start_assistant":
        run(["docker", "start", container_name])
        run(["docker", "start", proxy_name])
    elif operation == "stop_assistant":
        run(["docker", "stop", proxy_name])
        run(["docker", "stop", container_name])
    state = json.loads(run(["docker", "inspect", container_name]))[0]
    proxy_state = json.loads(run(["docker", "inspect", proxy_name]))[0]
    return {
        "assistant_id": assistant_id,
        "status": state["State"]["Status"],
        "running": state["State"]["Running"],
        "dashboard_proxy_running": proxy_state["State"]["Running"],
        "image_id": state["Image"],
    }


def assistant_runtime_dir(assistant_id):
    return STATE_ROOT / f"runtime/assistants/{assistant_id}/data"


def assistant_fleet_dir(assistant_id):
    return STATE_ROOT / f"fleet/assistants/{assistant_id}"


def first_existing_path(paths):
    fallback = None
    for path in paths:
        if path is None:
            continue
        candidate = Path(path)
        if fallback is None:
            fallback = candidate
        if candidate.is_file():
            return candidate
    return fallback


def controller_hermes_dir():
    override_home = os.environ.get("AIDEE_CONTROLLER_HOME")
    if override_home:
        return Path(override_home) / ".hermes"
    preferred = STATE_ROOT / "controller-home" / ".hermes"
    if preferred.is_dir() or (preferred / "config.yaml").is_file():
        return preferred
    return STATE_ROOT / "controller"


def controller_config_path():
    return first_existing_path(
        [
            Path(os.environ["AIDEE_CONTROLLER_CONFIG"])
            if os.environ.get("AIDEE_CONTROLLER_CONFIG")
            else None,
            controller_hermes_dir() / "config.yaml",
            STATE_ROOT / "controller-home" / ".hermes" / "config.yaml",
            STATE_ROOT / "controller" / "config.yaml",
        ]
    )


def controller_env_path():
    return first_existing_path(
        [
            Path(os.environ["AIDEE_CONTROLLER_ENV"])
            if os.environ.get("AIDEE_CONTROLLER_ENV")
            else None,
            controller_hermes_dir() / ".env",
            STATE_ROOT / "controller-home" / ".hermes" / ".env",
            STATE_ROOT / "controller" / ".env",
        ]
    )


def load_image_record(version):
    if not isinstance(version, str) or not version:
        return None
    path = IMAGE_RECORD_ROOT / f"{version}.json"
    try:
        record = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return record if isinstance(record, dict) else None


def hermes_skill_paths(home):
    return [Path(home) / relative for relative in OPENCODE_SKILL_PATHS]


def controller_opencode_desired_path():
    return STATE_ROOT / "fleet/controller/opencode.json"


def controller_runtime_view():
    home = controller_hermes_dir()
    present = shutil.which("opencode") is not None
    source = "host" if present else "missing"
    return inspect_hermes_runtime(
        config_path=controller_config_path(),
        env_path=controller_env_path(),
        plugins_dirs=[home / "plugins"],
        opencode_paths=hermes_skill_paths(home),
        opencode_present=present,
        opencode_source=source,
        opencode_desired_path=controller_opencode_desired_path(),
        opencode_scope="host",
    )


def assistant_runtime_view(assistant_id, item=None, image_record=None):
    runtime = assistant_runtime_dir(assistant_id)
    record = image_record
    if record is None and isinstance(item, dict):
        image = item.get("image") if isinstance(item.get("image"), dict) else {}
        record = load_image_record(image.get("aidee_version"))
    present = image_has_opencode(record)
    return inspect_hermes_runtime(
        config_path=runtime / "config.yaml",
        env_path=runtime / ".env",
        plugins_dirs=[runtime / "plugins"],
        opencode_paths=hermes_skill_paths(runtime),
        opencode_present=present,
        opencode_source="image" if present else "missing",
        opencode_desired_path=runtime / OPENCODE_DESIRED_RELATIVE,
        opencode_scope="image",
    )


def assistant_secret_dir(assistant_id):
    return STATE_ROOT / f"secrets/assistants/{assistant_id}"


def registered_assistant(assistant_id):
    assistant_id = safe_assistant_id(assistant_id)
    registry = yaml.safe_load((STATE_ROOT / "fleet/registry.yaml").read_text())
    for item in registry.get("assistants") or []:
        if item.get("id") == assistant_id:
            return item
    raise AdminError(f"assistant is not registered: {assistant_id}")


def set_dashboard_origin(request):
    """Record the published HTTPS origin for one assistant dashboard."""
    assistant_id = safe_assistant_id(request["assistant_id"])
    try:
        url = normalize_dashboard_url(request["dashboard_url"])
        hostname = dashboard_hostname(url)
    except RuntimeError as error:
        raise AdminError(str(error)) from error
    registry_path = STATE_ROOT / "fleet/registry.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    found = None
    for item in registry.get("assistants") or []:
        if item.get("id") == assistant_id:
            found = item
            break
    if found is None:
        raise AdminError(f"assistant is not registered: {assistant_id}")
    dashboard = found.setdefault("dashboard", {})
    if not isinstance(dashboard, dict):
        raise AdminError(f"assistant dashboard is invalid: {assistant_id}")
    dashboard["url"] = url
    dashboard["hostname"] = hostname
    controller_uid, controller_gid = controller_identity()
    write_text(
        registry_path,
        yaml.safe_dump(registry, sort_keys=False),
        controller_uid,
        controller_gid,
    )
    runtime_dir = assistant_runtime_dir(assistant_id)
    config_path = runtime_dir / "config.yaml"
    try:
        config = yaml.safe_load(config_path.read_text()) or {}
    except FileNotFoundError:
        config = {}
    except yaml.YAMLError as error:
        raise AdminError(f"assistant config is invalid: {config_path}") from error
    if not isinstance(config, dict):
        raise AdminError(f"assistant config is not a mapping: {config_path}")
    apply_published_dashboard_url(config, url)
    write_text(
        config_path,
        yaml.safe_dump(config, sort_keys=False),
        CONTAINER_UID,
        controller_gid,
    )
    profile_path = runtime_dir / "profiles/default/config.yaml"
    if profile_path.is_file():
        try:
            profile = yaml.safe_load(profile_path.read_text()) or {}
        except yaml.YAMLError as error:
            raise AdminError(
                f"assistant profile config is invalid: {profile_path}"
            ) from error
        if isinstance(profile, dict) and apply_published_dashboard_url(profile, url):
            write_text(
                profile_path,
                yaml.safe_dump(profile, sort_keys=False),
                CONTAINER_UID,
                controller_gid,
            )
    return {
        "status": "updated",
        "assistant_id": assistant_id,
        "dashboard_url": url,
        "next_action": (
            "Ask that assistant to set the Telegram menu button to "
            "dashboard.public_url for the default chat and this owner chat. "
            "Set descriptions for the default profile and language_code en. "
            "Do not put dashboard URLs in Telegram descriptions."
        ),
    }


def dashboard_password_file(assistant_id):
    return assistant_secret_dir(assistant_id) / "dashboard-initial-password"


def read_dashboard_password(assistant_id):
    password_file = dashboard_password_file(assistant_id)
    if password_file.is_file():
        password = password_file.read_text().strip()
        if password:
            return password
    env_file = assistant_runtime_dir(assistant_id) / ".env"
    if env_file.is_file():
        password = env_value(env_file.read_text(), DASHBOARD_PASSWORD_KEY)
        if password:
            return password
    raise AdminError(
        "dashboard password is missing; reset it from the Fleet page"
    )


def safe_dashboard_username(username):
    if not isinstance(username, str) or not DASHBOARD_USERNAME_PATTERN.fullmatch(
        username
    ):
        raise AdminError("invalid dashboard username")
    return username


def safe_dashboard_password(password):
    if (
        not isinstance(password, str)
        or len(password) < 8
        or len(password) > 128
        or "\n" in password
        or "\r" in password
    ):
        raise AdminError("invalid dashboard password")
    return password


def read_dashboard_username(assistant_id):
    env_file = assistant_runtime_dir(assistant_id) / ".env"
    if env_file.is_file():
        username = env_value(env_file.read_text(), DASHBOARD_USERNAME_KEY)
        if username:
            return username
    return DASHBOARD_USERNAME


def write_dashboard_password(assistant_id, password, session_secret=None, username=None):
    controller_uid, controller_gid = controller_identity()
    runtime_dir = assistant_runtime_dir(assistant_id)
    secret_dir = assistant_secret_dir(assistant_id)
    env_file = runtime_dir / ".env"
    ensure_directory(runtime_dir, CONTAINER_UID, controller_gid, 0o770)
    ensure_directory(secret_dir, 0, 0, 0o700)
    current = env_file.read_text() if env_file.is_file() else ""
    updates = {
        DASHBOARD_USERNAME_KEY: username or read_dashboard_username(assistant_id),
        DASHBOARD_PASSWORD_KEY: password,
        DASHBOARD_TTL_KEY: str(DASHBOARD_TTL_SECONDS),
    }
    if session_secret is not None:
        updates[DASHBOARD_SECRET_KEY] = session_secret
    elif env_value(current, DASHBOARD_SECRET_KEY) is None:
        updates[DASHBOARD_SECRET_KEY] = secrets.token_hex(32)
    write_text(
        env_file,
        upsert_env(current, updates),
        CONTAINER_UID,
        controller_gid,
        0o600,
    )
    write_text(
        dashboard_password_file(assistant_id),
        password + "\n",
        0,
        0,
        0o600,
    )


def restart_assistant_containers(assistant_id):
    container_name = f"aidee-{assistant_id}"
    proxy_name = f"{container_name}-dashboard-proxy"
    run(["docker", "restart", container_name])
    run(["docker", "restart", proxy_name])


def run_optional(command, timeout=5):
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, str(error)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        return None, f"{command[0]} failed: {detail}"
    return result.stdout.strip(), None


def host_capacity():
    memory = {"error": "host memory is unavailable"}
    try:
        memory = parse_meminfo(Path("/proc/meminfo").read_text())
    except OSError:
        pass
    disk_path = STATE_ROOT if STATE_ROOT.exists() else Path("/")
    disk = {"path": str(disk_path), "error": "host disk is unavailable"}
    try:
        usage = shutil.disk_usage(disk_path)
        disk = parse_disk_usage(usage.total, usage.free, disk_path)
    except OSError:
        pass
    return {
        "memory": memory,
        "disk": disk,
        "cpu_count": os.cpu_count(),
    }


def installed_release():
    output, error = run_optional(
        ["git", "-C", str(SOURCE_ROOT), "describe", "--tags", "--exact-match"]
    )
    if output:
        return output
    latest = SOURCE_ROOT / "LATEST"
    try:
        tag = latest.read_text().strip()
    except OSError:
        return None
    return tag or None


def latest_validated_image_version():
    if not IMAGE_RECORD_ROOT.is_dir():
        return None
    versions = []
    for path in IMAGE_RECORD_ROOT.glob("v*.json"):
        try:
            record = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        version = record.get("aidee_version")
        if record.get("validation") == "validated" and isinstance(version, str):
            versions.append(version)
    if not versions:
        return None
    return sorted(versions)[-1]


def load_registry_document():
    registry_path = STATE_ROOT / "fleet/registry.yaml"
    try:
        registry = yaml.safe_load(registry_path.read_text())
    except FileNotFoundError as error:
        raise AdminError(f"required file not found: {registry_path}") from error
    except (OSError, yaml.YAMLError) as error:
        raise AdminError(f"fleet registry is invalid: {registry_path}") from error
    if registry is None:
        return {}
    if not isinstance(registry, dict):
        raise AdminError("fleet registry is invalid")
    return registry


def load_onboarding_document(path):
    try:
        status = json.loads(path.read_text())
    except FileNotFoundError:
        return None, "onboarding status is unavailable"
    except (OSError, json.JSONDecodeError):
        return None, "onboarding status is malformed"
    if not isinstance(status, dict):
        return None, "onboarding status is malformed"
    return status, None


def probe_assistant_live(container_name):
    raw, error = run_optional(["docker", "inspect", container_name])
    if error:
        lowered = error.lower()
        missing = "no such object" in lowered or "no such container" in lowered
        return {
            "health_status": "missing" if missing else "unknown",
            "running": False,
            "image_version": None,
            "usage": {"cpu_percent": None, "memory_mb": None, "error": error},
            "error": error,
        }
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "health_status": "unknown",
            "running": False,
            "image_version": None,
            "usage": {
                "cpu_percent": None,
                "memory_mb": None,
                "error": "container inspect is invalid",
            },
            "error": "container inspect is invalid",
        }
    live = parse_docker_inspect(payload)
    stats_raw, stats_error = run_optional(
        [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            container_name,
        ]
    )
    if stats_error:
        live["usage"] = {
            "cpu_percent": None,
            "memory_mb": None,
            "error": stats_error,
        }
    else:
        live["usage"] = parse_docker_stats(stats_raw)
    return live


def fleet_overview():
    registry = dict(load_registry_document())
    warnings = []
    live_by_id = {}
    hydrated = []
    assistants = registry.get("assistants")
    if isinstance(assistants, list):
        for item in assistants:
            if not isinstance(item, dict):
                hydrated.append(item)
                continue
            entry = dict(item)
            assistant_id = entry.get("id")
            if not isinstance(assistant_id, str):
                hydrated.append(entry)
                continue
            container_name = entry.get("container_name") or f"aidee-{assistant_id}"
            live = probe_assistant_live(container_name)
            status_path = (
                STATE_ROOT
                / f"runtime/assistants/{assistant_id}/data/aidee/onboarding-status.json"
            )
            status, status_error = load_onboarding_document(status_path)
            if status is not None:
                entry["onboarding"] = status
            else:
                live["onboarding_error"] = status_error
            runtime = assistant_runtime_view(assistant_id, entry)
            live["langfuse"] = runtime.get("langfuse")
            live["tools"] = runtime.get("tools")
            live_by_id[assistant_id] = live
            hydrated.append(entry)
        registry["assistants"] = hydrated
    controller_status, controller_error = load_onboarding_document(
        STATE_ROOT / "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json"
    )
    if controller_error and controller_status is None:
        warnings.append("controller onboarding is unavailable")
    release = {
        "installed": installed_release(),
        "desired": None,
        "image_version": latest_validated_image_version(),
        "error": None,
    }
    if not release["installed"] and not release["image_version"]:
        release["error"] = "installed release is unavailable"
    return public_payload(
        build_overview(
            registry,
            host=host_capacity(),
            release=release,
            controller_onboarding=controller_status,
            live_by_id=live_by_id,
            warnings=warnings,
            controller_runtime=controller_runtime_view(),
        )
    )


def list_assistants():
    registry = yaml.safe_load((STATE_ROOT / "fleet/registry.yaml").read_text())
    assistants = []
    for item in registry.get("assistants") or []:
        assistant_id = item.get("id")
        if not isinstance(assistant_id, str):
            continue
        dashboard = item.get("dashboard") or {}
        entry = {
            "id": assistant_id,
            "name": item.get("name") or assistant_id,
            "kind": item.get("kind"),
            "registry_status": item.get("status"),
            "dashboard_url": dashboard.get("url"),
            "dashboard_username": read_dashboard_username(assistant_id),
            "running": False,
            "status": "missing",
        }
        try:
            live = lifecycle("status_assistant", assistant_id)
            entry["running"] = live["running"]
            entry["status"] = live["status"]
        except AdminError:
            pass
        assistants.append(entry)
    return {"assistants": assistants}


def reveal_dashboard_password(assistant_id):
    item = registered_assistant(assistant_id)
    dashboard = item.get("dashboard") or {}
    return {
        "assistant_id": assistant_id,
        "dashboard_username": read_dashboard_username(assistant_id),
        "dashboard_password": read_dashboard_password(assistant_id),
        "dashboard_url": dashboard.get("url"),
    }


def reset_dashboard_password(assistant_id):
    registered_assistant(assistant_id)
    password = secrets.token_urlsafe(24)
    write_dashboard_password(assistant_id, password)
    restart_assistant_containers(assistant_id)
    item = registered_assistant(assistant_id)
    dashboard = item.get("dashboard") or {}
    return {
        "assistant_id": assistant_id,
        "dashboard_username": read_dashboard_username(assistant_id),
        "dashboard_password": password,
        "dashboard_url": dashboard.get("url"),
        "restarted": True,
    }


def set_dashboard_credentials(request):
    assistant_id = safe_assistant_id(request["assistant_id"])
    registered_assistant(assistant_id)
    username = safe_dashboard_username(request["dashboard_username"])
    password = safe_dashboard_password(request["dashboard_password"])
    write_dashboard_password(assistant_id, password, username=username)
    restart_assistant_containers(assistant_id)
    item = registered_assistant(assistant_id)
    dashboard = item.get("dashboard") or {}
    return {
        "assistant_id": assistant_id,
        "dashboard_username": username,
        "dashboard_password": password,
        "dashboard_url": dashboard.get("url"),
        "restarted": True,
    }


def persistable_request(request):
    stored = dict(request)
    for key in HASHED_REQUEST_KEYS:
        value = stored.get(key)
        if isinstance(value, str) and value:
            stored[key] = "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
    return stored


def load_managed_yaml(path, missing_ok=True):
    if path is None:
        if missing_ok:
            return {}
        raise AdminError("Hermes config.yaml is missing")
    candidate = Path(path)
    if candidate.is_symlink():
        raise AdminError(f"managed file must not be a symlink: {candidate}")
    if not candidate.is_file():
        if missing_ok:
            return {}
        raise AdminError(f"required file not found: {candidate}")
    try:
        data = yaml.safe_load(candidate.read_text()) or {}
    except yaml.YAMLError as error:
        raise AdminError(f"Hermes config.yaml is malformed: {candidate}") from error
    if not isinstance(data, dict):
        raise AdminError(f"Hermes config.yaml is malformed: {candidate}")
    return data


def write_managed_yaml(path, data, uid, gid, mode=0o660):
    write_text(path, yaml.safe_dump(data, sort_keys=False), uid, gid, mode)


def write_opencode_desired(path, desired, uid, gid):
    path = Path(path)
    ensure_directory(path.parent, uid, gid, 0o770)
    write_text(
        path,
        json.dumps(opencode_desired_document(desired), indent=2) + "\n",
        uid,
        gid,
        0o660,
    )


def langfuse_result(view, *, restarted=False, next_action=None):
    langfuse = view.get("langfuse") if isinstance(view, dict) else {}
    payload = {
        "status": "updated",
        "langfuse": langfuse
        if isinstance(langfuse, dict)
        else {"status": "unknown", "reason": "Hermes runtime status is unavailable"},
        "restarted": bool(restarted),
    }
    if next_action:
        payload["next_action"] = next_action
    return public_payload(payload)


def schedule_controller_restart():
    unit = f"aidee-restart-gateway-{secrets.token_hex(4)}"
    try:
        subprocess.Popen(
            [
                "systemd-run",
                "--collect",
                "--on-active=3s",
                "--no-block",
                f"--unit={unit}",
                "systemctl",
                "restart",
                GATEWAY_SERVICE,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return True


def write_langfuse_files(
    config_path,
    env_path,
    uid,
    gid,
    request,
    env_mode=0o600,
    opencode_enabled=False,
    opencode_config_path=None,
    environment=None,
    keep_keys=True,
):
    config_path = Path(config_path)
    env_path = Path(env_path)
    ensure_directory(config_path.parent, uid, gid, 0o770)
    ensure_directory(env_path.parent, uid, gid, 0o770)
    config = load_managed_yaml(config_path, missing_ok=True)
    env_text = env_path.read_text() if env_path.is_file() else ""
    enabled = bool(request.get("enabled"))
    try:
        next_config, next_env = apply_langfuse_settings(
            config,
            env_text,
            enabled=enabled,
            public_key=request.get("public_key"),
            secret_key=request.get("secret_key"),
            base_url=request.get("base_url"),
            environment=environment,
            opencode_enabled=opencode_enabled,
            opencode_config_path=opencode_config_path,
            keep_keys=keep_keys,
        )
    except ValueError as error:
        raise AdminError(str(error)) from error
    write_managed_yaml(config_path, next_config, uid, gid)
    if enabled or env_path.is_file() or next_env.strip():
        write_text(env_path, next_env, uid, gid, env_mode)
    tracing = enabled and opencode_enabled
    write_opencode_config_file(opencode_config_path, tracing, uid, gid)
    write_opencode_credentials_file(
        opencode_credentials_path(opencode_config_path),
        tracing,
        uid,
        gid,
        next_env,
        environment=environment,
    )


def controller_soul_path():
    return STATE_ROOT / "fleet/controller/SOUL.md"


def controller_opencode_config_path():
    return controller_home_dir() / OPENCODE_CONFIG_RELATIVE


def controller_opencode_credentials_path():
    return controller_home_dir() / OPENCODE_CREDENTIALS_RELATIVE


def assistant_opencode_config_path(runtime):
    return assistant_opencode_host_dir(runtime) / OPENCODE_CONFIG_RELATIVE.name


def assistant_opencode_credentials_path(runtime):
    return assistant_opencode_host_dir(runtime) / OPENCODE_CREDENTIALS_RELATIVE.name


def opencode_credentials_path(config_path):
    if config_path is None:
        return None
    return Path(config_path).with_name(OPENCODE_CREDENTIALS_RELATIVE.name)


def remove_managed_file(path):
    if path is None:
        return
    candidate = Path(path)
    if candidate.is_symlink():
        raise AdminError(f"managed file must not be a symlink: {candidate}")
    if candidate.is_file():
        candidate.unlink()


def write_opencode_credentials_file(
    path, tracing, uid, gid, env_text, environment=None
):
    if path is None:
        return
    path = Path(path)
    if not tracing:
        remove_managed_file(path)
        return
    document = opencode_langfuse_credentials_document(
        env_text, environment=environment
    )
    if document is None:
        remove_managed_file(path)
        return
    ensure_directory(path.parent, uid, gid, 0o770)
    write_text(path, json.dumps(document, indent=2) + "\n", uid, gid, 0o600)


def write_opencode_config_file(path, tracing, uid, gid):
    if path is None:
        return
    path = Path(path)
    if not tracing and not path.is_file():
        return
    ensure_directory(path.parent, uid, gid, 0o770)
    current = load_opencode_config(path)
    write_text(
        path,
        json.dumps(apply_opencode_config(current, tracing), indent=2) + "\n",
        uid,
        gid,
        0o660,
    )


def patch_soul_opencode(path, enabled, uid, gid):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        return
    current = path.read_text()
    next_text = apply_opencode_instruction(current, enabled)
    if next_text != current:
        write_text(path, next_text, uid, gid)


def patch_soul_tracing(path, enabled, uid, gid):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        return
    current = path.read_text()
    next_text = apply_tracing_instruction(current, enabled)
    if next_text != current:
        write_text(path, next_text, uid, gid)


def write_opencode_env(
    env_path, enabled, tracing, uid, gid, config_path, env_mode=0o600, environment=None
):
    env_path = Path(env_path)
    current = env_path.read_text() if env_path.is_file() else ""
    if enabled and tracing:
        next_env = apply_opencode_langfuse_env(
            current, config_path, environment=environment
        )
    else:
        next_env = strip_opencode_langfuse_env(current)
    if next_env != current:
        ensure_directory(env_path.parent, uid, gid, 0o770)
        write_text(env_path, next_env, uid, gid, env_mode)
    write_opencode_credentials_file(
        opencode_credentials_path(config_path),
        enabled and tracing,
        uid,
        gid,
        next_env,
        environment=environment,
    )


def langfuse_tracing_on(view):
    langfuse = view.get("langfuse") if isinstance(view, dict) else None
    return isinstance(langfuse, dict) and langfuse.get("status") == "enabled"


def registered_assistants():
    registry = yaml.safe_load((STATE_ROOT / "fleet/registry.yaml").read_text())
    items = []
    for item in registry.get("assistants") or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            items.append(item)
    return items


def inherit_assistant_install_langfuse(assistant_id, item=None, install=None):
    assistant_id = safe_assistant_id(assistant_id)
    if item is None:
        item = registered_assistant(assistant_id)
    controller_uid, controller_gid = controller_identity()
    runtime = assistant_runtime_dir(assistant_id)
    fleet_dir = assistant_fleet_dir(assistant_id)
    image = item.get("image") if isinstance(item.get("image"), dict) else {}
    record = load_image_record(image.get("aidee_version"))
    present = image_has_opencode(record)
    opencode_enabled = opencode_is_enabled(
        present, load_opencode_desired(runtime / OPENCODE_DESIRED_RELATIVE)
    )
    if install is None:
        install = load_controller_install_langfuse(STATE_ROOT)
    enabled = apply_install_langfuse_files(
        runtime,
        assistant_id,
        install,
        opencode_enabled=opencode_enabled,
        uid=CONTAINER_UID,
        gid=controller_gid,
    )
    patch_soul_tracing(fleet_dir / "SOUL.md", enabled, controller_uid, controller_gid)
    patch_soul_tracing(runtime / "SOUL.md", enabled, CONTAINER_UID, controller_gid)
    return item, record, enabled


def set_controller_langfuse(request):
    uid, gid = controller_identity()
    home = controller_hermes_dir()
    config_path = controller_config_path() or (home / "config.yaml")
    env_path = controller_env_path() or (home / ".env")
    present = shutil.which("opencode") is not None
    opencode_enabled = opencode_is_enabled(
        present, load_opencode_desired(controller_opencode_desired_path())
    )
    config_file = controller_opencode_config_path()
    write_langfuse_files(
        config_path,
        env_path,
        uid,
        gid,
        request,
        opencode_enabled=opencode_enabled,
        opencode_config_path=config_file,
        environment=CONTROLLER_LANGFUSE_ENVIRONMENT,
        keep_keys=True,
    )
    enabled = bool(request.get("enabled"))
    patch_soul_tracing(controller_soul_path(), enabled, uid, gid)
    install = load_controller_install_langfuse(STATE_ROOT)
    for item in registered_assistants():
        inherit_assistant_install_langfuse(item["id"], item, install)
        restart_assistant_containers(item["id"])
    restarted = False
    next_action = (
        "Restart the controller gateway so Langfuse tracing starts on the next turn."
    )
    if enabled:
        restarted = schedule_controller_restart()
        if restarted:
            next_action = (
                "The controller gateway will restart in a few seconds so tracing starts."
            )
    return langfuse_result(
        controller_runtime_view(),
        restarted=restarted,
        next_action=next_action,
    )


def set_assistant_langfuse(request):
    assistant_id = safe_assistant_id(request["assistant_id"])
    item, record, _enabled = inherit_assistant_install_langfuse(assistant_id)
    restart_assistant_containers(assistant_id)
    return langfuse_result(
        assistant_runtime_view(assistant_id, item, record),
        restarted=True,
        next_action="The assistant restarted so Langfuse tracing can load.",
    )


def controller_home_dir():
    override = os.environ.get("AIDEE_CONTROLLER_HOME")
    if override:
        return Path(override)
    try:
        return Path(pwd.getpwnam(CONTROLLER_USER).pw_dir)
    except KeyError:
        return controller_hermes_dir().parent


def controller_npm():
    bundled = controller_hermes_dir() / "node" / "bin" / "npm"
    if bundled.is_file():
        return bundled
    found = shutil.which("npm")
    return Path(found) if found else None


def run_controller_npm(args):
    npm = controller_npm()
    if npm is None:
        raise AdminError(
            "Node is not installed for the controller, so OpenCode cannot be changed here"
        )
    home = controller_home_dir()
    hermes = controller_hermes_dir()
    node_bin = hermes / "node" / "bin"
    path = os.environ.get("PATH", "/usr/bin:/bin")
    if node_bin.is_dir():
        path = f"{node_bin}:{path}"
    command = [
        "runuser",
        "-u",
        CONTROLLER_USER,
        "--",
        "env",
        f"HOME={home}",
        f"HERMES_HOME={hermes}",
        f"PATH={path}",
        str(npm),
        *args,
    ]
    return run(command)


def write_opencode_skill(runtime_dir, enabled, uid, gid):
    skill_path = Path(runtime_dir) / OPENCODE_RUNTIME_SKILL
    if enabled:
        ensure_directory(skill_path.parent, uid, gid, 0o770)
        write_text(skill_path, OPENCODE_SKILL_BODY, uid, gid, 0o660)
        return
    if skill_path.is_symlink():
        raise AdminError(f"managed file must not be a symlink: {skill_path}")
    if skill_path.is_file():
        skill_path.unlink()


def set_controller_opencode(request):
    action = request["action"]
    uid, gid = controller_identity()
    home = controller_hermes_dir()
    env_path = controller_env_path() or (home / ".env")
    config_file = controller_opencode_config_path()
    enabled = action == "install"
    if enabled:
        run_controller_npm(
            [
                "install",
                "--global",
                f"--allow-scripts={OPENCODE_PACKAGE}",
                f"{OPENCODE_PACKAGE}@{OPENCODE_VERSION}",
            ]
        )
        write_opencode_desired(controller_opencode_desired_path(), "installed", uid, gid)
        note = (
            f"OpenCode {OPENCODE_VERSION} is installed on the controller host. "
            "Hermes will plan and investigate, then delegate coding to OpenCode."
        )
    else:
        run_controller_npm(["uninstall", "--global", OPENCODE_PACKAGE])
        write_opencode_desired(controller_opencode_desired_path(), "absent", uid, gid)
        note = (
            "OpenCode was removed from the controller host PATH. "
            "The coding-delegation instruction is off."
        )
    write_opencode_skill(home, enabled, uid, gid)
    patch_soul_opencode(controller_soul_path(), enabled, uid, gid)
    view = controller_runtime_view()
    tracing = langfuse_tracing_on(view)
    patch_soul_tracing(controller_soul_path(), tracing, uid, gid)
    tracing = enabled and tracing
    write_opencode_env(
        env_path,
        enabled,
        tracing,
        uid,
        gid,
        config_file,
        environment=CONTROLLER_LANGFUSE_ENVIRONMENT,
    )
    write_opencode_config_file(config_file, tracing, uid, gid)
    restarted = schedule_controller_restart()
    next_action = (
        "The controller gateway will restart in a few seconds so OpenCode can load."
        if restarted
        else "Restart the controller gateway so OpenCode can load."
    )
    view = controller_runtime_view()
    return public_payload(
        {
            "status": "updated",
            "action": action,
            "note": note,
            "tools": view.get("tools") if isinstance(view.get("tools"), list) else [],
            "restarted": restarted,
            "next_action": next_action,
        }
    )


def set_assistant_opencode(request):
    assistant_id = safe_assistant_id(request["assistant_id"])
    item = registered_assistant(assistant_id)
    action = request["action"]
    controller_uid, controller_gid = controller_identity()
    runtime = assistant_runtime_dir(assistant_id)
    fleet_dir = assistant_fleet_dir(assistant_id)
    image = item.get("image") if isinstance(item.get("image"), dict) else {}
    record = load_image_record(image.get("aidee_version"))
    present = image_has_opencode(record)
    config_file = assistant_opencode_config_path(runtime)
    enabled = action == "install"
    if enabled:
        if not present:
            raise AdminError(
                "This assistant image does not include OpenCode. "
                "Update the assistant to an image that pins OpenCode."
            )
        write_opencode_skill(runtime, True, CONTAINER_UID, controller_gid)
        write_opencode_desired(
            runtime / OPENCODE_DESIRED_RELATIVE,
            "installed",
            CONTAINER_UID,
            controller_gid,
        )
        note = (
            "OpenCode is usable for this assistant. The CLI stays in the image. "
            "Hermes will plan and investigate, then delegate coding to OpenCode."
        )
    else:
        write_opencode_skill(runtime, False, CONTAINER_UID, controller_gid)
        write_opencode_desired(
            runtime / OPENCODE_DESIRED_RELATIVE,
            "absent",
            CONTAINER_UID,
            controller_gid,
        )
        if present:
            note = (
                "The OpenCode CLI stays in the assistant image. "
                "The coding-delegation instruction and skill are off until you enable OpenCode again."
            )
        else:
            note = "OpenCode is not in this assistant image."
    patch_soul_opencode(fleet_dir / "SOUL.md", enabled, controller_uid, controller_gid)
    patch_soul_opencode(runtime / "SOUL.md", enabled, CONTAINER_UID, controller_gid)
    view = assistant_runtime_view(assistant_id, item, record)
    tracing = langfuse_tracing_on(view)
    patch_soul_tracing(fleet_dir / "SOUL.md", tracing, controller_uid, controller_gid)
    patch_soul_tracing(runtime / "SOUL.md", tracing, CONTAINER_UID, controller_gid)
    tracing = enabled and tracing
    write_opencode_env(
        runtime / ".env",
        enabled,
        tracing,
        CONTAINER_UID,
        controller_gid,
        config_file,
        environment=langfuse_environment_name(assistant_id),
    )
    write_opencode_config_file(
        config_file, tracing, CONTAINER_UID, controller_gid
    )
    restart_assistant_containers(assistant_id)
    view = assistant_runtime_view(assistant_id, item, record)
    return public_payload(
        {
            "status": "updated",
            "assistant_id": assistant_id,
            "action": action,
            "note": note,
            "tools": view.get("tools") if isinstance(view.get("tools"), list) else [],
            "restarted": True,
        }
    )


def execute(request):
    validate_request(request)
    operation = request["operation"]
    if operation == "build_image":
        return build_image()
    if operation == "create_assistant":
        return create_assistant(request)
    if operation == "list_assistants":
        return list_assistants()
    if operation == "fleet_overview":
        return fleet_overview()
    if operation == "reveal_dashboard_password":
        return reveal_dashboard_password(request["assistant_id"])
    if operation == "reset_dashboard_password":
        return reset_dashboard_password(request["assistant_id"])
    if operation == "set_dashboard_credentials":
        return set_dashboard_credentials(request)
    if operation == "set_dashboard_origin":
        return set_dashboard_origin(request)
    if operation == "set_controller_langfuse":
        return set_controller_langfuse(request)
    if operation == "set_assistant_langfuse":
        return set_assistant_langfuse(request)
    if operation == "set_controller_opencode":
        return set_controller_opencode(request)
    if operation == "set_assistant_opencode":
        return set_assistant_opencode(request)
    if operation in {
        "start_assistant",
        "stop_assistant",
        "status_assistant",
    }:
        return lifecycle(operation, request["assistant_id"])
    raise AdminError(f"unsupported operation: {operation}")


def execute_idempotent(request):
    validate_request(request)
    request_id = request["request_id"]
    records = STATE_ROOT / "runtime/admin-requests"
    controller_uid, controller_gid = controller_identity()
    records.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(records, 0o770)
        os.chown(records, controller_uid, controller_gid)
    except OSError:
        pass
    record_path = records / f"{request_id}.json"
    if record_path.exists():
        record = load_json(record_path)
        if record.get("request") != persistable_request(request):
            raise AdminError("request ID was already used with different content")
        return record["result"]

    result = execute(request)
    temporary = record_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {"request": persistable_request(request), "result": result},
            indent=2,
        )
        + "\n"
    )
    os.chmod(temporary, 0o660)
    try:
        os.chown(temporary, controller_uid, controller_gid)
    except OSError:
        pass
    temporary.replace(record_path)
    return result


def peer_uid(connection):
    if not hasattr(socket, "SO_PEERCRED"):
        raise AdminError("SO_PEERCRED is unavailable")
    credentials = connection.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        struct.calcsize("3i"),
    )
    _, uid, _ = struct.unpack("3i", credentials)
    return uid


def handle_connection(connection, allowed_uid):
    uid = peer_uid(connection)
    if uid != allowed_uid and uid != 0:
        raise AdminError("unauthorized socket peer")
    message = connection.recv(MAX_REQUEST_BYTES + 1)
    if len(message) > MAX_REQUEST_BYTES:
        raise AdminError("request exceeds size limit")
    try:
        request = json.loads(message)
    except json.JSONDecodeError as error:
        raise AdminError("request is not valid JSON") from error
    return execute_idempotent(request)


def serve():
    controller_uid, controller_gid = controller_identity()
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(SOCKET_PATH.parent, 0o770)
        os.chown(SOCKET_PATH.parent, 0, controller_gid)
    except OSError:
        pass
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(SOCKET_PATH))
        os.chown(SOCKET_PATH, 0, controller_gid)
        os.chmod(SOCKET_PATH, 0o660)
        server.listen(8)
        print(f"Aidee administration helper listening at {SOCKET_PATH}", flush=True)
        while True:
            connection, _ = server.accept()
            with connection:
                try:
                    result = {"ok": True, "result": handle_connection(connection, controller_uid)}
                except Exception as error:
                    result = {"ok": False, "error": str(error)}
                connection.sendall((json.dumps(result) + "\n").encode())


if __name__ == "__main__":
    try:
        serve()
    except (AdminError, KeyError, OSError, pwd.KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
