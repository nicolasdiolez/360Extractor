#!/usr/bin/env python3
"""Release consistency guard.

Three releases in a row shipped with something out of sync (pyproject stuck on
an old version, a changelog entry that never got written, a tag that did not
match). This script makes that impossible by refusing a release unless every
source of truth agrees:

1. ``version.py`` holds a valid ``X.Y.Z``.
2. ``pyproject.toml`` still derives its version from ``version.py`` (dynamic),
   so the two can never drift apart again.
3. The newest *versioned* CHANGELOG entry matches ``version.py`` — ``[Unreleased]``
   is ignored on purpose, so work in progress does not have to be versioned.
4. That CHANGELOG entry actually has content.
5. On a tagged release, the tag matches the version and uses the canonical
   ``vX.Y.Z`` form.

Stdlib only: it runs in CI and in the release workflow before any install.

Examples
--------
    python scripts/check_release.py                # version.py <-> CHANGELOG
    python scripts/check_release.py --tag v4.0.0   # ... and the tag too
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_notes import (  # noqa: E402
    SEMVER_RE,
    extract_notes,
    latest_released_version,
    normalize_version,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "src" / "extractor360" / "core" / "version.py"
CHANGELOG_FILE = REPO_ROOT / "CHANGELOG.md"
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"

CANONICAL_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")

# Tags cut before the canonical vX.Y.Z convention was enforced. They are
# grandfathered so re-running the guard against them still works; any *new*
# tag must use the three-component form.
LEGACY_TAGS = frozenset({"v3.0", "v3.1", "v3.2", "v3.3"})


def read_version(version_file: Path) -> str | None:
    """Read ``VERSION`` from version.py without importing it (no deps, no side effects)."""
    tree = ast.parse(version_file.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "VERSION":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    return None


def pyproject_version_is_dynamic(text: str) -> bool:
    """True when pyproject derives the version from version.py rather than hard-coding it.

    Guards against the exact regression of issue #7, where pyproject declared a
    static version that silently fell behind version.py.
    """
    in_project = False
    has_dynamic = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("["):
            in_project = line == "[project]"
            continue
        if not in_project or line.startswith("#"):
            continue
        if re.match(r"^version\s*=", line):
            return False  # a static version in [project] — exactly what we forbid
        if re.match(r"^dynamic\s*=", line) and "version" in line:
            has_dynamic = True
    return has_dynamic


def check(tag: str | None = None) -> list[str]:
    """Run every consistency check and return the list of failures (empty == OK)."""
    errors: list[str] = []

    version = read_version(VERSION_FILE)
    if not version:
        return [f"could not find VERSION in {VERSION_FILE.relative_to(REPO_ROOT)}"]
    if not SEMVER_RE.match(version):
        errors.append(f"VERSION '{version}' is not a valid X.Y.Z version")

    # pyproject must stay dynamic so it can never drift from version.py again.
    if not pyproject_version_is_dynamic(PYPROJECT_FILE.read_text(encoding="utf-8")):
        errors.append(
            "pyproject.toml must declare dynamic = [\"version\"] (derived from "
            "extractor360.core.version) instead of a hard-coded version"
        )

    changelog = CHANGELOG_FILE.read_text(encoding="utf-8")
    latest = latest_released_version(changelog)
    if latest is None:
        errors.append("CHANGELOG.md has no versioned entry")
    elif latest != version:
        errors.append(
            f"version.py says {version} but the newest versioned CHANGELOG entry is "
            f"{latest} — add a '## [{version}] - YYYY-MM-DD' section (or fix version.py)"
        )
    else:
        try:
            extract_notes(changelog, [version])
        except (KeyError, ValueError) as exc:
            errors.append(f"CHANGELOG entry for {version} is unusable: {exc}")

    if tag:
        if tag not in LEGACY_TAGS and not CANONICAL_TAG_RE.match(tag):
            errors.append(f"tag '{tag}' must use the canonical form vX.Y.Z (e.g. v{version})")
        if normalize_version(tag) != version:
            errors.append(f"tag '{tag}' does not match version.py ({version})")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="Git tag being released (e.g. v4.0.0)")
    args = parser.parse_args(argv)

    errors = check(args.tag)
    if errors:
        print("Release consistency check FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    version = read_version(VERSION_FILE)
    scope = f"version {version}" + (f", tag {args.tag}" if args.tag else "")
    print(f"Release consistency check passed ({scope}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
