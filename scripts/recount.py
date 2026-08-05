#!/usr/bin/env python3
"""Independent rollup recomputation: the compute-twice route.

Reads only report.scores.json (never the tool's own aggregation code) and
recomputes every rollup from the raw per-case check records. The test
suite asserts equality with the runner's numbers; the report footer's
cross-check claim rests on this file staying independent, so keep it free
of agent_report_card imports.
"""

import json
import sys

CORRECTNESS_CODE = ("exact_match", "contains_all", "contains_none",
                    "numbers_agree", "regex_match")


def recount(scores: dict) -> dict:
    cases = scores["cases"]

    def statuses(case, names):
        return [c["status"] for c in case["checks"] if c["name"] in names]

    det_num = det_den = judge_num = judge_den = 0
    hall_num = hall_den = cite_num = cite_den = ref_num = ref_den = 0
    banner_failures = 0

    for case in cases:
        answerable = case["answerable"]
        det = [s for s in statuses(case, CORRECTNESS_CODE)
               if s in ("pass", "fail")]
        det_ok = all(s == "pass" for s in det) if det else None
        judge = statuses(case, ("judge_correct",))
        judge_ok = {True: True, False: False}.get(
            judge[0] == "pass" if judge and judge[0] in ("pass", "fail")
            else None)
        if answerable:
            if det_ok is not None:
                det_den += 1
                det_num += det_ok
            if judge_ok is not None:
                judge_den += 1
                judge_num += judge_ok
            resolved = det_ok if det_ok is not None else judge_ok
            banner_failures += resolved is False
        for s in statuses(case, ("judge_grounded",)):
            if s in ("pass", "fail"):
                hall_den += 1
                hall_num += (s == "fail")
        for s in statuses(case, ("cites_expected_source", "no_phantom_citation",
                                 "judge_citation_support")):
            if s in ("pass", "fail"):
                cite_den += 1
                cite_num += (s == "pass")
        for s in statuses(case, ("refuses_when_required", "judge_refusal")):
            if s in ("pass", "fail"):
                ref_den += 1
                ref_num += (s == "pass")

    return {
        "accuracy_det": [det_num, det_den],
        "accuracy_judge": [judge_num, judge_den],
        "hallucination": [hall_num, hall_den],
        "citations": [cite_num, cite_den],
        "refusals": [ref_num, ref_den],
        "banner_failures": banner_failures,
    }


def main(path: str) -> int:
    scores = json.loads(open(path, encoding="utf-8").read())
    fresh = recount(scores)
    stored = dict(scores["rollups"])
    stored["banner_failures"] = scores["banner_failures"]
    mismatches = {k: (stored.get(k), v) for k, v in fresh.items()
                  if stored.get(k) != v}
    if mismatches:
        print(f"MISMATCH: {mismatches}")
        return 1
    print(f"recount agrees with the runner on every rollup: {fresh}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "report.scores.json"))
