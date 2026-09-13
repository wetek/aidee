#!/usr/bin/env python3
import json
import os
import pwd
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema
import yaml


SOURCE_ROOT = Path(os.environ.get("AIDEE_SOURCE_ROOT", "/opt/aidee/source"))
STATE_ROOT = Path(os.environ.get("AIDEE_STATE_ROOT", "/var/lib/aidee"))
IMAGE_RECORD_ROOT = Path(
    os.environ.get("AIDEE_IMAGE_RECORD_ROOT", "/etc/aidee/images")
)
OWNER_RECORD = Path(os.environ.get("AIDEE_OWNER_RECORD", "/etc/aidee/owner.json"))
SOCKET_PATH = Path(os.environ.get("AIDEE_ADMIN_SOCKET", "/run/aidee/admin.sock"))
CONTROLLER_USER = os.environ.get("AIDEE_CONTROLLER_USER", "aidee-controller")
CONTAINER_UID = 10000
MAX_REQUEST_BYTES = 65536
ASSISTANT_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


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
    path.mkdir(parents=True, exist_ok=True)
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def write_text(path, text, uid, gid, mode=0o660):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text)
    os.chown(temporary, uid, gid)
    os.chmod(temporary, mode)
    temporary.replace(path)


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


def create_assistant_state(assistant, image_id):
    controller_uid, controller_gid = controller_identity()
    assistant_id = safe_assistant_id(assistant["id"])
    fleet_dir = STATE_ROOT / f"fleet/assistants/{assistant_id}"
    runtime_dir = STATE_ROOT / f"runtime/assistants/{assistant_id}/data"

    if fleet_dir.exists():
        raise AdminError(f"assistant state already exists: {assistant_id}")

    ensure_directory(fleet_dir, controller_uid, controller_gid, 0o2770)
    ensure_directory(
        fleet_dir / "memories", controller_uid, controller_gid, 0o2770
    )
    ensure_directory(runtime_dir, CONTAINER_UID, controller_gid, 0o770)

    soul = f"""# {assistant["name"]}

You are {assistant["name"]}, a Hermes assistant owned by {owner_name()}.

Purpose: {assistant["purpose"]}

You run in an isolated Aidee container. Use only your approved files, tools,
repositories, and services. Never expose credentials or another assistant's
data.

Keep user-facing responses concise. Default to 120 words or fewer. Expand only
when safety, a decision, or an error requires it.
"""
    write_text(
        fleet_dir / "SOUL.md",
        soul,
        controller_uid,
        controller_gid,
    )
    write_text(
        fleet_dir / "memories/USER.md",
        f"# User\n\n{owner_name()} owns and directs this assistant.\n",
        controller_uid,
        controller_gid,
    )
    write_text(
        fleet_dir / "memories/MEMORY.md",
        "# Memory\n",
        controller_uid,
        controller_gid,
    )

    config = {
        "schema_version": 1,
        "assistant": {
            "id": assistant_id,
            "name": assistant["name"],
            "kind": assistant["kind"],
            "purpose": assistant["purpose"],
        },
        "projects": [],
        "approvals": {"mode": "hermes_default"},
    }
    write_text(
        fleet_dir / "assistant.yaml",
        yaml.safe_dump(config, sort_keys=False),
        controller_uid,
        controller_gid,
    )
    write_text(
        runtime_dir / "config.yaml",
        "{}\n",
        CONTAINER_UID,
        controller_gid,
    )

    return fleet_dir, runtime_dir


def update_registry(assistant, image_id, dashboard_url):
    registry_path = STATE_ROOT / "fleet/registry.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    if any(item["id"] == assistant["id"] for item in registry["assistants"]):
        raise AdminError(f"assistant is already registered: {assistant['id']}")
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
        for item in registry["assistants"]
        if item["status"] not in {"retired", "failed"}
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
    host_memory = int(
        next(
            line.split()[1]
            for line in Path("/proc/meminfo").read_text().splitlines()
            if line.startswith("MemTotal:")
        )
    ) // 1024
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
            "--volume",
            f"{fleet_dir / 'memories'}:/opt/data/memories",
            "--env",
            f"HERMES_GID={controller_gid}",
            "--env",
            "HERMES_DASHBOARD=1",
            "--env",
            "HERMES_DASHBOARD_HOST=127.0.0.1",
            "--env",
            "HERMES_DASHBOARD_PORT=9119",
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
                image_id,
                "socat",
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
    fleet_dir, runtime_dir = create_assistant_state(assistant, image_id)
    container_name = f"aidee-{assistant['id']}"
    proxy_name = f"{container_name}-dashboard-proxy"
    try:
        container_name, proxy_name = create_containers(
            assistant, image_id, fleet_dir, runtime_dir
        )
        dashboard_url = configure_tailscale_route(assistant)
        update_registry(assistant, image_id, dashboard_url)
    except Exception:
        subprocess.run(["docker", "rm", "-f", proxy_name], capture_output=True)
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        shutil.rmtree(fleet_dir, ignore_errors=True)
        shutil.rmtree(runtime_dir.parent, ignore_errors=True)
        raise
    return {
        "status": "provisioning",
        "assistant_id": assistant["id"],
        "container_name": container_name,
        "proxy_container_name": proxy_name,
        "image_id": image_id,
        "dashboard_url": dashboard_url,
        "next_action": "Open the private dashboard and configure model and messaging credentials.",
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


def execute(request):
    validate_request(request)
    operation = request["operation"]
    if operation == "build_image":
        return build_image()
    if operation == "create_assistant":
        return create_assistant(request)
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
    records.mkdir(parents=True, exist_ok=True)
    record_path = records / f"{request_id}.json"
    if record_path.exists():
        record = load_json(record_path)
        if record.get("request") != request:
            raise AdminError("request ID was already used with different content")
        return record["result"]

    result = execute(request)
    temporary = record_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"request": request, "result": result}, indent=2) + "\n"
    )
    os.chmod(temporary, 0o600)
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
    if peer_uid(connection) != allowed_uid:
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
