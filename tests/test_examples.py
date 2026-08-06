"""Every example is loadable, honest, and reachable from its index.

Examples rot faster than code: a schema change lands, the tests stay
green, and the file a new user copies is the one thing still broken. The
strict loader already knows what a valid suite is, so pointing it at
`examples/` costs nothing and makes that failure impossible.
"""

import os
import re
import unittest
from pathlib import Path

from agent_report_card.schema import load_suite

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = sorted((REPO / "examples").glob("*.yaml"))
INDEX = REPO / "examples" / "README.md"

# endpoint-shapes.yaml demonstrates ${VAR} header expansion, and an unset
# variable is a fail-fast error by design (that IS the documented
# behaviour). Supply a value so the example can be validated without
# weakening the example.
ENV_FOR_EXAMPLES = {"MY_APP_TOKEN": "test-token-not-a-real-secret"}


class TestExamplesLoad(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ENV_FOR_EXAMPLES}
        os.environ.update(ENV_FOR_EXAMPLES)

    def tearDown(self):
        for key, old in self._saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def test_there_are_examples_at_all(self):
        self.assertTrue(EXAMPLES, "examples/ has no suites in it")

    def test_every_example_passes_strict_validation(self):
        for path in EXAMPLES:
            with self.subTest(example=path.name):
                suite = load_suite(str(path))
                self.assertTrue(suite.cases,
                                f"{path.name} validates but grades nothing")

    def test_no_example_teaches_the_silent_judge_default(self):
        """`expected` with no `match` becomes match: judge, and under
        --judge none the case is then checked by nothing while reporting
        a pass. The README warns about it; no example may demonstrate it.
        """
        for path in EXAMPLES:
            with self.subTest(example=path.name):
                for case in load_suite(str(path)).cases:
                    if case.expected:
                        self.assertTrue(
                            case.match,
                            f"{path.name}: case '{case.id}' sets expected "
                            f"without an explicit match")

    def test_no_example_carries_a_real_looking_secret(self):
        for path in EXAMPLES:
            text = path.read_text(encoding="utf-8")
            with self.subTest(example=path.name):
                # credentials belong in ${VAR}, never inline
                self.assertNotRegex(
                    text, r"(?i)\b(sk-[a-z0-9]{16,}|Bearer\s+[A-Za-z0-9._-]{16,})",
                    "an example appears to contain a literal credential")

    def test_no_example_contains_an_absolute_local_path(self):
        for path in EXAMPLES:
            with self.subTest(example=path.name):
                self.assertNotIn("/Users/", path.read_text(encoding="utf-8"))


class TestExampleIndex(unittest.TestCase):
    """The index is how anyone finds these. A file missing from it is a
    file nobody runs."""

    def test_index_exists(self):
        self.assertTrue(INDEX.exists(), "examples/README.md is missing")

    def test_every_example_is_listed(self):
        listed = set(re.findall(r"\(([\w.-]+\.yaml)\)",
                                INDEX.read_text(encoding="utf-8")))
        for path in EXAMPLES:
            with self.subTest(example=path.name):
                self.assertIn(path.name, listed,
                              f"{path.name} is not linked from examples/README.md")

    def test_index_links_nothing_that_does_not_exist(self):
        listed = set(re.findall(r"\(([\w.-]+\.yaml)\)",
                                INDEX.read_text(encoding="utf-8")))
        actual = {p.name for p in EXAMPLES}
        self.assertEqual(listed - actual, set(),
                         "examples/README.md links a suite that is not there")


class TestExamplesActuallyRun(unittest.TestCase):
    """Loading is not running. Each example documents an outcome in its
    own header, and an example whose header lies is worse than no example
    at all, because it is the file a new user copies.

    endpoint-shapes.yaml is absent on purpose: it demonstrates a custom
    path and response mapping, so by design it does not fit the fixture
    bot. Its correctness is covered by the validation tests above.
    """

    # example -> documented exit code. 1 means a gate fired, which for
    # the safety and citation suites is the file working, not failing.
    EXPECTED = {
        "minimal": 0,
        "match-types": 0,
        "release_questions": 0,
        "safety-and-refusals": 1,
        "citations-and-sources": 1,
        "ci-gates": 1,
    }

    @classmethod
    def setUpClass(cls):
        from agent_report_card import demo_bot
        cls.server = demo_bot.serve(port=0, background=True)
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_each_example_exits_as_its_header_promises(self):
        import subprocess
        import sys
        import tempfile
        for name, expected in self.EXPECTED.items():
            with self.subTest(example=name):
                with tempfile.TemporaryDirectory() as tmp:
                    result = subprocess.run(
                        [sys.executable, "-m", "agent_report_card.cli", "run",
                         "--tests", str(REPO / "examples" / f"{name}.yaml"),
                         "--endpoint", f"http://127.0.0.1:{self.port}",
                         "--judge", "none",
                         "--out", f"{tmp}/report.md",
                         "--scores", f"{tmp}/scores.json"],
                        capture_output=True, text=True, cwd=REPO)
                    self.assertEqual(
                        result.returncode, expected,
                        f"examples/{name}.yaml exited {result.returncode}, "
                        f"its header documents {expected}.\n"
                        f"{result.stdout[-400:]}{result.stderr[-400:]}")
                    # exit 2 is the tool breaking, never a graded outcome
                    self.assertNotEqual(result.returncode, 2)

    def test_every_runnable_example_is_covered(self):
        runnable = {p.stem for p in EXAMPLES} - {"endpoint-shapes"}
        self.assertEqual(
            runnable - set(self.EXPECTED), set(),
            "an example was added without a documented exit code here")


class TestTutorialNotebook(unittest.TestCase):
    """The notebook ships with its outputs, and they have to be real.

    A tutorial whose outputs were pasted in by hand stops being true on
    the next release and nobody notices, because notebooks are read, not
    run. Parsed as plain JSON so this costs no dependency: the package
    still needs only pyyaml and httpx.

    Rebuild with: .venv-docs/bin/python scripts/build_tutorial.py
    """

    NOTEBOOK = REPO / "examples" / "tutorial.ipynb"

    @classmethod
    def setUpClass(cls):
        import json
        cls.nb = json.loads(cls.NOTEBOOK.read_text(encoding="utf-8"))
        cls.code_cells = [c for c in cls.nb["cells"]
                          if c["cell_type"] == "code"]

    def test_notebook_exists_and_has_code(self):
        self.assertTrue(self.NOTEBOOK.exists())
        self.assertGreaterEqual(len(self.code_cells), 10)

    def test_it_was_executed_not_just_written(self):
        unrun = [i for i, c in enumerate(self.code_cells)
                 if not c.get("outputs") and c.get("source")]
        self.assertEqual(unrun, [],
                         "code cells with no output: the notebook was "
                         "committed without being executed")

    def test_no_cell_raised(self):
        for i, cell in enumerate(self.code_cells):
            for output in cell.get("outputs", []):
                with self.subTest(cell=i):
                    self.assertNotEqual(
                        output.get("output_type"), "error",
                        f"cell {i} raised {output.get('ename')}: "
                        f"{output.get('evalue')}")

    def test_it_carries_no_absolute_local_path_in_prose(self):
        # outputs legitimately contain temp paths; the authored source
        # must not carry a developer's home directory
        for cell in self.nb["cells"]:
            source = "".join(cell.get("source", []))
            with self.subTest(kind=cell["cell_type"]):
                self.assertNotIn("/Users/", source)

    def test_the_headline_claims_are_backed_by_real_output(self):
        """The notebook's whole argument rests on two runs. If either
        stops producing what the prose says, the tutorial is wrong."""
        streams = "".join(
            "".join(o.get("text", "")) for c in self.code_cells
            for o in c.get("outputs", []) if o.get("output_type") == "stream")
        # perfect accuracy and still not shippable
        self.assertIn("accuracy 100% (3/3)", streams)
        self.assertIn("NOT READY", streams)
        # a tool error is exit 2, never the exit 1 that means "bot regressed"
        self.assertIn("typo in --tests exit code: 2", streams)

    def test_the_builder_script_is_committed_beside_it(self):
        # a generated notebook with no generator is a hand-edited notebook
        self.assertTrue((REPO / "scripts" / "build_tutorial.py").exists())


if __name__ == "__main__":
    unittest.main()
