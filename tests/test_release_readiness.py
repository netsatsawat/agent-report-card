"""RC-11: the version the package declares must be the version everything
else declares, checked before a tag is ever pushed.

v0.1.0 shipped as a tag with no PyPI artifact because the publish
pipeline did not exist yet, and the rule that came out of it is that the
tagged tree is the tree that gets built. This is that rule as a test.
"""

import re
import unittest
from pathlib import Path

import agent_report_card

REPO = Path(__file__).resolve().parent.parent


def pyproject_version() -> str:
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert match, "no version in pyproject.toml"
    return match.group(1)


class TestVersionConsistency(unittest.TestCase):
    def test_pyproject_and_package_agree(self):
        self.assertEqual(pyproject_version(), agent_report_card.__version__,
                         "pyproject.toml and __init__.py declare different "
                         "versions; the artifact on PyPI would not match the "
                         "code at the tag")

    def test_changelog_documents_this_version(self):
        changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
        version = pyproject_version()
        self.assertRegex(
            changelog, rf"(?m)^## {re.escape(version)}\b",
            f"CHANGELOG.md has no '## {version}' section; either write it or "
            f"the release goes out undocumented")

    def test_no_unreleased_section_carries_content_at_release_time(self):
        """An Unreleased section with entries means the version was not
        bumped, so those changes would ship under the previous number."""
        changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
        match = re.search(r"^## Unreleased\n(.*?)(?=^## )", changelog,
                          re.M | re.S)
        if not match:
            return
        body = match.group(1).strip()
        self.assertIn(
            body.lower()[:20], ("nothing yet.", ""),
            "CHANGELOG.md's Unreleased section has entries; bump the version "
            "and retitle it before tagging")


class TestPackagingMetadata(unittest.TestCase):
    def test_license_is_machine_detectable(self):
        text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("License :: OSI Approved :: MIT License", text,
                      "PyPI cannot tell this package is MIT without either "
                      "the classifier or a PEP 639 expression")

    def test_readme_links_resolve_on_pypi(self):
        """PyPI renders the README with no repository around it, so a
        relative link is a 404 for anyone reading the project page."""
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        relative = re.findall(r'(?:\]\(|src=")(?!https?://|#)([^)"\s]+)',
                              readme)
        self.assertEqual(
            [], sorted(set(relative)),
            "these README links are relative, so they break on PyPI; make "
            "them absolute GitHub URLs")


if __name__ == "__main__":
    unittest.main()
