"""The compute-twice route: scripts/recount.py must reproduce the runner's
rollups from the raw per-case records alone."""

import importlib.util
import json
import tempfile
import unittest
from importlib import resources
from pathlib import Path

from agent_report_card import demo_bot
from agent_report_card.cli import run_pipeline
from agent_report_card.schema import load_suite

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "recount", REPO / "scripts" / "recount.py")
recount_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recount_mod)


class TestRecount(unittest.TestCase):
    def test_runner_and_recount_agree(self):
        server = demo_bot.serve(port=0, background=True)
        try:
            tmp = Path(tempfile.mkdtemp())
            tests = tmp / "t.yaml"
            tests.write_text(
                (resources.files("agent_report_card") / "_data" /
                 "board_questions.yaml").read_text(encoding="utf-8"),
                encoding="utf-8")
            scores_path = tmp / "scores.json"
            run_pipeline(load_suite(str(tests)),
                         f"http://127.0.0.1:{server.server_address[1]}",
                         "none", str(tmp / "r.md"), str(scores_path),
                         30.0, 120.0, None, None, False, "test")
            scores = json.loads(scores_path.read_text(encoding="utf-8"))
            fresh = recount_mod.recount(scores)
            stored = dict(scores["rollups"])
            stored["banner_failures"] = scores["banner_failures"]
            self.assertEqual(fresh, stored)
            self.assertEqual(recount_mod.main(str(scores_path)), 0)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
