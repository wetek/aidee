#!/usr/bin/env python3
import json
import os
import stat
import tempfile
from pathlib import Path

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]


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

    jsonschema.validate(registry, registry_schema)
    jsonschema.validate(assistant, assistant_schema)


def validate_yaml():
    for path in [
        ROOT / "platform" / "defaults" / "assistant.yaml",
        ROOT / "platform" / "policies" / "state-tracking.yaml",
    ]:
        load_yaml_text(path)


def validate_scripts():
    scripts = list((ROOT / "platform" / "scripts").glob("*.sh"))
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
    required_prompt_paths = [
        "docs/setup.md",
        "docs/wizard-style.md",
        "platform/shared-skills/unslop/SKILL.md",
    ]
    for path in required_prompt_paths:
        if path not in readme:
            raise AssertionError(f"README setup prompt does not reference {path}")

    wizard_style = (ROOT / "docs" / "wizard-style.md").read_text()
    for required_text in [
        "Ask one question per message.",
        "Aidee setup [2/6]",
        "Reply `approve` to begin",
    ]:
        if required_text not in wizard_style:
            raise AssertionError(
                f"Wizard response format is missing: {required_text}"
            )


if __name__ == "__main__":
    validate_schemas()
    validate_yaml()
    validate_scripts()
    validate_fleet_initialization()
    validate_setup_guidance()
    print("Repository validation passed.")
