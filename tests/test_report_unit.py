"""Renderer units the golden file cannot pin: quote truncation, docs
drift, console scrubbing, sidecar scrubbing under JSON escaping."""

import contextlib
import io
import unittest
from pathlib import Path

from agent_report_card import catalog, scrub
from agent_report_card.checks_code import CheckResult
from agent_report_card.client import EndpointReply
from agent_report_card.report import _quote, render, scores_sidecar
from agent_report_card.schema import Case, EndpointCfg, Gates, Patterns, Suite
from agent_report_card.scoring import CaseRecord, score

REPO = Path(__file__).resolve().parent.parent


class TestQuoteTruncation(unittest.TestCase):
    def test_600_char_truncation_with_note(self):
        quoted = _quote("x" * 1000)
        self.assertIn("truncated at 600 chars", quoted)
        self.assertLess(len(quoted), 700)
        self.assertEqual(_quote("short"), "> short")


class TestChecksMdDrift(unittest.TestCase):
    def test_committed_checks_md_matches_catalog(self):
        committed = (REPO / "CHECKS.md").read_text(encoding="utf-8")
        self.assertEqual(committed.strip(), catalog.catalog_markdown().strip(),
                         "CHECKS.md drifted from catalog.py; regenerate "
                         "with `make checks-md`")


class TestConsoleScrub(unittest.TestCase):
    def test_sprint_scrubs_registered_secrets(self):
        scrub.reset()
        scrub.register("sk-console-secret-123", "TOK")
        try:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                scrub.sprint("error while calling with sk-console-secret-123")
            printed = buffer.getvalue()
            self.assertNotIn("sk-console-secret-123", printed)
            self.assertIn("${TOK}", printed)
        finally:
            scrub.reset()


class TestSidecarEscapedSecret(unittest.TestCase):
    def test_secret_with_json_escapable_chars_still_scrubbed(self):
        scrub.reset()
        secret = 'pa"ss\\word-with-escapes'
        scrub.register(secret, "WEIRD")
        try:
            case = Case(id="c", question="q", line=1, must_contain=["x"])
            reply = EndpointReply(answer=f"echo {secret} done", latency_s=0.1)
            suite = Suite(name="t", path="t.yaml", sha256="0" * 64,
                          endpoint=EndpointCfg(), judge_model=None,
                          gates=Gates(), patterns=Patterns(),
                          corpus_manifest=[], cases=[case])
            record = CaseRecord(case=case, reply=reply,
                                checks=[CheckResult("contains_all", "fail",
                                                    f"missing near {secret}")])
            board = score([record], suite, judged=False)
            sidecar = scores_sidecar(board, "http://x", "none", "cmd", 1.0)
            self.assertNotIn("ss\\\\word", sidecar)  # escaped fragment
            self.assertIn("${WEIRD}", sidecar)
            report = render(board, "http://x", "none", "cmd", None, 1.0, 0)
            self.assertNotIn(secret, report)
        finally:
            scrub.reset()


if __name__ == "__main__":
    unittest.main()
