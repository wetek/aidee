"""Inject a mandatory onboarding offer before the model answers."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ASSISTANT_STATUS = Path("/opt/data/aidee/onboarding-status.json")


def controller_status_path():
    root = Path(os.environ.get("AIDEE_STATE_DIR", "/var/lib/aidee"))
    return root / "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json"


def resolve_target():
    if ASSISTANT_STATUS.is_file():
        kind = None
        try:
            kind = json.loads(ASSISTANT_STATUS.read_text()).get("assistant_kind")
        except (OSError, json.JSONDecodeError, AttributeError):
            kind = None
        return ASSISTANT_STATUS, "assistant", kind or os.environ.get(
            "AIDEE_ASSISTANT_KIND"
        )
    controller = controller_status_path()
    if controller.is_file():
        return controller, "controller", None
    return None


def load_gate():
    roots = [
        Path("/opt/aidee/onboarding"),
        Path("/usr/local/lib/aidee"),
        Path("/opt/aidee/source/platform/setup"),
        Path(__file__).resolve().parents[2] / "setup",
    ]
    for root in roots:
        if (root / "onboarding_state.py").is_file():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from onboarding_state import gate

            return gate
    return None


def offer_context(role, assistant_kind, first_step):
    step = first_step or "the first incomplete required step"
    if role == "assistant":
        kind = assistant_kind or "personal"
        decide = (
            "/opt/aidee/onboarding/onboarding-gate.py "
            "--status-file /opt/data/aidee/onboarding-status.json "
            f"--role assistant --assistant-kind {kind} --mode decide"
        )
    else:
        decide = (
            "/opt/aidee/source/platform/setup/onboarding-gate.py "
            "--status-file /var/lib/aidee/fleet/controller/"
            "CONTROLLER_ONBOARDING_STATUS.json "
            "--role controller --mode decide"
        )
    return (
        "AIDEE ONBOARDING OFFER. Required setup is incomplete. "
        f"The first incomplete required step is {step}. "
        "Before any greeting or other reply, run this command:\n"
        f"{decide}\n"
        "Then send one Telegram clarify whose only options are Resume now "
        "and Not now. That clarify is the entire reply. Do not greet. "
        "Do not answer the user yet. Record Resume now with --mode resume-now "
        "and Not now with --mode not-now."
    )


def continue_context(role, assistant_kind, first_step):
    step = first_step or "the first incomplete required step"
    return (
        "AIDEE ONBOARDING CONTINUE. The owner already chose Resume now. "
        f"Required setup is still incomplete. The current step is {step}. "
        "Do not greet. Continue that step now. "
        "The Telegram dashboard menu URL must equal dashboard.public_url "
        "in config.yaml. Do not invent a Tailscale URL. "
        "Set Telegram descriptions for the default profile and language_code en. "
        "Do not put dashboard URLs in bio or description."
    )


def should_inject(result):
    if not isinstance(result, dict):
        return False
    if result.get("decision") == "offer":
        return True
    rollup = result.get("rollup") or {}
    prompt = result.get("prompt") or {}
    if not rollup.get("incomplete_required"):
        return False
    response = prompt.get("response")
    return response is None or response == "resume_now"


def on_pre_llm_call(**_kwargs):
    try:
        target = resolve_target()
        if target is None:
            return None
        path, role, kind = target
        gate = load_gate()
        if gate is None:
            return None
        result = gate(path, role, assistant_kind=kind, action="inspect")
        if not should_inject(result):
            return None
        prompt = result.get("prompt") or {}
        first = result.get("first_incomplete_required")
        if prompt.get("response") == "resume_now":
            context = continue_context(role, kind, first)
        else:
            context = offer_context(role, kind, first)
        return {"context": context}
    except Exception:
        return None


def register(ctx):
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
