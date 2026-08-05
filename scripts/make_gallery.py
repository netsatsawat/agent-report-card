#!/usr/bin/env python3
"""Regenerate the verdict gallery: every committed report AND the terminal
output that produced it, one .log beside each .md.

- reports/demo_report.md / .log                 NOT READY, no judge (exit 1)
- reports/demo_report_judged.md / .log          NOT READY, judged   (exit 1)
- reports/sample_pass_with_warnings.md / .log   PASS WITH WARNINGS  (exit 0)
- reports/sample_pass.md / .log                 PASS, judged        (exit 0)

The two judged runs need Ollama with the default judge model. Run from
the repo root: .venv/bin/python scripts/make_gallery.py
"""

import contextlib
import io
import sys
from importlib import resources
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from agent_report_card import demo_bot                     # noqa: E402
from agent_report_card.cli import run_pipeline             # noqa: E402
from agent_report_card.schema import load_suite            # noqa: E402

RELEASE_SUITE = REPO / "examples" / "release_questions.yaml"
DEMO_SUITE_TEXT = (resources.files("agent_report_card") / "_data" /
                   "board_questions.yaml").read_text(encoding="utf-8")

# One fixed port so the committed report header, the sidecar's endpoint
# field, and the Reproduce command all tell the same story, and
# regeneration is deterministic. Chosen away from the common 8000.
PORT = 8123


def generate(suite_path, judge_spec, out_name, command, expect_exit,
             html=False):
    try:
        server = demo_bot.serve(port=PORT, background=True)
    except OSError:
        raise SystemExit(f"port {PORT} is in use; free it and re-run "
                         f"(the gallery uses a fixed port so committed "
                         f"artifacts are internally consistent)")
    buffer = io.StringIO()
    try:
        endpoint = f"http://localhost:{PORT}"
        out = REPO / "reports" / out_name
        scores = REPO / "reports" / (out.stem + ".scores.json")
        html_path = str(out.with_suffix(".html")) if html else None
        with contextlib.redirect_stdout(buffer):
            code = run_pipeline(load_suite(str(suite_path)), endpoint,
                                judge_spec, str(out), str(scores),
                                30.0, 120.0, None, None, True, command,
                                html_path=html_path)
    finally:
        server.shutdown()
    # normalize the machine-specific repo prefix out of the committed log:
    # a reader should see the paths a user would see from their own cwd
    output = buffer.getvalue().replace(str(REPO) + "/", "")
    log = REPO / "reports" / (out.stem + ".log")
    log.write_text(f"$ {command} -v\n{output}exit {code}\n",
                   encoding="utf-8")
    sys.stdout.write(output)
    if code != expect_exit:
        raise SystemExit(f"{out_name}: expected exit {expect_exit}, got "
                         f"{code}; inspect before committing")
    print(f"wrote {out} and {log.name} (exit {code})")


if __name__ == "__main__":
    import tempfile
    demo_suite = Path(tempfile.mkdtemp()) / "board_questions.yaml"
    demo_suite.write_text(DEMO_SUITE_TEXT, encoding="utf-8")

    generate(demo_suite, "none", "demo_report.md",
             f"agent-report-card demo --port {PORT} --judge none "
             f"--html report.html", 1, html=True)
    generate(RELEASE_SUITE, "none", "sample_pass_with_warnings.md",
             f"agent-report-card run --tests examples/release_questions.yaml "
             f"--endpoint http://localhost:{PORT} --judge none", 0)
    generate(demo_suite, "ollama:qwen3.6:27b", "demo_report_judged.md",
             f"agent-report-card demo --port {PORT}", 1)
    generate(RELEASE_SUITE, "ollama:qwen3.6:27b", "sample_pass.md",
             f"agent-report-card run --tests examples/release_questions.yaml "
             f"--endpoint http://localhost:{PORT}", 0)
