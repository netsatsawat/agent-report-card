"""End to end over real HTTP: boots the actual fixture bot, runs the
bundled suite with --judge none, asserts the exact planted failure vector,
the tuned rollups, and all three exit-code outcomes."""

import json
import os
import tempfile
import unittest
from importlib import resources
from pathlib import Path

from agent_report_card import demo_bot
from agent_report_card.cli import run_pipeline
from agent_report_card.schema import load_suite

EXPECTED_FAILURES = {
    "q03-penalty": {"contains_all", "contains_none", "numbers_agree",
                    "cites_expected_source"},
    "q04-5g-price": {"contains_none", "numbers_agree",
                     "cites_expected_source", "retrieval_hit"},
    "q07-coverage": {"latency_under"},
    "q09-dividend": {"cites_expected_source"},
    "q10-founded": {"no_phantom_citation"},
    "q12-maintenance": {"no_error_leak"},
    "q19-support": {"contains_all"},
    "q21-salary": {"refuses_when_required"},
}


class TestE2EDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = demo_bot.serve(port=0, background=True)
        cls.endpoint = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.tmp = tempfile.mkdtemp()
        bundled = (resources.files("agent_report_card") / "_data" /
                   "board_questions.yaml").read_text(encoding="utf-8")
        cls.tests_path = Path(cls.tmp) / "board_questions.yaml"
        cls.tests_path.write_text(bundled, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def run_demo(self, suite_text=None):
        path = self.tests_path
        if suite_text is not None:
            path = Path(self.tmp) / "variant.yaml"
            path.write_text(suite_text, encoding="utf-8")
        out = Path(self.tmp) / "report.md"
        scores = Path(self.tmp) / "scores.json"
        code = run_pipeline(load_suite(str(path)), self.endpoint, "none",
                            str(out), str(scores), 30.0, 120.0, None, None,
                            False, "test")
        return code, json.loads(scores.read_text(encoding="utf-8"))

    def test_planted_failure_vector_and_tuned_rollups(self):
        code, scores = self.run_demo()
        self.assertEqual(code, 1)  # gates fail on the planted flaws
        self.assertEqual(scores["verdict"], "NOT READY")
        self.assertEqual(scores["rollups"]["accuracy_det"], [16, 19])
        self.assertEqual(scores["banner_failures"], 3)
        self.assertEqual(scores["rollups"]["hallucination"], [0, 0])  # n/a, judge off
        got_failures = {
            c["id"]: {ch["name"] for ch in c["checks"] if ch["status"] == "fail"}
            for c in scores["cases"]
            if any(ch["status"] == "fail" for ch in c["checks"])}
        self.assertEqual(got_failures, EXPECTED_FAILURES)

    def test_relaxed_gates_exit_zero_with_warnings(self):
        bundled = self.tests_path.read_text(encoding="utf-8")
        relaxed = bundled.replace("min_accuracy: 0.90", "min_accuracy: 0.50") \
                         .replace("criticals_must_pass: true",
                                  "criticals_must_pass: false")
        code, scores = self.run_demo(relaxed)
        self.assertEqual(code, 0)
        # judge off: the judge-fed gate is unevaluable, disclosed as a warning
        self.assertEqual(scores["verdict"], "PASS WITH WARNINGS")

    def test_unreachable_endpoint_is_exit_two(self):
        out = Path(self.tmp) / "r2.md"
        scores = Path(self.tmp) / "s2.json"
        code = run_pipeline(load_suite(str(self.tests_path)),
                            "http://127.0.0.1:9", "none", str(out),
                            str(scores), 5.0, 120.0, None, None, False, "test")
        self.assertEqual(code, 2)

    def test_contract_command_shape(self):
        """The README's verbatim command, against the served bot.

        CI has no Ollama, so the judge flag is pinned to none here; without
        it the verbatim command exits 2 with a message naming --judge none,
        which is the documented behavior on a judge-less machine.
        """
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "-m", "agent_report_card.cli", "run",
             "--tests", "board_questions.yaml", "--endpoint", self.endpoint,
             "--judge", "none"],
            cwd=self.tmp, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("accuracy 84% (16/19)", result.stdout)
        self.assertIn("3 failures", result.stdout)


if __name__ == "__main__":
    unittest.main()
