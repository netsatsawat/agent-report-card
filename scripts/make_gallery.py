#!/usr/bin/env python3
"""Regenerate the verdict gallery: one committed report per verdict level.

- reports/sample_pass.md               judged run, all gates green (needs Ollama)
- reports/sample_pass_with_warnings.md same suite, --judge none: the judge-fed
                                       gate cannot be evaluated, which is a
                                       warning, never a silent pass
- NOT READY lives in reports/demo_report.md and reports/demo_report_judged.md,
  produced by the flawed demo suite.

Run from the repo root: .venv/bin/python scripts/make_gallery.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from agent_report_card import demo_bot                     # noqa: E402
from agent_report_card.cli import run_pipeline             # noqa: E402
from agent_report_card.schema import load_suite            # noqa: E402

SUITE = REPO / "examples" / "release_questions.yaml"


def generate(judge_spec: str, out_name: str, expect_exit: int) -> None:
    server = demo_bot.serve(port=0, background=True)
    try:
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        out = REPO / "reports" / out_name
        scores = REPO / "reports" / (out.stem + ".scores.json")
        judge_arg = "" if judge_spec != "none" else " --judge none"
        command = (f"agent-report-card run --tests "
                   f"examples/release_questions.yaml --endpoint "
                   f"http://localhost:8000{judge_arg}")
        code = run_pipeline(load_suite(str(SUITE)), endpoint, judge_spec,
                            str(out), str(scores), 30.0, 120.0, None, None,
                            True, command, demo_fallback=False)
        if code != expect_exit:
            raise SystemExit(
                f"{out_name}: expected exit {expect_exit}, got {code}; "
                f"inspect the report before committing")
        print(f"wrote {out} (exit {code})")
    finally:
        server.shutdown()


if __name__ == "__main__":
    generate("none", "sample_pass_with_warnings.md", 0)
    generate("ollama:qwen3.6:27b", "sample_pass.md", 0)
