"""Golden-file test: a fresh no-judge demo run must reproduce the
committed reports/demo_report.md byte for byte, modulo the enumerated
mask (timestamp, wall clock, latency values). Also asserts the renderer's
style rules: fractions beside percentages, no em dashes."""

import re
import tempfile
import unittest
from importlib import resources
from pathlib import Path

from agent_report_card import demo_bot
from agent_report_card.cli import run_pipeline
from agent_report_card.schema import load_suite

from maskutil import mask

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "reports" / "demo_report.md"


class TestGoldenReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = demo_bot.serve(port=0, background=True)
        endpoint = f"http://127.0.0.1:{cls.server.server_address[1]}"
        tmp = Path(tempfile.mkdtemp())
        tests = tmp / "board_questions.yaml"
        tests.write_text(
            (resources.files("agent_report_card") / "_data" /
             "board_questions.yaml").read_text(encoding="utf-8"),
            encoding="utf-8")
        cls.out = tmp / "report.md"
        run_pipeline(load_suite(str(tests)), endpoint, "none", str(cls.out),
                     str(tmp / "scores.json"), 30.0, 120.0, None, None,
                     False, "agent-report-card demo --judge none")
        cls.fresh = cls.out.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_matches_committed_golden(self):
        committed = GOLDEN.read_text(encoding="utf-8")
        # the endpoint port is ephemeral in tests; mask it on both sides
        port = re.compile(r"127\.0\.0\.1:\d+")
        self.assertEqual(
            port.sub("127.0.0.1:<PORT>", mask(self.fresh)),
            port.sub("127.0.0.1:<PORT>", mask(committed)),
            "fresh demo report drifted from reports/demo_report.md; "
            "regenerate with `make demo-report` if the change is intended")

    def test_every_percentage_carries_its_fraction(self):
        for match in re.finditer(r"(\d+)% \((\d+)/(\d+)\)", self.fresh):
            pct, num, den = (int(g) for g in match.groups())
            self.assertEqual(pct, round(100 * num / den), match.group(0))
        # the scoreboard's headline numbers all carry fractions
        self.assertIn("84% (16/19)", self.fresh)

    def test_no_em_dashes_anywhere(self):
        self.assertNotIn("—", self.fresh)
        self.assertNotIn("–", self.fresh)

    def test_na_rows_never_vanish(self):
        self.assertIn("n/a (judge did not run)", self.fresh)
        self.assertIn("n/a (match is not 'exact')", self.fresh)


if __name__ == "__main__":
    unittest.main()
