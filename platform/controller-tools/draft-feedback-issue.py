#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlencode


ISSUE_URL = "https://github.com/wetek/aidee/issues/new"
KINDS = ("bug", "docs", "feature", "insight")
MAX_TITLE = 80
MAX_BODY = 1500
MAX_URL = 3500

SECRET_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\d{8,}:[A-Za-z0-9_-]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*\S+"),
)


class DraftError(ValueError):
    pass


def require_text(value, path, maximum):
    if not isinstance(value, str) or not value.strip():
        raise DraftError(f"{path} must be non-empty text")
    text = value.strip()
    if len(text) > maximum:
        raise DraftError(f"{path} must be at most {maximum} characters")
    return text


def reject_secrets(text, path):
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise DraftError(f"{path} looks like it contains a secret")


def compose_body(kind, body, host_release, knowledge_release, channel):
    lines = [f"Kind: {kind}"]
    if host_release:
        lines.append(f"Host release: {host_release}")
    if knowledge_release:
        lines.append(f"Knowledge release: {knowledge_release}")
    if channel:
        lines.append(f"Channel: {channel}")
    return "\n".join(lines) + "\n\n" + body


def build_url(title, body):
    return f"{ISSUE_URL}?{urlencode({'title': title, 'body': body, 'labels': 'feedback'})}"


def draft(title, kind, body, host_release=None, knowledge_release=None, channel=None):
    title = require_text(title, "title", MAX_TITLE)
    if "\n" in title:
        raise DraftError("title must be one line")
    if kind not in KINDS:
        raise DraftError(f"kind must be one of: {', '.join(KINDS)}")
    body = require_text(body, "body", MAX_BODY)
    reject_secrets(title, "title")
    reject_secrets(body, "body")
    for value, path in (
        (host_release, "host-release"),
        (knowledge_release, "knowledge-release"),
        (channel, "channel"),
    ):
        if value:
            require_text(value, path, 80)
            if "\n" in value:
                raise DraftError(f"{path} must be one line")
            reject_secrets(value, path)
    composed = compose_body(kind, body, host_release, knowledge_release, channel)
    url = build_url(title, composed)
    if len(url) > MAX_URL:
        raise DraftError("draft is too long for a Telegram submit link. Shorten the body")
    return title, composed, url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--body")
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--host-release")
    parser.add_argument("--knowledge-release")
    parser.add_argument("--channel")
    arguments = parser.parse_args()

    if bool(arguments.body) == bool(arguments.body_file):
        print("error: provide exactly one of --body or --body-file", file=sys.stderr)
        return 1

    if arguments.body_file:
        try:
            body = arguments.body_file.read_text()
        except OSError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    else:
        body = arguments.body

    try:
        title, composed, url = draft(
            arguments.title,
            arguments.kind,
            body,
            arguments.host_release,
            arguments.knowledge_release,
            arguments.channel,
        )
    except DraftError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(title)
    print()
    print(composed)
    print()
    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
