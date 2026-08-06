"""The judge's exam, reported at a resolution that cannot be over-read.

These tests exist because the aggregate is the number that lies. A judge
can score 83% overall while getting every subtle-numeric pair wrong, which
is the one category this tool was built to catch, so the breakdown has to
make that visible and the statistics have to refuse to say more than 30
hand-labeled pairs can support.

Covers RC-17 (denominators, intervals, no rate on tiny categories),
RC-18 (kappa computed rather than asserted) and RC-19 (a comparison that
declines to rank when it cannot).
"""

import unittest

from agent_report_card import calibrate


def exam(judged_for) -> dict:
    """Build a calibration record over the real pair set.

    ``judged_for(pair) -> 'pass' | 'fail' | 'error'`` stands in for a judge,
    so the categories and their sizes are the ones actually shipped rather
    than a convenient fiction.
    """
    pairs = calibrate.load_pairs()
    recorded = [{"id": p["id"], "category": p["category"], "label": p["label"],
                 "judged": judged_for(p)} for p in pairs]
    return {"n": len(recorded),
            "agreement": sum(r["judged"] == r["label"] for r in recorded),
            "pairs": recorded}


PERFECT = exam(lambda p: p["label"])
ALL_PASS = exam(lambda p: "pass")
ALL_FAIL = exam(lambda p: "fail")
# right about everything except the category the product exists for
BLIND_TO_NUMBERS = exam(
    lambda p: ("pass" if p["category"] == "subtle_numeric" else p["label"]))


class TestKappa(unittest.TestCase):
    """RC-18: kappa is computed against the labels, not asserted."""

    def test_perfect_judge_is_one(self):
        self.assertAlmostEqual(calibrate.kappa(PERFECT), 1.0, places=9)

    def test_a_constant_judge_is_zero_however_it_answers(self):
        # all-pass agrees with 15 of 30 on a balanced set. Raw agreement
        # calls that 50%; kappa calls it what it is, which is no skill.
        for constant in (ALL_PASS, ALL_FAIL):
            with self.subTest(agreement=constant["agreement"]):
                self.assertEqual(constant["agreement"], 15)
                self.assertAlmostEqual(calibrate.kappa(constant), 0.0, places=9)

    def test_a_coin_flip_does_not_read_as_half_right(self):
        # deterministic alternation, not randomness: a seeded flip that
        # happened to do well would make this test lie about the property
        flip = iter(range(10_000))
        coin = exam(lambda p: "pass" if next(flip) % 2 else "fail")
        self.assertLess(abs(calibrate.kappa(coin)), 0.35,
                        "a judge with no skill must not score near 1")

    def test_errors_are_scored_as_failures_to_judge(self):
        broken = exam(lambda p: "error")
        self.assertEqual(broken["agreement"], 0)
        # an error can never match a label, and no label is ever 'error',
        # so it costs observed agreement and adds nothing to chance
        self.assertLessEqual(calibrate.kappa(broken), 0.0)

    def test_absent_calibration_is_none_not_zero(self):
        # zero would read as a measured result; None reads as "not measured"
        self.assertIsNone(calibrate.kappa(None))
        self.assertIsNone(calibrate.kappa({"n": 0, "pairs": []}))


class TestBreakdown(unittest.TestCase):
    """RC-17: the breakdown cannot lie by omission or by precision."""

    def test_the_dangerous_judge_is_visible_not_a_93_percent(self):
        rows = {r["category"]: r for r in calibrate.by_category(BLIND_TO_NUMBERS)}
        numeric = rows["subtle_numeric"]
        self.assertEqual((numeric["correct"], numeric["n"]), (0, 5))
        self.assertEqual(numeric["rate"], 0.0)
        # and the aggregate it hides behind is genuinely reassuring
        aggregate = BLIND_TO_NUMBERS["agreement"] / BLIND_TO_NUMBERS["n"]
        self.assertGreater(aggregate, 0.80,
                           "the point of this test is that the aggregate looks fine")

    def test_no_rate_where_there_is_not_enough_evidence_for_one(self):
        for row in calibrate.by_category(PERFECT):
            with self.subTest(category=row["category"], n=row["n"]):
                if row["n"] < calibrate.MIN_RATE_N:
                    self.assertIsNone(row["rate"])
                    self.assertIsNone(row["lo"])
                    self.assertIsNone(row["hi"])
                else:
                    self.assertIsNotNone(row["rate"])

    def test_every_printed_rate_carries_its_denominator_and_interval(self):
        for row in calibrate.by_category(BLIND_TO_NUMBERS):
            with self.subTest(category=row["category"]):
                self.assertIn("n", row)
                self.assertIn("correct", row)
                if row["rate"] is not None:
                    self.assertLessEqual(row["lo"], row["rate"])
                    self.assertLessEqual(row["rate"], row["hi"])

    def test_a_perfect_small_category_still_admits_uncertainty(self):
        # 5/5 is not evidence of 100%. The lower bound has to say so, or
        # the report repeats the mistake it accuses benchmarks of making.
        row = next(r for r in calibrate.by_category(PERFECT)
                   if r["category"] == "subtle_numeric")
        self.assertEqual((row["correct"], row["n"]), (5, 5))
        self.assertLess(row["lo"], 0.75)

    def test_every_pair_lands_in_exactly_one_category(self):
        rows = calibrate.by_category(PERFECT)
        self.assertEqual(sum(r["n"] for r in rows), PERFECT["n"])

    def test_biggest_categories_lead(self):
        counts = [r["n"] for r in calibrate.by_category(PERFECT)]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_absent_calibration_breaks_down_to_nothing(self):
        self.assertEqual(calibrate.by_category(None), [])
        self.assertEqual(calibrate.by_category({"n": 0}), [])


class TestSeparability(unittest.TestCase):
    """RC-19: comparison declines to rank when 30 items cannot."""

    def test_two_close_judges_are_not_ranked(self):
        near = exam(lambda p: "pass" if p["id"] == calibrate.load_pairs()[0]["id"]
                    and p["label"] == "fail" else p["label"])
        self.assertFalse(calibrate.separable(PERFECT, near),
                         "30 items cannot separate judges one pair apart")

    def test_genuinely_far_apart_judges_are_separable(self):
        self.assertTrue(calibrate.separable(PERFECT, ALL_PASS))

    def test_a_missing_judge_is_never_separable(self):
        # absent evidence must not read as a decisive difference
        self.assertFalse(calibrate.separable(PERFECT, None))
        self.assertFalse(calibrate.separable(None, None))

    def test_separability_is_symmetric(self):
        self.assertEqual(calibrate.separable(PERFECT, ALL_PASS),
                         calibrate.separable(ALL_PASS, PERFECT))


class TestRendered(unittest.TestCase):
    """The numbers have to reach the page, not just the dict. A breakdown
    that exists only in memory protects nobody."""

    @staticmethod
    def report_for(calibration):
        from agent_report_card.checks_code import CheckResult
        from agent_report_card.client import EndpointReply
        from agent_report_card.report import render
        from agent_report_card.schema import (Case, EndpointCfg, Gates,
                                              Patterns, Suite)
        from agent_report_card.scoring import CaseRecord, score
        case = Case(id="c", question="q", line=1, must_contain=["x"])
        record = CaseRecord(case=case,
                            reply=EndpointReply(answer="x", latency_s=0.1),
                            checks=[CheckResult("contains_all", "pass", "")])
        suite = Suite(name="t", path="t.yaml", sha256="0" * 64,
                      endpoint=EndpointCfg(), judge_model="j", gates=Gates(),
                      patterns=Patterns(), corpus_manifest=[], cases=[case])
        board = score([record], suite, judged=True)
        return render(board, "http://x", "ollama:j", "cmd", calibration, 1.0, 30)

    def full(self, exam_record):
        # the renderer reads keys run_exam writes; supply the ones the
        # synthetic exams above do not carry
        return dict(exam_record, n_pass_labeled=15, n_fail_labeled=15,
                    false_pass=0, false_fail=0, subtle_total=5,
                    subtle_caught=5)

    def test_the_blind_judge_cannot_hide_behind_its_aggregate(self):
        report = self.report_for(self.full(BLIND_TO_NUMBERS))
        self.assertIn("| subtle_numeric | 0/5 |", report,
                      "the category the tool exists for must show its tally")

    def test_tiny_categories_render_a_reason_not_a_percentage(self):
        report = self.report_for(self.full(PERFECT))
        self.assertIn("too few pairs to bound", report)
        self.assertIn("| non_refusal | 1/1 | n/a |", report)

    def test_kappa_reaches_the_page(self):
        self.assertIn("Cohen's kappa", self.report_for(self.full(PERFECT)))

    def test_no_em_dashes_survive_the_new_section(self):
        report = self.report_for(self.full(BLIND_TO_NUMBERS))
        self.assertNotIn("—", report)
        self.assertNotIn("–", report)

    def test_an_uncalibrated_judge_renders_no_breakdown_rather_than_zeros(self):
        report = self.report_for(None)
        self.assertNotIn("Cohen's kappa", report)
        self.assertNotIn("| category | correct |", report)


if __name__ == "__main__":
    unittest.main()
