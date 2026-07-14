"""Unit tests for the release tooling (scripts/release_notes.py, scripts/check_release.py).

The consistency guard is the whole point of these scripts: three releases in a
row shipped out of sync. The tests below pin both the parsing rules and the
invariant that the repository itself is always release-consistent.
"""
import unittest

import check_release
from check_release import check, pyproject_version_is_dynamic, read_version
from release_notes import (
    extract_notes,
    latest_released_version,
    normalize_version,
    parse_sections,
    released_sections,
)

SAMPLE_CHANGELOG = """# Changelog

Some preamble.

## [Unreleased] — v4.0 foundation

### Changed
- Something not yet released.

## [3.3.0] - 2026-07-13

### Added
- Nadir mask.

## [3.2.1] - 2026-07-13

### Fixed
- Exit code.

## [1.0.0] - Initial Release

- First cut.
"""


class TestNormalizeVersion(unittest.TestCase):
    def test_strips_v_prefix(self):
        self.assertEqual(normalize_version("v4.0.0"), "4.0.0")
        self.assertEqual(normalize_version("4.0.0"), "4.0.0")

    def test_expands_two_component_legacy_tags(self):
        """The repo's older tags used vX.Y for an X.Y.0 release (v3.3 -> 3.3.0)."""
        self.assertEqual(normalize_version("v3.3"), "3.3.0")
        self.assertEqual(normalize_version("3.2"), "3.2.0")

    def test_leaves_three_component_untouched(self):
        self.assertEqual(normalize_version("v3.2.1"), "3.2.1")


class TestChangelogParsing(unittest.TestCase):
    def test_parses_every_section_including_unreleased(self):
        versions = [s["version"] for s in parse_sections(SAMPLE_CHANGELOG)]
        self.assertEqual(versions, ["Unreleased", "3.3.0", "3.2.1", "1.0.0"])

    def test_released_sections_exclude_unreleased(self):
        versions = [s["version"] for s in released_sections(SAMPLE_CHANGELOG)]
        self.assertEqual(versions, ["3.3.0", "3.2.1", "1.0.0"])

    def test_latest_released_version_ignores_unreleased(self):
        self.assertEqual(latest_released_version(SAMPLE_CHANGELOG), "3.3.0")

    def test_latest_released_version_none_when_no_release(self):
        self.assertIsNone(latest_released_version("# Changelog\n\n## [Unreleased]\n\n- wip\n"))


class TestExtractNotes(unittest.TestCase):
    def test_single_version_returns_body_without_heading(self):
        notes = extract_notes(SAMPLE_CHANGELOG, ["3.3.0"])
        self.assertIn("### Added", notes)
        self.assertIn("Nadir mask", notes)
        # The body stops at the next section.
        self.assertNotIn("Exit code", notes)
        self.assertNotIn("## [3.3.0]", notes)

    def test_multiple_versions_are_concatenated_with_headings(self):
        notes = extract_notes(SAMPLE_CHANGELOG, ["3.3.0", "3.2.1"])
        self.assertIn("## 3.3.0", notes)
        self.assertIn("## 3.2.1", notes)
        self.assertIn("Nadir mask", notes)
        self.assertIn("Exit code", notes)
        self.assertLess(notes.index("## 3.3.0"), notes.index("## 3.2.1"))

    def test_unknown_version_raises(self):
        with self.assertRaises(KeyError):
            extract_notes(SAMPLE_CHANGELOG, ["9.9.9"])

    def test_empty_section_raises(self):
        with self.assertRaises(ValueError):
            extract_notes("## [2.0.0] - 2026-01-01\n\n## [1.0.0] - x\n\n- ok\n", ["2.0.0"])


class TestPyprojectDynamicVersion(unittest.TestCase):
    def test_dynamic_version_accepted(self):
        text = '[project]\nname = "x"\ndynamic = ["version"]\n'
        self.assertTrue(pyproject_version_is_dynamic(text))

    def test_hardcoded_version_rejected(self):
        """This is the issue-#7 regression: a static version drifting from version.py."""
        text = '[project]\nname = "x"\nversion = "1.2.3"\n'
        self.assertFalse(pyproject_version_is_dynamic(text))

    def test_version_in_another_table_is_not_the_project_version(self):
        text = '[project]\nname = "x"\ndynamic = ["version"]\n\n[tool.foo]\nversion = "9.9.9"\n'
        self.assertTrue(pyproject_version_is_dynamic(text))


class TestRepositoryIsReleaseConsistent(unittest.TestCase):
    """Runs the real guard against the real repo — this is what CI enforces."""

    def test_version_py_is_readable_semver(self):
        version = read_version(check_release.VERSION_FILE)
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")

    def test_repo_passes_the_guard_without_a_tag(self):
        self.assertEqual(check(), [], "repository is not release-consistent")

    def test_matching_canonical_tag_passes(self):
        version = read_version(check_release.VERSION_FILE)
        self.assertEqual(check(tag=f"v{version}"), [])

    def test_mismatched_tag_fails(self):
        errors = check(tag="v99.0.0")
        self.assertTrue(any("does not match version.py" in e for e in errors), errors)

    def test_non_canonical_new_tag_is_rejected(self):
        """A new two-component tag (v4.0) must be refused; only legacy ones are grandfathered."""
        errors = check(tag="v99.0")
        self.assertTrue(any("canonical form vX.Y.Z" in e for e in errors), errors)

    def test_legacy_tag_format_is_grandfathered(self):
        """v3.3 is a real historical tag: its format must not be flagged."""
        errors = check(tag="v3.3")
        self.assertFalse(any("canonical form" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
