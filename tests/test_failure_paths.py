"""Exit 1 means a gate failed. Nothing else may ever claim it.

Every tool failure must produce an actionable message and exit 2, because
exit 1 is what CI reads as "the bot regressed". A traceback reaching a
user is a bug twice over: it is unreadable, and it bypasses the secret
scrubbing every other output path goes through.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SUITE = "suite: t\ncases:\n  - id: a\n    question: q\n"


def run_cli(*args, cwd=None):
    result = subprocess.run(
        [sys.executable, "-m", "agent_report_card.cli", *args],
        capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout + result.stderr


class TestSuiteFileFailures(unittest.TestCase):
    """The most common misuse of this tool is a typo in --tests."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "ok.yaml").write_text(SUITE, encoding="utf-8")

    def assert_clean_tool_error(self, code, output, expect):
        self.assertEqual(code, 2, f"expected exit 2, got {code}: {output}")
        self.assertNotIn("Traceback", output)
        self.assertIn("error:", output)
        self.assertIn(expect, output)

    def test_missing_file(self):
        code, out = run_cli("run", "--tests", str(self.tmp / "nope.yaml"),
                            "--endpoint", "http://127.0.0.1:9", "--judge", "none")
        self.assert_clean_tool_error(code, out, "cannot read")

    def test_directory(self):
        (self.tmp / "adir").mkdir()
        code, out = run_cli("run", "--tests", str(self.tmp / "adir"),
                            "--endpoint", "http://127.0.0.1:9", "--judge", "none")
        self.assert_clean_tool_error(code, out, "cannot read")

    def test_not_utf8(self):
        (self.tmp / "bin.yaml").write_bytes(bytes(range(200, 255)) * 4)
        code, out = run_cli("run", "--tests", str(self.tmp / "bin.yaml"),
                            "--endpoint", "http://127.0.0.1:9", "--judge", "none")
        self.assert_clean_tool_error(code, out, "not UTF-8")

    @unittest.skipIf(os.geteuid() == 0, "root can read anything")
    def test_unreadable(self):
        path = self.tmp / "noread.yaml"
        path.write_text(SUITE, encoding="utf-8")
        path.chmod(0o000)
        try:
            code, out = run_cli("run", "--tests", str(path),
                                "--endpoint", "http://127.0.0.1:9",
                                "--judge", "none")
            self.assert_clean_tool_error(code, out, "cannot read")
        finally:
            path.chmod(0o644)

    def test_wrong_type_names_the_field_and_the_line(self):
        bad = ("suite: t\ngates:\n  min_accuracy: high\n"
               "cases:\n  - id: a\n    question: q\n")
        (self.tmp / "typed.yaml").write_text(bad, encoding="utf-8")
        code, out = run_cli("run", "--tests", str(self.tmp / "typed.yaml"),
                            "--endpoint", "http://127.0.0.1:9", "--judge", "none")
        self.assert_clean_tool_error(code, out, "must be a number")
        self.assertIn("line 3", out)

    def test_duplicate_key_is_refused_rather_than_silently_dropped(self):
        dupe = ("suite: t\ncases:\n  - id: a\n    question: q\n"
                "cases:\n  - id: b\n    question: q2\n")
        (self.tmp / "dupe.yaml").write_text(dupe, encoding="utf-8")
        code, out = run_cli("run", "--tests", str(self.tmp / "dupe.yaml"),
                            "--endpoint", "http://127.0.0.1:9", "--judge", "none")
        self.assert_clean_tool_error(code, out, "duplicate key")


class TestOutputFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.suite = self.tmp / "ok.yaml"
        self.suite.write_text(SUITE, encoding="utf-8")

    def test_unwritable_out_is_a_tool_error_not_a_gate_failure(self):
        code, out = run_cli("run", "--tests", str(self.suite),
                            "--endpoint", "http://127.0.0.1:9", "--judge", "none",
                            "--out", str(self.tmp / "nope" / "deep" / "r.md"))
        self.assertEqual(code, 2, out)
        self.assertNotIn("Traceback", out)

    def test_out_may_not_overwrite_the_suite(self):
        code, out = run_cli("run", "--tests", str(self.suite),
                            "--endpoint", "http://127.0.0.1:9", "--judge", "none",
                            "--out", str(self.suite))
        self.assertEqual(code, 2, out)
        self.assertIn("same file", out)
        self.assertEqual(self.suite.read_text(encoding="utf-8"), SUITE)


class TestEndpointFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.suite = self.tmp / "ok.yaml"
        self.suite.write_text(SUITE, encoding="utf-8")

    def test_dead_endpoint_is_exit_two_not_a_verdict(self):
        code, out = run_cli("run", "--tests", str(self.suite),
                            "--endpoint", "http://127.0.0.1:9",
                            "--judge", "none",
                            "--out", str(self.tmp / "r.md"),
                            "--scores", str(self.tmp / "s.json"))
        self.assertEqual(code, 2, out)
        self.assertNotIn("Traceback", out)

    def test_malformed_endpoint_does_not_traceback(self):
        code, out = run_cli("run", "--tests", str(self.suite),
                            "--endpoint", "http://[::1",
                            "--judge", "none",
                            "--out", str(self.tmp / "r.md"),
                            "--scores", str(self.tmp / "s.json"))
        self.assertNotIn("Traceback", out)
        self.assertEqual(code, 2, out)


if __name__ == "__main__":
    unittest.main()
