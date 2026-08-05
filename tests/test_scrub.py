"""Secret scrubbing across every output surface the tool renders."""

import unittest

from agent_report_card import scrub
from agent_report_card.checks_code import CheckResult
from agent_report_card.client import EndpointReply
from agent_report_card.report import render, scores_sidecar
from agent_report_card.schema import Case, EndpointCfg, Gates, Patterns, Suite
from agent_report_card.scoring import CaseRecord, score

SECRET = "sk-abc123-the-actual-token"


class TestScrub(unittest.TestCase):
    def setUp(self):
        scrub.reset()
        scrub.register(SECRET, "ARC_TOKEN")

    def tearDown(self):
        scrub.reset()

    def _board(self):
        # an endpoint that echoes the bearer token into its answer
        case = Case(id="echo", question="q", line=1,
                    must_contain=["result"])
        reply = EndpointReply(
            answer=f"result computed (auth: Bearer {SECRET})", latency_s=0.1)
        suite = Suite(name="t", path="t.yaml", sha256="0" * 64,
                      endpoint=EndpointCfg(), judge_model=None, gates=Gates(),
                      patterns=Patterns(), corpus_manifest=[], cases=[case])
        record = CaseRecord(case=case, reply=reply, checks=[
            CheckResult("contains_all", "pass"),
            CheckResult("no_error_leak", "fail",
                        f"leak marker present: {SECRET!r}")])
        return score([record], suite, judged=False)

    def test_report_is_scrubbed_even_when_answers_echo_the_secret(self):
        text = render(self._board(), "http://x", "none", "cmd", None, 1.0, 0)
        self.assertNotIn(SECRET, text)
        self.assertIn("${ARC_TOKEN}", text)

    def test_sidecar_is_scrubbed(self):
        text = scores_sidecar(self._board(), "http://x", "none", "cmd", 1.0)
        self.assertNotIn(SECRET, text)

    def test_longest_secret_wins_when_nested(self):
        scrub.register("abc123", "SHORT")
        cleaned = scrub.scrub(f"x {SECRET} y")
        self.assertNotIn("the-actual-token", cleaned)
        self.assertIn("${ARC_TOKEN}", cleaned)


if __name__ == "__main__":
    unittest.main()
