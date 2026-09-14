#!/usr/bin/env python3
"""Fail if relative Markdown links or heading fragments do not resolve."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
PUNCT_RE = re.compile(r"[^\w\s-]", re.UNICODE)
SPACE_RE = re.compile(r"[\s_]+")
HYPHEN_RE = re.compile(r"-{2,}")
MD_EMPHASIS_RE = re.compile(r"[*_`]+")
MD_LINK_TEXT_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def github_slug(heading: str) -> str:
    text = heading.strip()
    text = MD_LINK_TEXT_RE.sub(r"\1", text)
    text = MD_EMPHASIS_RE.sub("", text)
    text = text.lower()
    text = PUNCT_RE.sub("", text)
    text = SPACE_RE.sub("-", text)
    text = HYPHEN_RE.sub("-", text)
    return text.strip("-")


def heading_slugs(path: Path) -> set[str]:
    counts: dict[str, int] = defaultdict(int)
    slugs: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = HEADING_RE.match(raw)
        if not match:
            continue
        base = github_slug(match.group(2))
        if not base:
            continue
        n = counts[base]
        counts[base] += 1
        slugs.add(base if n == 0 else f"{base}-{n}")
    return slugs


def iter_markdown(root: Path) -> list[Path]:
    skip = {
        ".git",
        "node_modules",
        "dist",
        ".next",
        "__pycache__",
        "_broken_link_fixtures",
    }
    root = root.resolve()
    files: list[Path] = []
    for path in root.rglob("*.md"):
        relative = path.relative_to(root).parts
        if any(part in skip for part in relative[:-1]):
            continue
        files.append(path)
    return sorted(files)


def split_target(target: str) -> tuple[str, str | None]:
    if target.startswith("#"):
        return "", target[1:]
    if "#" in target:
        path, fragment = target.split("#", 1)
        return path, fragment
    return target, None


def should_skip(target: str) -> bool:
    lowered = target.strip().lower()
    if not lowered:
        return True
    if lowered.startswith(("<", "http://", "https://", "mailto:", "tel:")):
        return True
    if lowered.startswith(("ftp://", "data:", "javascript:")):
        return True
    return False


def check_file(path: Path, root: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    for match in LINK_RE.finditer(text):
        raw = match.group(1).strip()
        target = raw.split()[0].strip("<>") if raw else ""
        if should_skip(target):
            continue
        rel, fragment = split_target(target)
        if rel:
            dest = (path.parent / rel).resolve()
            try:
                dest.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{path}: {target} escapes the repository")
                continue
            if not dest.exists():
                errors.append(f"{path}: missing {target}")
                continue
        else:
            dest = path
        if fragment is None:
            continue
        if dest.suffix.lower() != ".md":
            continue
        if github_slug(fragment) not in heading_slugs(dest) and fragment not in heading_slugs(dest):
            errors.append(f"{path}: missing heading #{fragment} in {dest.relative_to(root)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to scan (default: current directory)",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    errors: list[str] = []
    for path in iter_markdown(root):
        errors.extend(check_file(path, root))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"{len(errors)} broken Markdown link(s).", file=sys.stderr)
        return 1
    print(f"OK: {len(iter_markdown(root))} Markdown files, no broken relative links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
