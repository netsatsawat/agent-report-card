#!/usr/bin/env python3
"""No number in the README without a runnable path behind it.

Two assertions, wired into CI:
1. The deterministic banner numbers the README quotes (accuracy 84%
   (16/19), 3 failures) must match a FRESH no-judge demo run executed by
   this script.
2. Every judged number the README quotes (the hallucination line and the
   judge calibration sentence) must match the committed artifacts it
   cites: reports/demo_report_judged.md and reports/calibration_qwen3.6_27b.json.
"""

import json
import re
import sys
import tempfile
from importlib import resources
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from agent_report_card import demo_bot                     # noqa: E402
from agent_report_card.cli import run_pipeline             # noqa: E402
from agent_report_card.schema import load_suite            # noqa: E402

problems = []


def check(name, condition, detail=""):
    print(f"  {'ok ' if condition else 'FAIL'} {name}" +
          (f" ({detail})" if detail and not condition else ""))
    if not condition:
        problems.append(name)


def main() -> int:
    readme = (REPO / "README.md").read_text(encoding="utf-8")

    print("fresh deterministic demo run:")
    server = demo_bot.serve(port=0, background=True)
    try:
        tmp = Path(tempfile.mkdtemp())
        tests = tmp / "t.yaml"
        tests.write_text(
            (resources.files("agent_report_card") / "_data" /
             "board_questions.yaml").read_text(encoding="utf-8"),
            encoding="utf-8")
        scores_path = tmp / "s.json"
        code = run_pipeline(load_suite(str(tests)),
                            f"http://127.0.0.1:{server.server_address[1]}",
                            "none", str(tmp / "r.md"), str(scores_path),
                            30.0, 120.0, None, None, False, "verify")
        scores = json.loads(scores_path.read_text(encoding="utf-8"))
    finally:
        server.shutdown()

    check("demo exits 1 (gates fail on planted flaws)", code == 1, str(code))
    check("fresh accuracy is 16/19",
          scores["rollups"]["accuracy_det"] == [16, 19],
          str(scores["rollups"]["accuracy_det"]))
    check("fresh failure count is 3", scores["banner_failures"] == 3,
          str(scores["banner_failures"]))
    check("README quotes accuracy 84% (16/19)",
          "accuracy 84% (16/19)" in readme)
    check("README quotes 3 failures", "3 failures" in readme)

    print("committed judged artifacts:")
    judged_path = REPO / "reports" / "demo_report_judged.md"
    check("judged sample report is committed", judged_path.exists())
    if judged_path.exists():
        judged = judged_path.read_text(encoding="utf-8")
        match = re.search(r"hallucination (\d+% \(\d+/\d+\))", judged)
        check("judged report carries a hallucination fraction",
              match is not None)
        if match:
            check(f"README quotes the judged hallucination number "
                  f"({match.group(1)})", match.group(1) in readme)

    calib_files = list((REPO / "reports").glob("calibration_*.json"))
    check("calibration JSON is committed", bool(calib_files))
    if calib_files:
        calib = json.loads(calib_files[0].read_text(encoding="utf-8"))
        sentence = f"{calib['agreement']}/{calib['n']}"
        check(f"README quotes the calibration score ({sentence})",
              sentence in readme)
        subtle = f"{calib['subtle_caught']}/{calib['subtle_total']}"
        check(f"README quotes the subtle-numeric recall ({subtle})",
              subtle in readme)

    if problems:
        print(f"\n{len(problems)} README claim(s) drifted: {problems}")
        return 1
    print("\nevery quoted README number matches its artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
