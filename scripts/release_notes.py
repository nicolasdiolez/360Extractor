#!/usr/bin/env python3
"""Extract release notes for one or more versions from CHANGELOG.md.

Used by the release workflow to turn the (already carefully written) CHANGELOG
into the body of a GitHub Release, so the notes never have to be retyped and
can never drift from the changelog.

Stdlib only: the release workflow runs this before installing any dependency.

Examples
--------
    python scripts/release_notes.py 4.0.0
    python scripts/release_notes.py v3.3 3.2.1 -o notes.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# "## [3.3.0] - 2026-07-13" / "## [Unreleased] — v4.0 foundation" / "## [1.0.0] - Initial Release"
HEADING_RE = re.compile(r"^##\s+\[(?P<version>[^\]]+)\]\s*(?P<rest>.*)$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def normalize_version(value: str) -> str:
    """Normalize a tag or version string to a bare ``X.Y.Z``.

    Accepts ``v3.3``, ``3.3``, ``v3.3.0`` and ``3.3.0`` — the repo's older tags
    used a two-component form (``v3.3`` for release 3.3.0), so they must still
    resolve to the right CHANGELOG section.
    """
    version = str(value).strip()
    if version.lower().startswith("v"):
        version = version[1:]
    parts = version.split(".")
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        version = f"{version}.0"
    return version


def parse_sections(text: str) -> list[dict]:
    """Return every ``## [...]`` section of the changelog, in document order."""
    sections: list[dict] = []
    current: dict | None = None

    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            if current is not None:
                sections.append(current)
            current = {
                "version": match.group("version").strip(),
                "heading": line,
                "body_lines": [],
            }
        elif current is not None:
            current["body_lines"].append(line)

    if current is not None:
        sections.append(current)

    for section in sections:
        section["body"] = "\n".join(section.pop("body_lines")).strip("\n")
    return sections


def released_sections(text: str) -> list[dict]:
    """Only the versioned sections — ``[Unreleased]`` is deliberately excluded."""
    return [s for s in parse_sections(text) if SEMVER_RE.match(s["version"])]


def latest_released_version(text: str) -> str | None:
    """The most recent versioned entry (the changelog is newest-first)."""
    sections = released_sections(text)
    return sections[0]["version"] if sections else None


def extract_notes(text: str, versions: list[str]) -> str:
    """Concatenate the notes of ``versions`` (already normalized), in order."""
    by_version = {s["version"]: s for s in parse_sections(text)}
    chunks: list[str] = []

    for version in versions:
        section = by_version.get(version)
        if section is None:
            raise KeyError(f"No CHANGELOG section for version {version}")
        body = section["body"].strip()
        if not body:
            raise ValueError(f"CHANGELOG section for {version} is empty")
        # When several versions are bundled into one release, keep a heading so
        # the reader can tell them apart.
        chunks.append(f"## {version}\n\n{body}" if len(versions) > 1 else body)

    return "\n\n".join(chunks).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("versions", nargs="+", help="Versions or tags (e.g. 4.0.0, v3.3)")
    parser.add_argument("--changelog", default="CHANGELOG.md", help="Path to CHANGELOG.md")
    parser.add_argument("-o", "--output", help="Write to this file instead of stdout")
    args = parser.parse_args(argv)

    text = Path(args.changelog).read_text(encoding="utf-8")
    versions = [normalize_version(v) for v in args.versions]

    try:
        notes = extract_notes(text, versions)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_text(notes, encoding="utf-8")
    else:
        sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
