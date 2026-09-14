#!/usr/bin/env python3
"""Read the published Aidee tag from LATEST."""

import copy
import json
import re
from pathlib import Path


RELEASE_PATTERN = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+$")
TOKEN = "LATEST"
REPO_ROOT = Path(__file__).resolve().parents[1]


def latest(root=None):
    base = Path(root) if root is not None else REPO_ROOT
    path = base / "LATEST"
    try:
        tag = path.read_text().strip()
    except OSError as error:
        raise ValueError(f"cannot read {path}") from error
    if not RELEASE_PATTERN.fullmatch(tag):
        raise ValueError(f"LATEST is not a published tag: {tag}")
    return tag


def bind_latest(data, release=None):
    release = latest() if release is None else release
    if isinstance(data, dict):
        bound = {}
        for key, value in data.items():
            if key in {"release", "image_version"} and value == TOKEN:
                bound[key] = release
            else:
                bound[key] = bind_latest(value, release)
        return bound
    if isinstance(data, list):
        return [bind_latest(item, release) for item in data]
    return data


def pin_schema(schema, release=None):
    pinned = copy.deepcopy(schema)
    release = latest() if release is None else release
    schema_id = pinned.get("$id", "")
    if schema_id.endswith(":setup-plan:1"):
        pinned["properties"]["release"]["const"] = release
    elif schema_id.endswith(":assistant-request:1"):
        pinned["$defs"]["assistant"]["properties"]["image_version"]["const"] = (
            release
        )
    return pinned


def load_schema(path, release=None):
    return pin_schema(json.loads(Path(path).read_text()), release)
