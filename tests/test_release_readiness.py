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


class TestShippedFilesNameThisVersion(unittest.TestCase):
    """Every place that tells a reader which version they are getting must
    name this one.

    0.2.1 went to PyPI while the Kestra example still pinned 0.2.0, the
    version with the regex bug 0.2.1 fixed, so copying the example installed
    the bug. The README (the PyPI page) and the tutorial said 0.2.0 as well,
    and two judged reports once shipped with a stale tool_version. Each check
    below is a claim about the current version. History, such as CHANGELOG
    sections or "the groundwork shipped in 0.2.0", is deliberately not
    checked.
    """

    def version(self) -> str:
        return agent_report_card.__version__

    def read(self, rel: str) -> str:
        return (REPO / rel).read_text(encoding="utf-8")

    def test_kestra_example_installs_this_version(self):
        pins = re.findall(r"agent-report-card==(\S+)",
                          self.read("examples/kestra/quality-gate.yml"))
        self.assertTrue(pins, "the Kestra flow no longer pins a version")
        self.assertEqual(
            set(pins), {self.version()},
            "examples/kestra/quality-gate.yml pins a different version, so "
            "anyone who copies the quality gate installs that one")

    def test_kestra_guide_shows_a_run_of_this_version(self):
        guide = self.read("examples/kestra/README.md")
        verified = re.search(r"Verified against the (?:published )?(\S+) wheel",
                             guide)
        shown = re.findall(r'"tool_version": "([^"]+)"', guide)
        self.assertTrue(verified and shown,
                        "the Kestra guide no longer shows a verified run")
        self.assertEqual(
            {verified.group(1), *shown}, {self.version()},
            "examples/kestra/README.md shows a run of another version; re-run "
            "the flow's gate.py against this version's wheel and the fixture "
            "bot, then paste the real output")

    def test_readme_roadmap_names_this_version(self):
        today = re.search(r"^Today \(([^)]+)\)", self.read("README.md"), re.M)
        self.assertIsNotNone(today, "the README roadmap no longer says "
                                    "'Today (version)'")
        self.assertEqual(
            today.group(1), self.version(),
            "README.md, which is also the PyPI page, calls another version "
            "'today'")

    def test_tutorial_was_run_on_this_version(self):
        import json
        nb = json.loads(self.read("examples/tutorial.ipynb"))
        printed = "".join("".join(o.get("text", []))
                          for c in nb["cells"] if c["cell_type"] == "code"
                          for o in c.get("outputs", []))
        seen = set(re.findall(r"^agent-report-card (\S+)$", printed, re.M))
        self.assertEqual(
            seen, {self.version()},
            "examples/tutorial.ipynb printed another version; rebuild it with "
            ".venv-docs/bin/python scripts/build_tutorial.py so its outputs "
            "are real")

    def test_every_committed_report_was_made_by_this_version(self):
        import json
        stale = {p.name: json.loads(p.read_text(encoding="utf-8"))
                 .get("tool_version")
                 for p in sorted((REPO / "reports").glob("*.scores.json"))}
        self.assertTrue(stale, "no committed reports found")
        stale = {name: v for name, v in stale.items() if v != self.version()}
        self.assertEqual(
            stale, {},
            "these committed reports were made by another version; regenerate "
            "them with `make gallery` (the judged ones need the judge model)")


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
