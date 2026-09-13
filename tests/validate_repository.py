#!/usr/bin/env python3
import json
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
LOCAL_ONLY_DIRECTORIES = {".agents", ".cursor", ".git", ".venv"}


def load_json(path: Path):
    return json.loads(path.read_text())


def load_yaml_text(path: Path, replacements=None):
    text = path.read_text()
    for old, new in (replacements or {}).items():
        text = text.replace(old, new)
    return yaml.safe_load(text)


def validate_schemas():
    registry_schema = load_json(
        ROOT / "platform" / "schemas" / "fleet-registry.schema.json"
    )
    assistant_schema = load_json(
        ROOT / "platform" / "schemas" / "assistant-config.schema.json"
    )
    setup_plan_schema = load_json(
        ROOT / "platform" / "schemas" / "setup-plan.schema.json"
    )
    telegram_profile_schema = load_json(
        ROOT / "platform" / "schemas" / "telegram-profile.schema.json"
    )

    registry = load_yaml_text(
        ROOT / "fleet-template" / "registry.yaml.template",
        {"{{ aidee_repository_url }}": "https://example.com/aidee.git"},
    )
    assistant = load_yaml_text(
        ROOT
        / "fleet-template"
        / "assistants"
        / "_template"
        / "config.yaml.template",
        {
            "{{ assistant_id }}": "pilot",
            "{{ assistant_name }}": "Pilot",
            "{{ assistant_kind }}": "personal",
            "{{ purpose }}": "Validate Aidee",
        },
    )
    setup_plan = load_json(
        ROOT / "fleet-template" / "setup-plan.json.example"
    )
    telegram_profile = load_json(
        ROOT / "fleet-template" / "telegram-profile.json.example"
    )

    jsonschema.validate(registry, registry_schema)
    jsonschema.validate(assistant, assistant_schema)
    jsonschema.validate(setup_plan, setup_plan_schema)
    jsonschema.validate(telegram_profile, telegram_profile_schema)


def validate_yaml():
    for path in [
        ROOT / "platform" / "defaults" / "assistant.yaml",
        ROOT / "platform" / "policies" / "state-tracking.yaml",
    ]:
        load_yaml_text(path)


def validate_scripts():
    scripts = list((ROOT / "platform" / "scripts").glob("*.sh"))
    scripts.append(ROOT / "setup.sh")
    if not scripts:
        raise AssertionError("No platform scripts found")

    for path in scripts:
        mode = path.stat().st_mode
        if not mode & stat.S_IXUSR:
            raise AssertionError(f"Script is not executable: {path.relative_to(ROOT)}")

        text = path.read_text()
        if " +  " in text:
            raise AssertionError(
                f"Possible patch artifact in {path.relative_to(ROOT)}"
            )

    python_tools = [
        ROOT / "platform" / "setup" / "plan.py",
        *list((ROOT / "platform" / "controller-tools").glob("*.py")),
    ]
    for path in python_tools:
        mode = path.stat().st_mode
        if not mode & stat.S_IXUSR:
            raise AssertionError(f"Tool is not executable: {path.relative_to(ROOT)}")


def validate_fleet_initialization():
    script = ROOT / "platform" / "scripts" / "init-fleet.sh"
    with tempfile.TemporaryDirectory() as temporary_directory:
        state_dir = Path(temporary_directory)
        result = os.spawnve(
            os.P_WAIT,
            "/bin/bash",
            [
                "bash",
                str(script),
                "--owner-name",
                "Example Owner",
                "--repository-url",
                "https://example.com/aidee.git",
            ],
            {**os.environ, "AIDEE_STATE_DIR": str(state_dir)},
        )
        if result != 0:
            raise AssertionError("Fleet initialization failed")

        registry = state_dir / "fleet" / "registry.yaml"
        controller_soul = state_dir / "fleet" / "controller" / "SOUL.md"
        if not registry.is_file() or not controller_soul.is_file():
            raise AssertionError("Fleet initialization omitted generated files")

        generated_text = registry.read_text() + controller_soul.read_text()
        if "{{" in generated_text or "}}" in generated_text:
            raise AssertionError("Generated fleet contains unresolved placeholders")


def validate_setup_guidance():
    skill_path = (
        ROOT / "platform" / "shared-skills" / "unslop" / "SKILL.md"
    )
    skill_text = skill_path.read_text()
    if len(skill_text.splitlines()) >= 500:
        raise AssertionError("Unslop SKILL.md must stay under 500 lines")

    parts = skill_text.split("---", 2)
    if len(parts) != 3:
        raise AssertionError("Unslop SKILL.md is missing YAML frontmatter")
    metadata = yaml.safe_load(parts[1])
    if metadata.get("name") != "unslop" or not metadata.get("description"):
        raise AssertionError("Unslop SKILL.md metadata is invalid")

    readme = (ROOT / "README.md").read_text()
    required_prompt_paths = ["docs/setup.md"]
    for path in required_prompt_paths:
        if path not in readme:
            raise AssertionError(f"README setup prompt does not reference {path}")

    for required_text in [
        "If the guide cannot be loaded, stop",
        "Complete all six interview sections",
        "Never pipe downloaded code into a shell",
    ]:
        if required_text not in readme:
            raise AssertionError(f"README setup prompt is missing: {required_text}")

    setup = (ROOT / "docs" / "setup.md").read_text()
    for state in ["interview", "plan", "approval", "install", "validate", "handoff"]:
        if f"`{state}`" not in setup:
            raise AssertionError(f"Setup state is missing: {state}")
    for required_text in [
        "sudo ./setup.sh --plan setup-plan.json",
        "sudo ./setup.sh",
        "SETUP_PLAN_JSON",
        "v0.1.0-alpha.3",
    ]:
        if required_text not in setup:
            raise AssertionError(f"Setup handoff is missing: {required_text}")

    wizard_style = (ROOT / "docs" / "wizard-style.md").read_text()
    for required_text in [
        "Ask one question per message.",
        "Aidee setup [2/6]",
        "Reply `approve` to begin",
        "Do not ask the owner to run any command during the interview",
        "Do not infer cloud firewall exposure from local listening ports",
    ]:
        if required_text not in wizard_style:
            raise AssertionError(
                f"Wizard response format is missing: {required_text}"
            )

    plan_tool = ROOT / "platform" / "setup" / "plan.py"
    example_plan = ROOT / "fleet-template" / "setup-plan.json.example"
    for command in [
        ["python3", str(plan_tool), str(example_plan)],
        ["bash", str(ROOT / "setup.sh"), "--check-plan", str(example_plan)],
    ]:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError(
                f"Setup plan validation command failed: {result.stderr}"
            )

    with tempfile.TemporaryDirectory() as temporary_directory:
        unsafe_plan = load_json(example_plan)
        unsafe_plan["controller"]["google_" + "api_key"] = "redacted"  # pragma: allowlist secret
        unsafe_path = Path(temporary_directory) / "unsafe-plan.json"
        unsafe_path.write_text(json.dumps(unsafe_plan))
        result = subprocess.run(
            ["python3", str(plan_tool), str(unsafe_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            raise AssertionError("Setup plan accepted a credential field")


def validate_document_paths():
    markdown_files = list(ROOT.rglob("*.md"))
    markdown_link = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    raw_repository_link = re.compile(
        r"https://raw\.githubusercontent\.com/wetek/aidee/main/"
        r"([A-Za-z0-9_./-]+)"
    )
    script_reference = re.compile(r"(platform/scripts/[a-z0-9-]+\.sh)")

    for document in markdown_files:
        if LOCAL_ONLY_DIRECTORIES.intersection(document.parts):
            continue

        text = document.read_text()
        for link in markdown_link.findall(text):
            if link.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = link.split("#", 1)[0]
            if target and not (document.parent / target).resolve().exists():
                raise AssertionError(
                    f"Broken link in {document.relative_to(ROOT)}: {link}"
                )

        for repository_path in raw_repository_link.findall(text):
            if not (ROOT / repository_path).is_file():
                raise AssertionError(
                    f"Broken raw repository link in "
                    f"{document.relative_to(ROOT)}: {repository_path}"
                )

        for script_path in script_reference.findall(text):
            if not (ROOT / script_path).is_file():
                raise AssertionError(
                    f"Broken script path in "
                    f"{document.relative_to(ROOT)}: {script_path}"
                )

        if "raw.githubusercontent.com/wetek/aidee/main/scripts/" in text:
            raise AssertionError(
                f"Document invents a root scripts directory: "
                f"{document.relative_to(ROOT)}"
            )


def validate_no_pipe_to_shell():
    for pattern in ("*.md", "*.sh"):
        for path in ROOT.rglob(pattern):
            if LOCAL_ONLY_DIRECTORIES.intersection(path.parts):
                continue
            for line_number, line in enumerate(path.read_text().splitlines(), 1):
                lower = line.lower()
                downloads = "curl " in lower or "wget " in lower
                pipes_to_shell = "|" in line and (
                    " bash" in lower or " sh" in lower
                )
                if downloads and pipes_to_shell:
                    raise AssertionError(
                        f"Unsafe pipe to shell in "
                        f"{path.relative_to(ROOT)}:{line_number}"
                    )


if __name__ == "__main__":
    validate_schemas()
    validate_yaml()
    validate_scripts()
    validate_fleet_initialization()
    validate_setup_guidance()
    validate_document_paths()
    validate_no_pipe_to_shell()
    print("Repository validation passed.")
