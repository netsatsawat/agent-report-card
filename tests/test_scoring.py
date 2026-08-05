"""Scoring: Wilson interval against published reference values, rollup
formulas, gate logic including every PASS WITH WARNINGS trigger."""

import unittest

from agent_report_card.checks_code import CheckResult
from agent_report_card.client import EndpointReply
from agent_report_card.schema import (Case, EndpointCfg, Gates, Patterns,
                                      Suite)
from agent_report_card.scoring import (CaseRecord, VERDICT_FAIL, VERDICT_PASS,
                                       VERDICT_WARN, percentile, score, wilson)


def make_suite(gates=None):
    return Suite(name="t", path="t.yaml", sha256="0" * 64,
                 endpoint=EndpointCfg(), judge_model=None,
                 gates=gates or Gates(), patterns=Patterns(),
                 corpus_manifest=[], cases=[])


def record(case_id="c", answerable=True, tags=(), checks=()):
    case = Case(id=case_id, question="q", line=1, answerable=answerable,
                tags=list(tags))
    return CaseRecord(case=case, reply=EndpointReply(answer="x", latency_s=0.1),
                      checks=list(checks))


def ok(name):
    return CheckResult(name, "pass")


def bad(name):
    return CheckResult(name, "fail")


class TestWilson(unittest.TestCase):
    def test_published_reference_values(self):
        # Newcombe (1998), "Two-sided confidence intervals for the single
        # proportion", example: r=81, n=263 -> Wilson 95% (0.2553, 0.3662).
        low, high = wilson(81, 263)
        self.assertAlmostEqual(low, 0.2553, places=4)
        self.assertAlmostEqual(high, 0.3662, places=4)
        # Boundary cases from the same paper's discussion: 0/10 and 10/10.
        low0, high0 = wilson(0, 10)
        self.assertAlmostEqual(low0, 0.0, places=6)
        self.assertAlmostEqual(high0, 0.2775, places=4)
        low1, high1 = wilson(10, 10)
        self.assertAlmostEqual(low1, 0.7225, places=4)
        self.assertAlmostEqual(high1, 1.0, places=6)

    def test_empty(self):
        self.assertEqual(wilson(0, 0), (0.0, 1.0))


class TestPercentile(unittest.TestCase):
    def test_nearest_rank(self):
        values = [0.1, 0.2, 0.3, 0.4, 1.0]
        self.assertEqual(percentile(values, 50), 0.3)
        self.assertEqual(percentile(values, 95), 1.0)
        self.assertEqual(percentile([], 50), 0.0)


class TestScoring(unittest.TestCase):
    def test_two_routes_and_disagreement_surfaced(self):
        agree = record("a", checks=[ok("contains_all"), ok("judge_correct")])
        disagree = record("b", checks=[ok("contains_all"), bad("judge_correct")])
        board = score([agree, disagree], make_suite(), judged=True)
        self.assertEqual((board.accuracy_det.num, board.accuracy_det.den), (2, 2))
        self.assertEqual((board.accuracy_judge.num, board.accuracy_judge.den), (1, 2))
        self.assertEqual(len(board.disagreements), 1)
        self.assertEqual(board.disagreements[0].case.id, "b")
        # deterministic wins the resolved verdict
        self.assertTrue(disagree.correctness)
        self.assertEqual(board.verdict, VERDICT_WARN)

    def test_hallucination_na_without_judge_never_a_number(self):
        board = score([record(checks=[ok("contains_all")])], make_suite(),
                      judged=False)
        self.assertFalse(board.hallucination.applicable)
        self.assertIn("n/a", board.hallucination.pct())

    def test_hallucination_rate_judge_fed(self):
        recs = [record("a", checks=[ok("judge_grounded")]),
                record("b", checks=[bad("judge_grounded")])]
        board = score(recs, make_suite(), judged=True)
        self.assertEqual((board.hallucination.num, board.hallucination.den), (1, 2))

    def test_banner_failures_counts_correctness_only(self):
        recs = [record("a", checks=[bad("numbers_agree")]),
                record("b", checks=[ok("contains_all"), bad("latency_under")]),
                record("c", answerable=False,
                       checks=[bad("refuses_when_required")])]
        board = score(recs, make_suite(), judged=False)
        self.assertEqual(board.banner_failures, 1)

    def test_gate_min_accuracy_uses_deterministic_route(self):
        gates = Gates(min_accuracy=0.9, explicit=True)
        recs = [record("a", checks=[ok("contains_all"), bad("judge_correct")]),
                record("b", checks=[ok("contains_all"), ok("judge_correct")])]
        board = score(recs, make_suite(gates), judged=True)
        gate = dict((n, ok_) for n, ok_, _t in board.gate_results)
        self.assertTrue(gate["min_accuracy"])  # det route is 2/2 despite judge 1/2

    def test_criticals_gate_counts_code_failures_only(self):
        judge_only_fail = record("a", tags=["critical"],
                                 checks=[ok("contains_all"), bad("judge_correct")])
        board = score([judge_only_fail], make_suite(), judged=True)
        gate = dict((n, ok_) for n, ok_, _t in board.gate_results)
        self.assertTrue(gate["criticals_must_pass"])
        code_fail = record("b", tags=["critical"], checks=[bad("no_error_leak"),
                                                           ok("contains_all")])
        board2 = score([code_fail], make_suite(), judged=True)
        gate2 = dict((n, ok_) for n, ok_, _t in board2.gate_results)
        self.assertFalse(gate2["criticals_must_pass"])
        self.assertEqual(board2.verdict, VERDICT_FAIL)

    def test_warning_triggers(self):
        # judge_error present -> warning
        rec = record("a", checks=[ok("contains_all"),
                                  CheckResult("judge_correct", "judge_error"),
                                  ok("judge_grounded")])
        board = score([rec], make_suite(), judged=True)
        self.assertEqual(board.verdict, VERDICT_WARN)
        self.assertTrue(any("judge_error" in w for w in board.warnings))

    def test_unreliable_judge_downgrades_hallucination_gate(self):
        recs = [record(f"g{i}", checks=[ok("contains_all"),
                                        bad("judge_grounded")])
                for i in range(3)]
        board = score(recs, make_suite(), judged=True, judge_unreliable=True)
        gate = dict((n, ok_) for n, ok_, _t in board.gate_results)
        self.assertIsNone(gate["max_hallucination"])  # downgraded, not failed
        self.assertEqual(board.verdict, VERDICT_WARN)
        self.assertTrue(any("unreliable" in w for w in board.warnings))

    def test_dead_endpoint_is_scored_never_a_silent_pass(self):
        # every answerable case failed `answered`: that is 0% accuracy and
        # a failed min_accuracy gate, not a warning
        recs = [record(f"d{i}", checks=[bad("answered")]) for i in range(5)]
        board = score(recs, make_suite(), judged=False)
        self.assertEqual((board.accuracy_det.num, board.accuracy_det.den),
                         (0, 5))
        self.assertEqual(board.banner_failures, 5)
        gate = dict((n, ok_) for n, ok_, _t in board.gate_results)
        self.assertFalse(gate["min_accuracy"])
        self.assertEqual(board.verdict, VERDICT_FAIL)

    def test_criticals_gate_na_when_no_critical_cases(self):
        board = score([record("a", checks=[ok("contains_all")])],
                      make_suite(), judged=False)
        gate = dict((n, ok_) for n, ok_, _t in board.gate_results)
        self.assertIsNone(gate["criticals_must_pass"])
        text = dict((n, t) for n, _ok, t in board.gate_results)
        self.assertIn("no case is tagged critical",
                      text["criticals_must_pass"])

    def test_clean_judged_run_is_pass(self):
        recs = [record("a", checks=[ok("contains_all"), ok("judge_correct"),
                                    ok("judge_grounded")])]
        board = score(recs, make_suite(), judged=True)
        self.assertEqual(board.verdict, VERDICT_PASS)


if __name__ == "__main__":
    unittest.main()
