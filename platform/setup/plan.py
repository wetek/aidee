#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path


RELEASE = "v0.1.0-alpha.9"
EXPERIENCE = {"beginner", "guided", "advanced"}
DASHBOARD_ACCESS = {"tailscale", "ssh_tunnel"}
MESSAGING = {"telegram", "discord", "slack"}
ASSISTANT_KINDS = {"personal", "coding", "client", "project"}
CODING_AGENTS = {"opencode", "claude_code", "codex", "none"}
AUTHORITIES = {
    "investigate_only",
    "pull_request",
    "approved_merge_deploy",
}
PRIVATE_GIT = {"later", "disabled"}
GIT_PROVIDERS = {"github", "gitlab", "other", None}
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class PlanError(ValueError):
    pass


def require_object(value, path):
    if not isinstance(value, dict):
        raise PlanError(f"{path} must be an object")
    return value


def require_exact_keys(value, required, optional, path):
    keys = set(value)
    missing = required - keys
    unknown = keys - required - optional
    if missing:
        raise PlanError(f"{path} is missing: {', '.join(sorted(missing))}")
    if unknown:
        raise PlanError(f"{path} has unknown fields: {', '.join(sorted(unknown))}")


def require_text(value, path, maximum):
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"{path} must be non-empty text")
    if "\n" in value or len(value) > maximum:
        raise PlanError(f"{path} must be one line and at most {maximum} characters")


def require_choice(value, choices, path):
    if value not in choices:
        allowed = ", ".join(sorted(str(choice) for choice in choices))
        raise PlanError(f"{path} must be one of: {allowed}")


def validate(plan):
    require_object(plan, "plan")
    require_exact_keys(
        plan,
        {
            "schema_version",
            "release",
            "owner",
            "server",
            "controller",
            "fleet",
            "recovery",
            "updates",
        },
        set(),
        "plan",
    )
    if plan["schema_version"] != 1:
        raise PlanError("schema_version must be 1")
    if plan["release"] != RELEASE:
        raise PlanError(f"release must be {RELEASE}")

    owner = require_object(plan["owner"], "owner")
    require_exact_keys(owner, {"name", "experience"}, set(), "owner")
    require_text(owner["name"], "owner.name", 100)
    require_choice(owner["experience"], EXPERIENCE, "owner.experience")

    server = require_object(plan["server"], "server")
    require_exact_keys(
        server, {"provider", "dashboard_access"}, set(), "server"
    )
    require_text(server["provider"], "server.provider", 100)
    if not IDENTIFIER.fullmatch(server["provider"]):
        raise PlanError(
            "server.provider must use lowercase letters, numbers, hyphens, or underscores"
        )
    require_choice(
        server["dashboard_access"],
        DASHBOARD_ACCESS,
        "server.dashboard_access",
    )

    controller = require_object(plan["controller"], "controller")
    require_exact_keys(
        controller,
        {"model_provider", "messaging", "telegram"},
        set(),
        "controller",
    )
    require_text(controller["model_provider"], "controller.model_provider", 100)
    if not IDENTIFIER.fullmatch(controller["model_provider"]):
        raise PlanError(
            "controller.model_provider must use lowercase letters, numbers, "
            "hyphens, or underscores"
        )
    if not isinstance(controller["messaging"], list):
        raise PlanError("controller.messaging must be a list")
    if len(controller["messaging"]) != len(set(controller["messaging"])):
        raise PlanError("controller.messaging cannot contain duplicates")
    for index, messaging in enumerate(controller["messaging"]):
        require_choice(
            messaging, MESSAGING, f"controller.messaging[{index}]"
        )

    telegram = controller["telegram"]
    if "telegram" in controller["messaging"]:
        telegram = require_object(telegram, "controller.telegram")
        require_exact_keys(
            telegram,
            {"access", "branding", "avatar", "menu_button"},
            set(),
            "controller.telegram",
        )
        require_choice(
            telegram["access"], {"pairing", "allowlist"}, "controller.telegram.access"
        )
        require_choice(
            telegram["branding"], {"offer"}, "controller.telegram.branding"
        )
        require_choice(
            telegram["avatar"],
            {"generate_or_upload"},
            "controller.telegram.avatar",
        )
        if not isinstance(telegram["menu_button"], bool):
            raise PlanError("controller.telegram.menu_button must be true or false")
        if (
            telegram["menu_button"]
            and server["dashboard_access"] == "ssh_tunnel"
        ):
            raise PlanError(
                "Telegram menu button requires persistent dashboard access"
            )
    elif telegram is not None:
        raise PlanError(
            "controller.telegram must be null when Telegram is not selected"
        )

    fleet = require_object(plan["fleet"], "fleet")
    require_exact_keys(fleet, {"assistants"}, set(), "fleet")
    if not isinstance(fleet["assistants"], list):
        raise PlanError("fleet.assistants must be a list")
    for index, assistant in enumerate(fleet["assistants"]):
        path = f"fleet.assistants[{index}]"
        require_object(assistant, path)
        require_exact_keys(
            assistant,
            {"name", "kind", "purpose", "coding_agent", "authority"},
            {"repository"},
            path,
        )
        require_text(assistant["name"], f"{path}.name", 100)
        require_text(assistant["purpose"], f"{path}.purpose", 500)
        require_choice(assistant["kind"], ASSISTANT_KINDS, f"{path}.kind")
        require_choice(
            assistant["coding_agent"],
            CODING_AGENTS,
            f"{path}.coding_agent",
        )
        require_choice(
            assistant["authority"], AUTHORITIES, f"{path}.authority"
        )
        repository = assistant.get("repository")
        if repository is not None:
            require_text(repository, f"{path}.repository", 500)

    recovery = require_object(plan["recovery"], "recovery")
    require_exact_keys(
        recovery, {"private_git"}, {"provider"}, "recovery"
    )
    require_choice(recovery["private_git"], PRIVATE_GIT, "recovery.private_git")
    require_choice(recovery.get("provider"), GIT_PROVIDERS, "recovery.provider")

    updates = require_object(plan["updates"], "updates")
    require_exact_keys(updates, {"daily_check"}, set(), "updates")
    if not isinstance(updates["daily_check"], bool):
        raise PlanError("updates.daily_check must be true or false")
    if updates["daily_check"] and "telegram" not in controller["messaging"]:
        raise PlanError("daily update checks require Telegram in Alpha 6")


def read_plan(path):
    try:
        plan = json.loads(path.read_text())
    except FileNotFoundError as error:
        raise PlanError(f"plan file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise PlanError(
            f"invalid JSON at line {error.lineno}, column {error.colno}"
        ) from error
    validate(plan)
    return plan


def get_value(plan, dotted_path):
    value = plan
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise PlanError(f"unknown plan field: {dotted_path}")
        value = value[part]
    if isinstance(value, (dict, list)):
        print(json.dumps(value, separators=(",", ":")))
    elif isinstance(value, bool):
        print(str(value).lower())
    elif value is None:
        print("")
    else:
        print(value)


def print_summary(plan):
    print("# Aidee setup summary")
    print()
    print(f"Owner: {plan['owner']['name']}")
    print(f"Experience: {plan['owner']['experience']}")
    print(f"Server provider: {plan['server']['provider']}")
    print(f"Dashboard access: {plan['server']['dashboard_access']}")
    print(f"Model provider: {plan['controller']['model_provider']}")
    messaging = ", ".join(plan["controller"]["messaging"]) or "none"
    print(f"Messaging: {messaging}")
    telegram = plan["controller"]["telegram"]
    if telegram is not None:
        print(f"Telegram access: {telegram['access']}")
        print(f"Telegram branding: {telegram['branding']}")
        print(f"Telegram menu button: {str(telegram['menu_button']).lower()}")
    print(f"Private Git backup: {plan['recovery']['private_git']}")
    print(
        "Daily update check: "
        f"{str(plan['updates']['daily_check']).lower()}"
    )
    print()
    print("Planned assistants:")
    if not plan["fleet"]["assistants"]:
        print("- None")
    for assistant in plan["fleet"]["assistants"]:
        print(
            f"- {assistant['name']}: {assistant['kind']}, "
            f"{assistant['coding_agent']}, {assistant['authority']}"
        )
    print()
    print("This summary contains no credentials.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--get")
    action.add_argument("--summary", action="store_true")
    arguments = parser.parse_args()

    try:
        plan = read_plan(arguments.plan)
        if arguments.get:
            get_value(plan, arguments.get)
        elif arguments.summary:
            print_summary(plan)
        else:
            print("Setup plan is valid.")
    except PlanError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
