#!/usr/bin/env python3
"""Aidee host desired-state reconciler."""

import argparse
import importlib.util
import json
import os
import pwd
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml


RELEASE_PATTERN = r"^v[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+$"
ASSISTANT_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
UPDATE_JOB = "Aidee daily update check"
WATCHDOG_JOB = "Aidee fleet health watchdog"


class ReconcileError(RuntimeError):
    pass


class Runner:
    def run(self, command, check=True, stream=False):
        if stream:
            result = subprocess.run(command, stdin=subprocess.DEVNULL)
            if check and result.returncode:
                raise ReconcileError(f"{command[0]} failed")
            return result
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        if check and result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            raise ReconcileError(f"{command[0]} failed: {detail}")
        return result


def emit_progress(index, total, message, stream=None):
    """Print one apply step so a long run does not look idle."""
    if stream is None:
        stream = sys.stdout
    print(f"[{index}/{total}] {message}", file=stream, flush=True)


class StepReporter:
    def __init__(self, actions, stream=None):
        self.actions = list(actions)
        self.stream = sys.stdout if stream is None else stream
        self.index = 0

    def next(self):
        if self.index >= len(self.actions):
            raise ReconcileError("update reported more steps than the printed plan")
        action = self.actions[self.index]
        self.index += 1
        emit_progress(self.index, len(self.actions), action, self.stream)
        return action


def atomic_write(path, content, mode=0o640):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ReconcileError(f"refusing to replace symlink: {path}")
    metadata = path.stat() if path.exists() else None
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
        if metadata is not None:
            os.chown(temporary, metadata.st_uid, metadata.st_gid)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def safe_state_path(root, relative, description):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ReconcileError(f"{description} must stay below {root}: {relative}")
    target = root / path
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ReconcileError(f"{description} contains a symlink: {current}")
    return target


def validate_registry(registry):
    for assistant in registry["assistants"]:
        if not isinstance(assistant, dict):
            raise ReconcileError("fleet registry assistant is not an object")
        assistant_id = assistant.get("id")
        if not isinstance(assistant_id, str) or not ASSISTANT_ID_PATTERN.fullmatch(
            assistant_id
        ):
            raise ReconcileError("fleet registry has an invalid assistant ID")
        expected_name = f"aidee-{assistant_id}"
        container_name = assistant.get("container_name", expected_name)
        if container_name != expected_name:
            raise ReconcileError(
                f"assistant {assistant_id} has an unsafe container name"
            )
        state_path = assistant.get("state_path") or f"assistants/{assistant_id}"
        if not isinstance(state_path, str):
            raise ReconcileError(
                f"assistant {assistant_id} has an unsafe state path"
            )
        state_path_value = Path(state_path)
        if state_path_value.is_absolute() or ".." in state_path_value.parts:
            raise ReconcileError(
                f"assistant {assistant_id} has an unsafe state path"
            )
        dashboard = assistant.get("dashboard") or {}
        if not isinstance(dashboard, dict):
            raise ReconcileError(f"assistant {assistant_id} dashboard is invalid")
        host_port = dashboard.get("host_port")
        if (
            not isinstance(host_port, int)
            or isinstance(host_port, bool)
            or not 1024 <= host_port <= 65535
        ):
            raise ReconcileError(
                f"assistant {assistant_id} has no dashboard host port"
            )
        resources = assistant.get("resources")
        if resources is not None and not isinstance(resources, dict):
            raise ReconcileError(f"assistant {assistant_id} resources are invalid")
        resources = resources or {}
        cpu_limit = resources.get("cpu_limit", 0.75)
        memory_mb = resources.get("memory_mb", 2048)
        pids_limit = resources.get("pids_limit", 512)
        if (
            not isinstance(cpu_limit, (int, float))
            or isinstance(cpu_limit, bool)
            or cpu_limit <= 0
            or not isinstance(memory_mb, int)
            or isinstance(memory_mb, bool)
            or memory_mb < 512
            or not isinstance(pids_limit, int)
            or isinstance(pids_limit, bool)
            or pids_limit < 64
        ):
            raise ReconcileError(f"assistant {assistant_id} resources are invalid")


def load_registry(path):
    try:
        value = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise ReconcileError(f"cannot read fleet registry: {error}") from error
    if not isinstance(value, dict) or not isinstance(value.get("assistants"), list):
        raise ReconcileError("fleet registry has an invalid shape")
    validate_registry(value)
    return value


def run_migrations(candidate, state_root):
    ledger = state_root / "migrations"
    backup_root = state_root / "backups" / "migrations"
    ledger.mkdir(parents=True, exist_ok=True)
    os.chmod(ledger, 0o750)
    applied = []
    for migration in sorted((candidate / "platform/migrations").glob("[0-9]*.py")):
        marker = ledger / f"{migration.stem}.json"
        if marker.exists():
            if marker.is_symlink():
                raise ReconcileError(f"migration marker is a symlink: {marker}")
            try:
                recorded = json.loads(marker.read_text())
            except (OSError, json.JSONDecodeError) as error:
                raise ReconcileError(
                    f"migration marker is invalid: {marker}"
                ) from error
            if recorded.get("migration") != migration.stem:
                raise ReconcileError(f"migration marker does not match: {marker}")
            continue
        spec = importlib.util.spec_from_file_location(
            f"aidee_migration_{migration.stem}", migration
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.apply(state_root=state_root, backup_root=backup_root / migration.stem)
        atomic_write(
            marker,
            json.dumps({"migration": migration.stem, "release": candidate.name}, indent=2)
            + "\n",
        )
        applied.append(migration.stem)
    return applied


def normalize_owner_name(value):
    if not isinstance(value, str) or not value.strip():
        raise ReconcileError("owner name must not be empty")
    value = value.strip()
    if len(value) > 200 or any(ord(character) < 32 for character in value):
        raise ReconcileError("owner name contains unsupported control characters")
    return value


def owner_name(owner_record):
    try:
        value = json.loads(owner_record.read_text()).get("name")
    except (OSError, json.JSONDecodeError):
        return "Owner"
    if not isinstance(value, str) or not value.strip():
        return "Owner"
    return normalize_owner_name(value)


def controller_account(name):
    try:
        account = pwd.getpwnam(name)
    except KeyError as error:
        raise ReconcileError(f"controller account does not exist: {name}") from error
    return account.pw_dir, account.pw_uid, account.pw_gid


def resolved_assistant(assistant, fleet_dir):
    desired = dict(assistant)
    assistant_config = fleet_dir / "assistant.yaml"
    if assistant_config.is_symlink():
        raise ReconcileError(f"assistant config must not be a symlink: {assistant_config}")
    if assistant_config.is_file():
        try:
            configured = yaml.safe_load(assistant_config.read_text()).get(
                "assistant", {}
            )
            if isinstance(configured, dict):
                for field in ("name", "kind", "purpose"):
                    if configured.get(field):
                        desired[field] = configured[field]
        except (OSError, yaml.YAMLError, AttributeError):
            pass
    desired.setdefault("name", assistant["id"].replace("-", " ").title())
    desired.setdefault("kind", "personal")
    existing_soul = fleet_dir / "SOUL.md"
    if existing_soul.is_symlink():
        raise ReconcileError(f"assistant instructions must not be a symlink: {existing_soul}")
    if "purpose" not in desired and existing_soul.is_file():
        match = re.search(
            r"^Purpose:\s*(.+)$", existing_soul.read_text(), re.MULTILINE
        )
        if match:
            desired["purpose"] = match.group(1).strip()
    desired.setdefault("purpose", f"Operate as {desired['name']} assistant.")
    return desired


def sync_assistant_state(
    candidate, state_root, owner, controller_uid, controller_gid
):
    sys.path.insert(0, str(candidate / "platform/admin"))
    from assistant_state import (
        CONTAINER_UID,
        ONBOARDING_RELATIVE_PATH,
        atomic_write as write_assistant_file,
        ensure_directory,
        ensure_file_metadata,
        onboarding_complete,
        reconcile_assistant_files,
    )

    registry_path = state_root / "fleet/registry.yaml"
    registry = load_registry(registry_path)
    changed = {}
    for assistant in registry["assistants"]:
        assistant_id = assistant["id"]
        state_path = assistant.get("state_path") or f"assistants/{assistant_id}"
        fleet_dir = safe_state_path(
            state_root / "fleet", state_path, "assistant state path"
        )
        runtime_dir = safe_state_path(
            state_root,
            f"runtime/assistants/{assistant_id}/data",
            "assistant runtime path",
        )
        desired_assistant = resolved_assistant(assistant, fleet_dir)
        assistant_changes = []
        assistant_changes.extend(
            reconcile_assistant_files(
                desired_assistant,
                owner,
                fleet_dir,
                runtime_dir,
                uid=CONTAINER_UID,
                gid=controller_gid,
                fleet_uid=controller_uid,
            )
        )
        status = json.loads((runtime_dir / ONBOARDING_RELATIVE_PATH).read_text())
        if onboarding_complete(status):
            onboarding_status = "complete"
        elif any(
            step.get("status") == "in_progress"
            for step in status.get("steps", {}).values()
            if isinstance(step, dict)
        ):
            onboarding_status = "in_progress"
        else:
            onboarding_status = "pending"
        assistant["onboarding"] = {
            "status": onboarding_status,
            "status_path": str(ONBOARDING_RELATIVE_PATH),
            "required_remaining": len(
                status.get("rollup", {}).get("incomplete_required", [])
            ),
            "optional_remaining": len(
                status.get("rollup", {}).get("incomplete_optional", [])
            ),
        }
        skills = runtime_dir / "skills"
        ensure_directory(skills, uid=CONTAINER_UID, gid=controller_gid)
        for source in sorted((candidate / "platform/shared-skills").iterdir()):
            if not (source / "SKILL.md").is_file():
                continue
            target = skills / source.name
            ensure_directory(target, uid=CONTAINER_UID, gid=controller_gid)
            for item in source.rglob("*"):
                relative = item.relative_to(source)
                destination = target / relative
                if item.is_dir():
                    ensure_directory(
                        destination, uid=CONTAINER_UID, gid=controller_gid
                    )
                elif item.is_file():
                    ensure_directory(
                        destination.parent,
                        uid=CONTAINER_UID,
                        gid=controller_gid,
                    )
                    content = item.read_text()
                    if (
                        not destination.is_file()
                        or destination.is_symlink()
                        or destination.read_text() != content
                    ):
                        write_assistant_file(
                            destination,
                            content,
                            uid=CONTAINER_UID,
                            gid=controller_gid,
                        )
                        assistant_changes.append(str(destination))
                    ensure_file_metadata(
                        destination, uid=CONTAINER_UID, gid=controller_gid
                    )
        if assistant_changes:
            changed[assistant_id] = assistant_changes
    return registry, changed


def reconcile_controller_onboarding(candidate, state_root, owner):
    """Migrate controller state and record only verified local convergence."""
    setup_dir = candidate / "platform/setup"
    if str(setup_dir) not in sys.path:
        sys.path.insert(0, str(setup_dir))
    from onboarding_state import locked_status, mark_step

    controller_dir = state_root / "fleet/controller"
    status_path = controller_dir / "CONTROLLER_ONBOARDING_STATUS.json"
    onboarding_config = None
    plan_path = state_root / "setup/setup-plan.json"
    if plan_path.is_file():
        try:
            plan = json.loads(plan_path.read_text())
            controller_plan = plan.get("controller") or {}
            messaging = controller_plan.get("messaging") or []
            telegram_plan = controller_plan.get("telegram") or {}
            onboarding_config = {
                "telegram_enabled": "telegram" in messaging,
                "dashboard_menu_enabled": bool(
                    telegram_plan.get("menu_button", False)
                ),
            }
        except (AttributeError, json.JSONDecodeError):
            onboarding_config = None
    with locked_status(status_path, "controller", config=onboarding_config):
        pass
    soul = controller_dir / "SOUL.md"
    template = candidate / "fleet-template/controller/SOUL.md.template"
    desired_soul = template.read_text().replace("{{ owner_name }}", owner)
    if not soul.is_file() or soul.read_text() != desired_soul:
        atomic_write(soul, desired_soul, 0o640)
    if soul.is_file():
        with locked_status(status_path, "controller") as status:
            identity_complete = (
                status["steps"]["identity_skin"]["status"] == "completed"
            )
        if not identity_complete:
            mark_step(
                status_path,
                "controller",
                "identity_skin",
                "completed",
                evidence_source="reconciler",
                evidence_detail="controller SOUL instructions are installed",
            )
    return status_path


def create_container_commands(assistant, image_id, state_root, controller_gid):
    assistant_id = assistant["id"]
    name = assistant.get("container_name") or f"aidee-{assistant_id}"
    proxy = f"{name}-dashboard-proxy"
    resources = assistant.get("resources") or {}
    dashboard = assistant.get("dashboard") or {}
    host_port = dashboard.get("host_port")
    if not isinstance(host_port, int):
        raise ReconcileError(f"assistant {assistant_id} has no dashboard host port")
    fleet_dir = safe_state_path(
        state_root / "fleet",
        assistant.get("state_path") or f"assistants/{assistant_id}",
        "assistant state path",
    )
    runtime_dir = state_root / f"runtime/assistants/{assistant_id}/data"
    main = [
        "docker", "create", "--name", name, "--restart", "unless-stopped",
        "--cpus", str(resources.get("cpu_limit", 0.75)),
        "--memory", f"{resources.get('memory_mb', 2048)}m",
        "--pids-limit", str(resources.get("pids_limit", 512)),
        "--read-only", "--security-opt", "no-new-privileges:true",
        "--tmpfs", "/run:rw,exec,nosuid,nodev,size=64m",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=256m",
        "--publish", f"127.0.0.1:{host_port}:9121",
        "--volume", f"{runtime_dir}:/opt/data",
        "--volume", f"{fleet_dir / 'SOUL.md'}:/opt/data/SOUL.md",
        "--env", f"HERMES_GID={controller_gid}",
        "--env", "HERMES_DASHBOARD=1",
        "--env", "HERMES_DASHBOARD_HOST=127.0.0.1",
        "--env", "HERMES_DASHBOARD_PORT=9119",
        image_id, "gateway", "run",
    ]
    proxy_command = [
        "docker", "create", "--name", proxy, "--restart", "unless-stopped",
        "--network", f"container:{name}", "--read-only",
        "--security-opt", "no-new-privileges:true",
        "--tmpfs", "/run:rw,exec,nosuid,nodev,size=64m",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m",
        "--entrypoint", "socat", image_id, "TCP-LISTEN:9121,fork,reuseaddr",
        "TCP:127.0.0.1:9119",
    ]
    return name, proxy, main, proxy_command


def container_image(runner, name):
    result = runner.run(
        ["docker", "inspect", name, "--format", "{{.Image}}"], check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def wait_healthy(runner, name, attempts=90, now=time.monotonic, sleep=time.sleep):
    started = now()
    last_note = 0
    for _ in range(attempts):
        result = runner.run(
            [
                "docker", "inspect", name, "--format",
                "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
            ],
            check=False,
        )
        if result.stdout.strip() in {"healthy", "running"}:
            return
        elapsed = int(now() - started)
        if elapsed - last_note >= 15:
            print(f"Still waiting for {name} ({elapsed}s)...", flush=True)
            last_note = elapsed
        sleep(1)
    raise ReconcileError(f"replacement container did not become healthy: {name}")


def dashboard_response(runner, assistant):
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--output",
        "/dev/null",
        "--write-out",
        "%{http_code}",
        "--max-time",
        "5",
    ]
    dashboard = assistant["dashboard"]
    hostname = dashboard.get("hostname")
    if hostname:
        if not isinstance(hostname, str) or not re.fullmatch(
            r"[A-Za-z0-9.-]+", hostname
        ):
            raise ReconcileError(
                f"assistant dashboard hostname is invalid: {assistant['id']}"
            )
        command.extend(["--header", f"Host: {hostname}"])
    command.append(f"http://127.0.0.1:{dashboard['host_port']}/")
    return runner.run(command, check=False)


def wait_dashboard(
    runner, assistant, attempts=90, now=time.monotonic, sleep=time.sleep
):
    started = now()
    last_note = 0
    for _ in range(attempts):
        result = dashboard_response(runner, assistant)
        if not result.returncode and re.fullmatch(r"[234][0-9]{2}", result.stdout):
            return
        elapsed = int(now() - started)
        if elapsed - last_note >= 15:
            print(
                f"Still waiting for {assistant['id']} dashboard ({elapsed}s)...",
                flush=True,
            )
            last_note = elapsed
        sleep(1)
    raise ReconcileError(
        f"assistant dashboard did not become ready: {assistant['id']}"
    )


def rollback_names(assistant):
    name = assistant.get("container_name") or f"aidee-{assistant['id']}"
    proxy = f"{name}-dashboard-proxy"
    return name, proxy, {
        name: f"{name}-aidee-rollback",
        proxy: f"{proxy}-aidee-rollback",
    }


def rollback_container_pair(runner, assistant):
    name, proxy, backups = rollback_names(assistant)
    for created in (proxy, name):
        if container_image(runner, created):
            runner.run(["docker", "rm", "-f", created], check=False)
    for original in (name, proxy):
        backup = backups[original]
        if container_image(runner, backup):
            runner.run(["docker", "rename", backup, original])
            runner.run(["docker", "start", original])


def finalize_container_pair(runner, assistant):
    _, _, backups = rollback_names(assistant)
    failures = []
    for backup in backups.values():
        if container_image(runner, backup):
            result = runner.run(["docker", "rm", backup], check=False)
            if result.returncode:
                failures.append(backup)
    return failures


def replace_container_pair(
    runner,
    assistant,
    image_id,
    state_root,
    controller_gid,
    retain_backup=False,
):
    name, proxy, main_create, proxy_create = create_container_commands(
        assistant, image_id, state_root, controller_gid
    )
    current_main = container_image(runner, name)
    current_proxy = container_image(runner, proxy)
    if current_main == image_id and current_proxy == image_id:
        runner.run(["docker", "start", name])
        runner.run(["docker", "start", proxy])
        wait_healthy(runner, name)
        wait_healthy(runner, proxy)
        return False
    _, _, backups = rollback_names(assistant)
    for backup in backups.values():
        if container_image(runner, backup):
            raise ReconcileError(f"stale rollback container requires review: {backup}")
    try:
        for original in (proxy, name):
            if container_image(runner, original):
                runner.run(["docker", "stop", original], check=False)
                runner.run(["docker", "rename", original, backups[original]])
        runner.run(main_create)
        runner.run(proxy_create)
        runner.run(["docker", "start", name])
        runner.run(["docker", "start", proxy])
        wait_healthy(runner, name)
        wait_healthy(runner, proxy)
        wait_dashboard(runner, assistant)
        if not retain_backup:
            finalize_container_pair(runner, assistant)
    except Exception:
        rollback_container_pair(runner, assistant)
        raise
    return True


def update_registry(registry_path, registry, release, image_id):
    platform = registry.setdefault("platform", {})
    platform["desired_release"] = release
    for assistant in registry["assistants"]:
        desired = {"aidee_version": release, "image_id": image_id}
        assistant["image"] = desired
        onboarding = assistant.get("onboarding")
        if not isinstance(onboarding, dict):
            onboarding = {}
            assistant["onboarding"] = onboarding
        if "status" not in onboarding:
            onboarding["status"] = "pending"
        if onboarding.get("status_path") != "aidee/onboarding-status.json":
            onboarding["status_path"] = "aidee/onboarding-status.json"
        onboarding.setdefault("required_remaining", 0)
        onboarding.setdefault("optional_remaining", 0)
    rendered = yaml.safe_dump(registry, sort_keys=False)
    changed = registry_path.read_text() != rendered
    if changed:
        atomic_write(registry_path, rendered, 0o660)
    return changed


def validated_image(candidate, release):
    record = Path("/etc/aidee/images") / f"{release}.json"
    try:
        value = json.loads(record.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ReconcileError(f"validated image record is unavailable: {error}") from error
    if value.get("validation") != "validated":
        raise ReconcileError("assistant image did not pass validation")
    if value.get("aidee_version") != release:
        raise ReconcileError("assistant image record has the wrong release")
    commit = subprocess.run(
        ["git", "-C", str(candidate), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if value.get("source_commit") != commit:
        raise ReconcileError("assistant image record does not match the release")
    image_id = value.get("image_id")
    if not isinstance(image_id, str) or not re.fullmatch(
        r"sha256:[a-f0-9]{64}", image_id
    ):
        raise ReconcileError("assistant image record has an invalid image ID")
    inspected = subprocess.run(
        ["docker", "image", "inspect", image_id],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspected.returncode:
        raise ReconcileError("validated assistant image is not present")
    return image_id


def activate_release(candidate, release, code_root):
    source = code_root / "source"
    releases = code_root / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    if source.exists() and not source.is_symlink():
        archive = releases / f"legacy-{int(time.time())}"
        source.rename(archive)
    temporary = code_root / ".source.next"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(Path("releases") / release)
    temporary.replace(source)


def run_controller_command(runner, user, home, command, check=True, stream=False):
    return runner.run(
        ["runuser", "-u", user, "--", "env", f"HOME={home}",
         f"PATH={home}/.local/bin:/usr/local/bin:/usr/bin:/bin", *command],
        check=check,
        stream=stream,
    )


def verify(
    runner,
    release,
    source,
    state_root,
    controller_user,
    controller_home,
    image_id,
    expected_registry=None,
):
    failures = []
    _, _, controller_gid = controller_account(controller_user)
    installed = runner.run(
        ["git", "-C", str(source), "describe", "--tags", "--exact-match"],
        check=False,
    ).stdout.strip()
    if installed != release:
        failures.append(f"host release is {installed or 'unknown'}")
    host_dirty = runner.run(
        ["git", "-C", str(source), "status", "--porcelain"], check=False
    )
    if host_dirty.returncode or host_dirty.stdout:
        failures.append("host release checkout is not clean")
    hermes_source = f"{controller_home}/.hermes/hermes-agent"
    hermes_tag = run_controller_command(
        runner,
        controller_user,
        controller_home,
        ["git", "-C", hermes_source, "describe", "--tags", "--exact-match"],
        check=False,
    ).stdout.strip()
    expected_hermes = (source / "platform/HERMES_VERSION").read_text().strip()
    if hermes_tag != expected_hermes:
        failures.append(f"controller Hermes is {hermes_tag or 'unknown'}")
    hermes_patch = run_controller_command(
        runner,
        controller_user,
        controller_home,
        [
            str(source / "platform/scripts/apply-hermes-runtime-patch.sh"),
            "--check",
            hermes_source,
        ],
        check=False,
    )
    if hermes_patch.returncode:
        failures.append("controller Hermes runtime patch is invalid")
    hermes_binary = runner.run(
        ["readlink", "-f", f"{controller_home}/.local/bin/hermes"], check=False
    ).stdout.strip()
    hermes_real_source = runner.run(
        ["readlink", "-f", hermes_source], check=False
    ).stdout.strip()
    if hermes_binary != f"{hermes_real_source}/venv/bin/hermes":
        failures.append("controller Hermes command does not use the active release")
    runtime_probe = run_controller_command(
        runner,
        controller_user,
        controller_home,
        [
            f"{hermes_real_source}/venv/bin/python",
            "-c",
            (
                "from agent.system_prompt import runtime_context_fingerprint; "
                "from gateway.run import GatewayRunner; "
                "from hermes_state import SessionDB; "
                "assert callable(runtime_context_fingerprint); "
                "assert callable(GatewayRunner._extract_cache_busting_config); "
                "assert callable(SessionDB.update_runtime_context)"
            ),
        ],
        check=False,
    )
    if runtime_probe.returncode:
        failures.append("controller Hermes does not import the patched runtime")
    synced_release = (
        Path(controller_home) / ".hermes/aidee-upstream/SYNCED_RELEASE"
    )
    if not synced_release.is_file() or synced_release.read_text().strip() != release:
        failures.append("controller knowledge release does not match")
    for service in (
        "aidee-admin.service",
        "aidee-controller-dashboard.service",
        "hermes-gateway.service",
    ):
        active = runner.run(
            ["systemctl", "is-active", service], check=False
        ).stdout.strip()
        if active != "active":
            failures.append(f"service is not active: {service}")
    cron_result = run_controller_command(
        runner, controller_user, controller_home,
        [f"{controller_home}/.local/bin/hermes", "cron", "list", "--all"],
    )
    for job in (UPDATE_JOB, WATCHDOG_JOB):
        if job not in cron_result.stdout:
            failures.append(f"controller cron is missing: {job}")
    controller_status_path = (
        state_root / "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json"
    )
    try:
        controller_status = json.loads(controller_status_path.read_text())
        if (
            controller_status.get("schema_version") != 2
            or controller_status.get("role") != "controller"
            or controller_status.get("steps", {})
            .get("default_crons", {})
            .get("status")
            != "completed"
        ):
            failures.append("controller onboarding status is invalid")
    except (OSError, json.JSONDecodeError):
        failures.append("controller onboarding status is invalid")
    registry = expected_registry or load_registry(
        state_root / "fleet/registry.yaml"
    )
    sys.path.insert(0, str(source / "platform/admin"))
    from assistant_state import (
        ONBOARDING_RELATIVE_PATH,
        STEP_STATES,
        build_soul_document,
    )
    setup_dir = source / "platform/setup"
    if str(setup_dir) not in sys.path:
        sys.path.insert(0, str(setup_dir))
    from onboarding_state import SCHEMA_VERSION, step_definitions
    owner = owner_name(Path("/etc/aidee/owner.json"))
    for assistant in registry["assistants"]:
        assistant_id = assistant["id"]
        runtime = state_root / f"runtime/assistants/{assistant_id}/data"
        name = assistant.get("container_name") or f"aidee-{assistant_id}"
        if container_image(runner, name) != image_id:
            failures.append(f"assistant image mismatch: {assistant_id}")
        proxy = f"{name}-dashboard-proxy"
        if container_image(runner, proxy) != image_id:
            failures.append(f"assistant proxy image mismatch: {assistant_id}")
        for container in (name, proxy):
            state = runner.run(
                ["docker", "inspect", container, "--format", "{{.State.Status}}"],
                check=False,
            ).stdout.strip()
            if state != "running":
                failures.append(f"container is not running: {container}")
        health = runner.run(
            [
                "docker",
                "inspect",
                name,
                "--format",
                "{{if .State.Health}}{{.State.Health.Status}}{{end}}",
            ],
            check=False,
        ).stdout.strip()
        if health != "healthy":
            failures.append(f"assistant is not healthy: {assistant_id}")
        dashboard_code = dashboard_response(runner, assistant)
        if dashboard_code.returncode or not re.fullmatch(
            r"[234][0-9]{2}", dashboard_code.stdout
        ):
            failures.append(f"assistant dashboard is unreachable: {assistant_id}")
        repos = runtime / "aidee/repos"
        if (
            not repos.is_dir()
            or (repos.stat().st_mode & 0o777) != 0o770
            or repos.stat().st_uid != 10000
            or repos.stat().st_gid != controller_gid
        ):
            failures.append(f"repository directory mismatch: {assistant_id}")
        onboarding = runtime / ONBOARDING_RELATIVE_PATH
        if not onboarding.is_file():
            failures.append(f"onboarding status missing: {assistant_id}")
        else:
            try:
                status = json.loads(onboarding.read_text())
                runtime_config = yaml.safe_load(
                    (runtime / "config.yaml").read_text()
                ) or {}
                telegram = (
                    (runtime_config.get("platforms") or {}).get("telegram") or {}
                )
                dashboard = runtime_config.get("dashboard") or {}
                policy_config = {
                    "telegram_enabled": bool(telegram.get("enabled", True)),
                    "dashboard_menu_enabled": bool(dashboard.get("public_url")),
                }
                required = {
                    item["id"]
                    for item in step_definitions(
                        "assistant",
                        assistant.get("kind", "personal"),
                        policy_config,
                    )
                }
                steps = status.get("steps", {})
                if (
                    status.get("schema_version") != SCHEMA_VERSION
                    or status.get("role") != "assistant"
                    or not isinstance(steps, dict)
                    or set(steps) != required
                    or any(
                    not isinstance(step, dict)
                    or step.get("status") not in STEP_STATES
                    for step in steps.values()
                    )
                ):
                    failures.append(f"onboarding status invalid: {assistant_id}")
                rollup = status.get("rollup") or {}
                registry_rollup = assistant.get("onboarding") or {}
                if (
                    registry_rollup.get("required_remaining")
                    != len(rollup.get("incomplete_required", []))
                    or registry_rollup.get("optional_remaining")
                    != len(rollup.get("incomplete_optional", []))
                ):
                    failures.append(
                        f"onboarding registry rollup mismatch: {assistant_id}"
                    )
                enabled = (runtime_config.get("plugins") or {}).get("enabled") or []
                if "aidee-onboarding" not in enabled:
                    failures.append(
                        f"onboarding plugin is not enabled: {assistant_id}"
                    )
            except json.JSONDecodeError:
                failures.append(f"onboarding status invalid: {assistant_id}")
        tools = runner.run(
            [
                "docker",
                "exec",
                name,
                "test",
                "-x",
                "/opt/aidee/onboarding/onboarding-gate.py",
            ],
            check=False,
        )
        if tools.returncode:
            failures.append(f"onboarding tools missing: {assistant_id}")
        plugin = runner.run(
            [
                "docker",
                "exec",
                name,
                "test",
                "-f",
                "/opt/hermes/plugins/aidee-onboarding/plugin.yaml",
            ],
            check=False,
        )
        if plugin.returncode:
            failures.append(f"onboarding plugin missing: {assistant_id}")
        user_plugin = runner.run(
            [
                "docker",
                "exec",
                name,
                "test",
                "-f",
                "/opt/data/plugins/aidee-onboarding/plugin.yaml",
            ],
            check=False,
        )
        if user_plugin.returncode:
            failures.append(
                f"onboarding plugin is not installed in Hermes home: {assistant_id}"
            )
        fleet_dir = safe_state_path(
            state_root / "fleet",
            assistant.get("state_path") or f"assistants/{assistant_id}",
            "assistant state path",
        )
        desired_assistant = resolved_assistant(assistant, fleet_dir)
        if (runtime / "SOUL.md").read_text() != build_soul_document(
            desired_assistant, owner
        ):
            failures.append(f"assistant instructions mismatch: {assistant_id}")
        if not (
            fleet_dir / "assistant.yaml"
        ).is_file():
            failures.append(f"assistant config missing: {assistant_id}")
        if not (runtime / "config.yaml").is_file():
            failures.append(f"assistant runtime config missing: {assistant_id}")
        for skill in (source / "platform/shared-skills").iterdir():
            if (skill / "SKILL.md").is_file() and not (
                runtime / "skills" / skill.name / "SKILL.md"
            ).is_file():
                failures.append(f"assistant skill missing: {assistant_id}/{skill.name}")
    if failures:
        raise ReconcileError("verification failed: " + "; ".join(failures))


def action_plan(registry, release):
    actions = [
        f"build and validate the assistant image from exact release {release}",
        "apply pending versioned migrations with backups",
        f"activate exact host release {release}",
        "update the pinned controller Hermes runtime if needed",
        "refresh root-owned services and Hermes plugins",
        "refresh controller skills and controller-only default crons",
    ]
    actions.extend(
        f"reconcile and replace assistant {item.get('id', '<invalid>')}"
        for item in registry.get("assistants", [])
    )
    actions.append("verify host, controller, crons, image, containers, and assistant state")
    return actions


def validate_candidate(candidate, release):
    if not re.fullmatch(RELEASE_PATTERN, release):
        raise ReconcileError("release has an invalid format")
    if candidate.is_symlink() or not (candidate / ".git").is_dir():
        raise ReconcileError("candidate is not a release checkout")
    tag = subprocess.run(
        ["git", "-C", str(candidate), "describe", "--tags", "--exact-match"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(candidate), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if tag != release or status:
        raise ReconcileError(f"candidate is not the clean exact tag {release}")
    try:
        marker = (candidate / "LATEST").read_text().strip()
    except OSError as error:
        raise ReconcileError(f"cannot read candidate release marker: {error}") from error
    if marker != release:
        raise ReconcileError("candidate release marker does not match")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--mode", choices=("preview", "apply"), required=True)
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--owner-name")
    parser.add_argument("--state-root", type=Path, default=Path("/var/lib/aidee"))
    parser.add_argument("--code-root", type=Path, default=Path("/opt/aidee"))
    parser.add_argument("--controller-user", default="aidee-controller")
    return parser.parse_args()


def main():
    arguments = parse_args()
    if arguments.mode == "apply" and not arguments.approved:
        print("error: apply requires explicit owner approval", file=sys.stderr)
        return 2
    candidate = arguments.candidate.resolve()
    validate_candidate(candidate, arguments.release)
    requested_owner = (
        normalize_owner_name(arguments.owner_name)
        if arguments.owner_name is not None
        else None
    )
    registry_path = arguments.state_root / "fleet/registry.yaml"
    registry = load_registry(registry_path)
    print("Aidee fleet update plan:")
    for action in action_plan(registry, arguments.release):
        print(f"  - {action}")
    if arguments.mode == "preview":
        print("Preview complete. No active host, controller, or assistant state changed.")
        return 0

    runner = Runner()
    reporter = StepReporter(action_plan(registry, arguments.release))
    controller_home, controller_uid, controller_gid = controller_account(
        arguments.controller_user
    )
    controller_home = str(controller_home)
    reporter.next()
    runner.run(
        [str(candidate / "platform/scripts/build-assistant-image.sh")],
        stream=True,
    )
    runner.run(
        [str(candidate / "platform/scripts/validate-assistant-image.sh")],
        stream=True,
    )
    image_id = validated_image(candidate, arguments.release)
    if requested_owner:
        atomic_write(
            Path("/etc/aidee/owner.json"),
            json.dumps({"name": requested_owner}, indent=2) + "\n",
            0o644,
        )
    reporter.next()
    run_migrations(candidate, arguments.state_root)
    reporter.next()
    activate_release(candidate, arguments.release, arguments.code_root)
    source = arguments.code_root / "source"
    reporter.next()
    runner.run(
        [
            str(source / "platform/scripts/update-controller-runtime.sh"),
            "--approved",
        ],
        stream=True,
    )
    reporter.next()
    runner.run(
        [str(source / "platform/scripts/install-admin-helper.sh")],
        stream=True,
    )
    runner.run(
        [str(source / "platform/scripts/install-dashboard-plugins.sh")],
        stream=True,
    )
    runner.run(
        [str(source / "platform/scripts/install-controller-service.sh")],
        stream=True,
    )
    gateway_installer = source / "platform/scripts/install-controller-gateway.sh"
    if gateway_installer.is_file():
        runner.run([str(gateway_installer)], stream=True)
    reporter.next()
    run_controller_command(
        runner,
        arguments.controller_user,
        controller_home,
        [
            "env",
            f"AIDEE_REPOSITORY={source.as_uri()}",
            str(source / "platform/scripts/sync-controller.sh"),
            "--release",
            arguments.release,
            "--apply",
            "--approved",
            "--skip-fleet-sync",
        ],
        stream=True,
    )
    controller_status = reconcile_controller_onboarding(
        source,
        arguments.state_root,
        owner_name(Path("/etc/aidee/owner.json")),
    )
    run_controller_command(
        runner,
        arguments.controller_user,
        controller_home,
        [
            "env",
            f"AIDEE_STATE_DIR={arguments.state_root}",
            "python3",
            str(source / "platform/controller-tools/install-default-crons.py"),
            "--approved",
            "--status-file",
            str(controller_status),
        ],
    )
    registry, changed_files = sync_assistant_state(
        source,
        arguments.state_root,
        owner_name(Path("/etc/aidee/owner.json")),
        controller_uid,
        controller_gid,
    )
    replaced_assistants = []
    try:
        for assistant in registry["assistants"]:
            reporter.next()
            replaced = replace_container_pair(
                runner,
                assistant,
                image_id,
                arguments.state_root,
                controller_gid,
                retain_backup=True,
            )
            if replaced:
                replaced_assistants.append(assistant)
            elif assistant["id"] in changed_files:
                name = assistant.get("container_name") or f"aidee-{assistant['id']}"
                runner.run(["docker", "restart", name])
                proxy = f"{name}-dashboard-proxy"
                if container_image(runner, proxy):
                    runner.run(["docker", "restart", proxy])
                wait_healthy(runner, name)
                wait_healthy(runner, proxy)
                wait_dashboard(runner, assistant)
        reporter.next()
        verify(
            runner,
            arguments.release,
            source,
            arguments.state_root,
            arguments.controller_user,
            controller_home,
            image_id,
            registry,
        )
        update_registry(registry_path, registry, arguments.release, image_id)
    except Exception:
        for assistant in reversed(replaced_assistants):
            rollback_container_pair(runner, assistant)
        raise
    cleanup_failures = []
    for assistant in replaced_assistants:
        cleanup_failures.extend(finalize_container_pair(runner, assistant))
    if cleanup_failures:
        print(
            "warning: stale rollback containers require cleanup: "
            + ", ".join(cleanup_failures),
            file=sys.stderr,
        )
    print(f"Aidee fleet updated and verified at {arguments.release}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReconcileError, OSError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
