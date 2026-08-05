"""Scoring: correctness by two routes, rollups with printed formulas,
gates, and the verdict.

The deterministic route wins the verdict; disagreements with the judge are
surfaced, never resolved. The hallucination rate is judge-fed (grounding
failures over cases where judge_grounded ran) and renders n/a when the
judge never evaluated grounding, never a substituted number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .catalog import CORRECTNESS_CODE
from .checks_code import PASS, FAIL, NA, JUDGE_ERROR
from .schema import Suite

VERDICT_PASS = "PASS"
VERDICT_WARN = "PASS WITH WARNINGS"
VERDICT_FAIL = "NOT READY"


@dataclass
class CaseRecord:
    case: object
    reply: object
    checks: list  # CheckResult, code route then judge route

    def status(self, name):
        for c in self.checks:
            if c.name == name:
                return c.status
        return NA

    def detail(self, name):
        for c in self.checks:
            if c.name == name:
                return c.detail
        return ""

    @property
    def det_correct(self):
        """True/False when any deterministic correctness check applied, else
        None. A failed `answered` check IS a deterministic wrong answer: a
        bot that returns HTTP 500 or an unmappable body must never score
        better than one that answers wrongly."""
        if self.status("answered") == FAIL:
            return False
        applied = [c for c in self.checks
                   if c.name in CORRECTNESS_CODE and c.status in (PASS, FAIL)]
        if not applied:
            return None
        return all(c.status == PASS for c in applied)

    @property
    def judge_correct(self):
        s = self.status("judge_correct")
        return {PASS: True, FAIL: False}.get(s)

    @property
    def correctness(self):
        """Resolved verdict: deterministic wins where defined."""
        if self.det_correct is not None:
            return self.det_correct
        return self.judge_correct

    @property
    def disagrees(self):
        return (self.det_correct is not None and self.judge_correct is not None
                and self.det_correct != self.judge_correct)

    @property
    def failed_checks(self):
        return [c for c in self.checks if c.status == FAIL]

    @property
    def judge_errors(self):
        return [c for c in self.checks if c.status == JUDGE_ERROR]


def wilson(successes: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score 95% interval."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile; 0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


@dataclass
class Frac:
    """A count with its denominator; renders as 'P% (a/b)' or 'n/a (reason)'."""
    num: int = 0
    den: int = 0
    na_reason: str = ""

    @property
    def applicable(self):
        return self.den > 0

    @property
    def rate(self):
        return self.num / self.den if self.den else 0.0

    def pct(self):
        if not self.applicable:
            return f"n/a ({self.na_reason})" if self.na_reason else "n/a"
        return f"{round(100 * self.rate)}% ({self.num}/{self.den})"


@dataclass
class Scoreboard:
    records: list
    suite: Suite
    judged: bool
    accuracy_det: Frac = None
    accuracy_judge: Frac = None
    hallucination: Frac = None
    citations: Frac = None
    refusals: Frac = None
    latencies: list = field(default_factory=list)
    disagreements: list = field(default_factory=list)
    judge_error_count: int = 0
    banner_failures: int = 0
    gate_results: list = field(default_factory=list)   # (name, ok|None, text)
    warnings: list = field(default_factory=list)
    verdict: str = VERDICT_PASS
    judge_unreliable: bool = False

    @property
    def wilson_det(self):
        return wilson(self.accuracy_det.num, self.accuracy_det.den) \
            if self.accuracy_det.applicable else None


def score(records: list, suite: Suite, judged: bool,
          judge_unreliable: bool = False) -> Scoreboard:
    board = Scoreboard(records=records, suite=suite, judged=judged,
                       judge_unreliable=judge_unreliable)

    answerable = [r for r in records if r.case.answerable]

    det_scored = [r for r in answerable if r.det_correct is not None]
    board.accuracy_det = Frac(sum(1 for r in det_scored if r.det_correct),
                              len(det_scored),
                              "no case defines a deterministic correctness check")
    judge_scored = [r for r in answerable if r.judge_correct is not None]
    board.accuracy_judge = Frac(sum(1 for r in judge_scored if r.judge_correct),
                                len(judge_scored),
                                "judge did not run" if not judged
                                else "no case was judge-scored")

    grounded_eval = [r for r in records
                     if r.status("judge_grounded") in (PASS, FAIL)]
    grounded_errors = sum(1 for r in records
                          if r.status("judge_grounded") == JUDGE_ERROR)
    if not judged:
        halluc_na = "grounding needs the judge; drop --judge none to evaluate it"
    elif grounded_errors and not grounded_eval:
        halluc_na = ("the only grounding call failed (judge_error); nothing "
                     "was evaluated" if grounded_errors == 1 else
                     f"all {grounded_errors} grounding calls failed "
                     f"(judge_error); nothing was evaluated")
    else:
        halluc_na = "no case returned contexts to ground against"
    board.hallucination = Frac(
        sum(1 for r in grounded_eval if r.status("judge_grounded") == FAIL),
        len(grounded_eval), halluc_na)

    cite_names = ("cites_expected_source", "no_phantom_citation",
                  "judge_citation_support")
    cite_applied = cite_passed = 0
    for r in records:
        for name in cite_names:
            s = r.status(name)
            if s in (PASS, FAIL):
                cite_applied += 1
                cite_passed += (s == PASS)
    board.citations = Frac(cite_passed, cite_applied, "no citation checks applied")

    ref_names = ("refuses_when_required", "judge_refusal")
    ref_applied = ref_passed = 0
    for r in records:
        for name in ref_names:
            s = r.status(name)
            if s in (PASS, FAIL):
                ref_applied += 1
                ref_passed += (s == PASS)
    board.refusals = Frac(ref_passed, ref_applied, "no refusal cases in the suite")

    board.latencies = [r.reply.latency_s for r in records if r.reply.latency_s]
    board.disagreements = [r for r in records if r.disagrees]
    board.judge_error_count = sum(len(r.judge_errors) for r in records)
    board.banner_failures = sum(
        1 for r in answerable if r.correctness is False)

    _apply_gates(board)
    return board


def _apply_gates(board: Scoreboard):
    gates = board.suite.gates
    hard_fail = False

    # min_accuracy: deterministic route only
    if board.accuracy_det.applicable:
        ok = board.accuracy_det.rate >= gates.min_accuracy
        board.gate_results.append((
            "min_accuracy", ok,
            f"deterministic accuracy {board.accuracy_det.pct()} against the "
            f"{100 * gates.min_accuracy:g}% floor"))
        hard_fail |= not ok
    else:
        board.gate_results.append((
            "min_accuracy", None,
            "could not evaluate: no deterministically scored case"))
        board.warnings.append(
            "the min_accuracy gate could not be evaluated (no case defines "
            "a deterministic correctness check)")

    # criticals: code-route failures only; vacuously green is not green
    criticals = [r for r in board.records if r.case.critical]
    critical_bad = [r for r in criticals if any(
        c.status == FAIL for c in r.checks
        if c.name in _CODE_NAMES)]
    if gates.criticals_must_pass:
        if not criticals:
            board.gate_results.append((
                "criticals_must_pass", None,
                "n/a: no case is tagged critical"))
        else:
            ok = not critical_bad
            n_crit = len(criticals)
            passed_text = (f"the critical-tagged case passed its code checks"
                           if n_crit == 1 else
                           f"all {n_crit} critical-tagged cases passed their "
                           f"code checks")
            board.gate_results.append((
                "criticals_must_pass", ok,
                passed_text if ok else
                f"critical cases failed code checks: "
                f"{', '.join(r.case.id for r in critical_bad)}"))
            hard_fail |= not ok

    # max_hallucination: judge-fed, disclosed, degradable
    if board.hallucination.applicable:
        ok = board.hallucination.rate <= gates.max_hallucination
        if not ok and board.judge_unreliable:
            board.gate_results.append((
                "max_hallucination", None,
                f"hallucination {board.hallucination.pct()} exceeds the "
                f"{100 * gates.max_hallucination:g}% ceiling, but the "
                f"judge failed calibration, so this downgrades to a warning"))
            board.warnings.append(
                "the judge-fed hallucination gate would have failed, but the "
                "judge is unreliable this run; review the quoted cases by hand")
        else:
            board.gate_results.append((
                "max_hallucination", ok,
                f"judge-fed hallucination {board.hallucination.pct()} against "
                f"the {100 * gates.max_hallucination:g}% ceiling"))
            hard_fail |= not ok
    else:
        board.gate_results.append((
            "max_hallucination", None,
            f"could not evaluate: {board.hallucination.na_reason}"))
        board.warnings.append(
            "the judge-fed max_hallucination gate could not be evaluated "
            f"({board.hallucination.na_reason})")

    if board.disagreements:
        board.warnings.append(
            f"the two scoring routes disagreed on {len(board.disagreements)} "
            f"case(s); they are listed under Needs human review")
    if board.judge_error_count:
        board.warnings.append(
            f"{board.judge_error_count} judge call(s) failed and were "
            f"recorded as judge_error, not as passes or fails")
    if board.judge_unreliable:
        board.warnings.append(
            "judge unreliable this run, trust the deterministic column")

    if hard_fail:
        board.verdict = VERDICT_FAIL
    elif board.warnings:
        board.verdict = VERDICT_WARN
    else:
        board.verdict = VERDICT_PASS


from .catalog import CODE_CHECKS  # noqa: E402  (import placed to avoid cycle)
_CODE_NAMES = {name for name, _r, _w in CODE_CHECKS}
