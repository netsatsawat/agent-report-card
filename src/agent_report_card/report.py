"""The report renderer. The report is the product.

Style rules enforced here and pinned by the golden test: every percentage
carries its fraction, n/a rows render with their reason and never vanish,
quotes are verbatim (truncated at 600 characters with a note), and no em
dashes appear anywhere in generated output.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import __version__, prompts, scrub
from .catalog import CHECKS, ROUTE as ROUTE_BY_NAME, SEVERITY, WHAT
from .checks_code import PASS, FAIL, NA, JUDGE_ERROR
from .scoring import Scoreboard, VERDICT_FAIL, percentile

QUOTE_LIMIT = 600


def _check_table(add, board):
    add("| check | route | what it catches | result |")
    add("|---|---|---|---|")
    for name, route, what in CHECKS:
        applied = [r.status(name) for r in board.records]
        n_pass = sum(1 for s in applied if s == PASS)
        n_fail = sum(1 for s in applied if s == FAIL)
        n_err = sum(1 for s in applied if s == JUDGE_ERROR)
        n_app = n_pass + n_fail
        if n_app == 0 and n_err == 0:
            if route == "judge" and not board.judged:
                reason = "judge did not run"
            else:
                reasons = {r.detail(name) for r in board.records
                           if r.status(name) == NA and r.detail(name)}
                reason = sorted(reasons)[0] if reasons else "not applicable"
            result = f"n/a ({reason})"
        else:
            result = f"{n_pass}/{n_app} passed"
            if n_err:
                result += f", {n_err} judge_error"
        add(f"| `{name}` | {route} | {what} | {result} |")
    add("")


def _quote(text: str) -> str:
    text = text.strip() or "(empty answer)"
    if len(text) > QUOTE_LIMIT:
        text = text[:QUOTE_LIMIT] + f" [... truncated at {QUOTE_LIMIT} chars]"
    return "\n".join("> " + line for line in text.splitlines())


def _fmt_latency(seconds: float) -> str:
    return f"{seconds:.2f}s"


def _n(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def banner_line(board: Scoreboard) -> str:
    acc = board.accuracy_det if board.accuracy_det.applicable else board.accuracy_judge
    parts = [f"accuracy {acc.pct()}",
             f"hallucination {board.hallucination.pct()}",
             f"{board.banner_failures} failures",
             board.verdict]
    return " · ".join(parts)


def smallest_fix(board: Scoreboard) -> str | None:
    """One concrete first move, only when the evidence supports it."""
    wrong = [r for r in board.records
             if r.case.answerable and r.correctness is False]
    if len(wrong) >= 2:
        shared = set(wrong[0].case.expected_sources)
        for r in wrong[1:]:
            shared &= set(r.case.expected_sources)
        if shared:
            doc = sorted(shared)[0]
            return (f"Smallest useful fix first: {len(wrong)} failing cases "
                    f"all expect '{doc}'; inspect that document and its "
                    f"chunking before touching prompts.")
    retrieval_faults = [r for r in wrong if r.status("retrieval_hit") == FAIL]
    if wrong and len(retrieval_faults) == len(wrong):
        return ("Smallest useful fix first: every failing case also failed "
                "retrieval_hit, so fix retrieval before touching generation.")
    return None


def appendix_verdict(record) -> str:
    """What the case was judged on, for the per-case table.

    A refusal case has no right answer to compare against, so it is
    excluded from accuracy and its `correctness` is None. Printing that
    as "unscored" would be false twice over: the case was evaluated, and
    a bot that answered a question it must decline would be shown
    identically to one that correctly refused. Report the refusal
    outcome, which is what correct behavior means for these cases.
    """
    if not record.case.answerable:
        return {PASS: "refused",
                FAIL: "did not refuse"}.get(
                    record.status("refuses_when_required"), "no answer")
    return {True: "pass", False: "fail", None: "unscored"}[record.correctness]


def localization(record) -> str | None:
    if record.correctness is not False:
        return None
    hit = record.status("retrieval_hit")
    if hit == PASS:
        return ("Where it broke: retrieval_hit PASSED, the right evidence was "
                "in context; the model contradicted or ignored it. Generation fault.")
    if hit == FAIL:
        return ("Where it broke: retrieval_hit FAILED, the evidence never "
                "reached the model. Retrieval fault.")
    if record.reply.contexts:
        return ("Where it broke: contexts came back, but retrieval_hit had "
                "nothing to check (no must_contain or expected_sources), so "
                "this failure cannot be localized.")
    return ("Where it broke: no contexts came back for this case, so "
            "retrieval fault and generation fault cannot be told apart.")


def render(board: Scoreboard, endpoint_url: str, judge_desc: str,
           command: str, calibration: dict | None,
           wall_clock_s: float, judge_calls: int,
           is_demo: bool = False) -> str:
    suite = board.suite
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = []
    add = lines.append

    add(f"# Report card · {suite.name}")
    add("")
    add(f"**{banner_line(board)}**")
    add("")
    add("| endpoint | tests | judge | date | wall clock | tool |")
    add("|---|---|---|---|---|---|")
    add(f"| {endpoint_url} | {suite.path.split('/')[-1]} "
        f"(sha256 {suite.sha256[:12]}) | {judge_desc} | {now} | "
        f"{_fmt_latency(wall_clock_s)} | agent-report-card {__version__} |")
    add("")
    if is_demo:
        add("Demo run. The graded system is the fixture bot bundled with "
            "this tool, a fictional Northstar Telecom support bot with "
            "flaws planted on purpose so the report has something to find. "
            "Every company, document, figure and failure below is synthetic.")
        add("")

    # ---- Verdict ----
    unreliable_note = (" (judge unreliable this run, trust the "
                       "deterministic column)" if board.judge_unreliable else "")
    add(f"## Verdict: {board.verdict}{unreliable_note}")
    add("")
    reasons = []
    for name, ok, text in board.gate_results:
        if ok is False:
            reasons.append(f"Gate failed: {text}.")
    if not reasons and board.verdict != VERDICT_FAIL:
        for name, ok, text in board.gate_results:
            if ok is True:
                reasons.append(f"Gate passed: {text}.")
    for reason in reasons[:3]:
        add(f"- {reason}")
    fix = smallest_fix(board)
    if fix:
        add(f"- {fix}")
    gates = suite.gates
    origin = "set by this test file" if gates.explicit else \
        "this tool's default opinions; override them in the YAML gates block"
    criticals_clause = ("cases tagged critical must pass every code check, "
                        "a leaked trace or a blown latency budget included"
                        if gates.criticals_must_pass
                        else "the criticals gate is disabled by this test file")
    add(f"- Bars used ({origin}): accuracy at least "
        f"{100 * gates.min_accuracy:g}%, hallucination at most "
        f"{100 * gates.max_hallucination:g}%, {criticals_clause}. "
        f"This verdict holds against this test set and these gates, nothing more.")
    if board.warnings:
        add("")
        for w in board.warnings:
            add(f"- Warning: {w}.")
    add("")

    # ---- Scorecard ----
    add("## Scorecard")
    add("")
    add("| metric | result | note |")
    add("|---|---|---|")
    wd = board.wilson_det
    wilson_note = (f"95% interval {round(100 * wd[0])}% to {round(100 * wd[1])}%"
                   if wd else "")
    add(f"| accuracy, deterministic route | {board.accuracy_det.pct()} | "
        f"{wilson_note} |")
    add(f"| accuracy, judge route | {board.accuracy_judge.pct()} | "
        f"routes shown side by side on purpose |")
    add(f"| hallucination (ungrounded vs retrieval, not untrue) | "
        f"{board.hallucination.pct()} | judge-fed |")
    n_refusal_cases = sum(1 for r in board.records if not r.case.answerable)
    add(f"| citation validity | {board.citations.pct()} | per check, not per "
        f"citation; judge_citation_support joins this denominator on a "
        f"judged run |")
    add(f"| refusal handling | {board.refusals.pct()} | per check, not per "
        f"case: {_n(n_refusal_cases, 'refusal case')}, plus judge_refusal "
        f"on a judged run |")
    if board.latencies:
        add(f"| latency p50 / p95 / slowest | "
            f"{_fmt_latency(percentile(board.latencies, 50))}"
            f" / {_fmt_latency(percentile(board.latencies, 95))}"
            f" / {_fmt_latency(max(board.latencies))} | "
            f"over {len(board.latencies)} requests; p95 is nearest-rank, so "
            f"on a suite this small it can sit below the slowest request |")
    add(f"| judge calls | {judge_calls} | judge errors: {board.judge_error_count} |")
    add("")
    add("Formulas: deterministic accuracy = answerable cases (the ones this "
        "test file says the bot should answer rather than decline) passing "
        "every correctness check they define, which means exact_match, "
        "contains_all, contains_none, numbers_agree and regex_match (an "
        "unanswered case counts as wrong), over cases with at least one "
        "applicable. Judge accuracy = judge_correct passes over judge-scored "
        "answerable cases; only a case that declares an expected answer is "
        "judge-scored, so this denominator is usually smaller than the "
        "deterministic one and the two percentages are not over the same "
        "cases. Hallucination = judge_grounded failures over cases where "
        "grounding was evaluated. Citation validity = passes over applicable "
        "citation checks. Refusal handling = passes over applicable refusal "
        "checks.")
    add("")

    # check by check, inside the scorecard
    add("### Check by check")
    add("")
    _check_table(add, board)
    add("An n/a row means no case in this test file exercised that check, "
        "so the failure mode it catches is untested here, not cleared.")
    add("")

    # ---- Failures ----
    add("## Failures, quoted")
    add("")
    failing = [r for r in board.records if r.failed_checks]
    failing.sort(key=lambda r: min(SEVERITY.get(c.name, 9)
                                   for c in r.failed_checks))
    if not failing:
        add("No case failed a check on this run.")
        add("")
    else:
        add(f"{_n(len(failing), 'case')} failed at least one check. The "
            f"banner's failure count ({board.banner_failures}) is narrower "
            f"on purpose: it counts answerable cases whose correctness "
            f"verdict failed, while this section quotes every case that "
            f"failed anything.")
        add("")
    for i, r in enumerate(failing, 1):
        names = ", ".join(c.name for c in r.failed_checks)
        judge_only = all(ROUTE_BY_NAME.get(c.name) == "judge"
                         for c in r.failed_checks)
        flag = " (judge-flagged)" if judge_only else ""
        add(f"### {i}. {r.case.id}{flag}")
        add("")
        add(f"**Question:** {' '.join(r.case.question.split())}")
        add("")
        if r.case.expected:
            add(f"**Expected:** {' '.join(r.case.expected.split())}")
            add("")
        add("**Got:**")
        add("")
        add(_quote(r.reply.answer if not r.reply.error
                   else f"(no usable answer: {r.reply.error})"))
        add("")
        add(f"**Failed:** {names}")
        for c in r.failed_checks:
            if c.detail:
                add(f"- {c.name}: {c.detail}")
        loc = localization(r)
        if loc:
            add(f"- {loc}")
        add("")

    # ---- Needs human review ----
    add("## Needs human review")
    add("")
    if board.disagreements:
        add("The two scoring routes disagreed on these cases. The tool does "
            "not know which is right; you decide.")
        add("")
        for r in board.disagreements:
            det = "pass" if r.det_correct else "fail"
            jud = "pass" if r.judge_correct else "fail"
            reason = r.detail("judge_correct")
            add(f"- {r.case.id}: deterministic route says {det}, judge says "
                f"{jud}. Judge's reason: {reason or '(none given)'}")
    elif not board.judged:
        add("Only the deterministic route ran, so nothing was cross-checked. "
            "A judged run grades the answerable cases a second way and lists "
            "any case the two routes disagree on here.")
    else:
        both = [r for r in board.records if r.case.answerable
                and r.det_correct is not None and r.judge_correct is not None]
        add(f"No case graded by both routes disagreed. {len(both)} of the "
            f"{board.accuracy_det.den} deterministically scored cases were "
            f"also judge-scored; the rest define no expected answer, so the "
            f"judge never graded them and the deterministic route is their "
            f"only check.")
    add("")

    # ---- Judge's own report card ----
    add("## The judge's own report card")
    add("")
    if not board.judged:
        add("The judge did not run (--judge none). Every number above comes "
            "from the deterministic route; judge checks are shown as n/a, "
            "never as passes.")
    elif calibration:
        add(f"Judge: {judge_desc}, temperature 0, prompt set "
            f"{prompts.PROMPT_VERSION} (hash {prompts.prompt_hash()}).")
        add("")
        add(f"On its {calibration['n']}-item hand-labeled exam this judge "
            f"scored {calibration['agreement']}/{calibration['n']} "
            f"({round(100 * calibration['agreement'] / calibration['n'])}%): "
            f"false passes {calibration['false_pass']}/"
            f"{calibration['n_fail_labeled']} (the dangerous direction), "
            f"false fails {calibration['false_fail']}/"
            f"{calibration['n_pass_labeled']}, and it caught "
            f"{calibration['subtle_caught']}/{calibration['subtle_total']} "
            f"of the subtle numeric errors (answers wrong by under 1%).")
        add("")
        add("Read the judge columns with that error rate in mind. Judge "
            "verdicts are evidence, not proof, and the judge is never the "
            "sole authority on numeric facts (numbers_agree is the "
            "deterministic backstop). The exam's labeled pairs are "
            "English-only, so judge reliability on other languages is "
            "unmeasured.")
    else:
        add(f"Judge: {judge_desc}, temperature 0, prompt set "
            f"{prompts.PROMPT_VERSION} (hash {prompts.prompt_hash()}). "
            f"Judge not calibrated: run agent-report-card judge-check to "
            f"measure this judge's error rate on the labeled exam; until "
            f"then, trust the deterministic column first.")
    add("")

    # ---- Honest limits ----
    add("## What this report cannot tell you")
    add("")
    n_det = board.accuracy_det.den
    n_judge = board.accuracy_judge.den
    add(f"- Scoring routes: {_n(n_det, 'case')} deterministically scored, "
        f"{n_judge} judge-scored, {_n(board.judge_error_count, 'judge error')}.")
    add("- Grounded is not the same as true: if your documents are wrong, a "
        "grounded answer is still wrong. Reference answers are assumed "
        "correct.")
    if board.accuracy_det.applicable and board.accuracy_det.den > 0:
        move = round(100 / board.accuracy_det.den)
        add(f"- Sample size: with {board.accuracy_det.den} scored cases, one "
            f"flipped case moves accuracy by about {move} points. The Wilson "
            f"interval in the scorecard is wide because the suite is small, "
            f"which is honesty, not a bug.")
    add("- Number matching does no unit conversion and does not canonicalize "
        "Thai digits; a correct answer expressed in different units can fail "
        "numbers_agree and must be triaged with must_contain.")
    add("- Substring matching makes no word-boundary assumptions, so a short "
        "must_contain string can match inside an unrelated longer word "
        "(this is what makes it work for unsegmented Thai text, and also "
        "its limitation).")
    add("- Secret scrubbing is exact-substring: an endpoint that transforms "
        "a header secret before echoing it can still leak it.")
    if board.judged:
        add("- Answers and retrieved contexts are sent verbatim to the "
            "judge URL for grading; keep the judge local when answers may "
            "carry sensitive content.")
    add("- This reflects a hand-written test set, not production traffic, "
        "and it does not test security, prompt injection, or multi-turn "
        "behavior. For those, see promptfoo and Inspect.")
    add("")

    # ---- Reproduce ----
    add("## Reproduce")
    add("")
    add("```")
    add(command)
    add("```")
    add("")
    add(f"Tests file sha256 {suite.sha256}. Tool version {__version__}, "
        f"prompt set {prompts.PROMPT_VERSION} (hash {prompts.prompt_hash()}). "
        f"Runs are seedless by design; the judge runs at temperature 0 but "
        f"large local models are not bit-stable across machines.")
    if board.judged:
        import platform
        add("")
        add(f"Judged on: {platform.system()} {platform.machine()}, judge "
            f"served locally by Ollama.")
    add("")
    add("Cross-check: the scores sidecar written beside this report carries "
        "every raw per-case record; scripts/recount.py in the repository "
        "recomputes all rollups from it independently, and the test suite "
        "asserts equality with the numbers above.")
    add("")
    add("<details><summary>Per-case appendix</summary>")
    add("")
    add("Correctness is the verdict on the answer alone, from the five "
        "content checks named under Formulas, or refused / did not refuse "
        "for a case this test file marks answerable: false. A case can read "
        "pass here and still have failed a citation, grounding, leak, "
        "refusal or latency check; those are in the next column, and they "
        "are what the criticals gate keys on.")
    add("")
    add("| case | correctness | failed checks | latency |")
    add("|---|---|---|---|")
    for r in board.records:
        verdict = appendix_verdict(r)
        names = ", ".join(c.name for c in r.failed_checks) or "none"
        add(f"| {r.case.id} | {verdict} | {names} | "
            f"{_fmt_latency(r.reply.latency_s)} |")
    add("")
    add("</details>")
    add("")

    return scrub.scrub("\n".join(lines))


def _scrub_tree(obj):
    """Scrub every string BEFORE json.dumps: JSON escaping (quotes,
    backslashes, unicode) inside a secret would otherwise defeat the
    exact-substring replacement."""
    if isinstance(obj, str):
        return scrub.scrub(obj)
    if isinstance(obj, list):
        return [_scrub_tree(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _scrub_tree(v) for k, v in obj.items()}
    return obj


def scores_sidecar(board: Scoreboard, endpoint_url: str, judge_desc: str,
                   command: str, wall_clock_s: float) -> str:
    """Machine sidecar (unstable format in v0.1)."""
    payload = {
        "format": "agent-report-card/scores",
        "format_stability": "unstable-v0.1",
        "tool_version": __version__,
        "prompt_version": prompts.PROMPT_VERSION,
        "prompt_hash": prompts.prompt_hash(),
        "suite": board.suite.name,
        "tests_sha256": board.suite.sha256,
        "endpoint": endpoint_url,
        "judge": judge_desc,
        "command": command,
        "wall_clock_s": round(wall_clock_s, 3),
        "verdict": board.verdict,
        "warnings": board.warnings,
        "gates": [{"name": n, "ok": ok, "text": t}
                  for n, ok, t in board.gate_results],
        "banner_failures": board.banner_failures,
        "rollups": {
            "accuracy_det": [board.accuracy_det.num, board.accuracy_det.den],
            "accuracy_judge": [board.accuracy_judge.num, board.accuracy_judge.den],
            "hallucination": [board.hallucination.num, board.hallucination.den],
            "citations": [board.citations.num, board.citations.den],
            "refusals": [board.refusals.num, board.refusals.den],
        },
        "cases": [
            {
                "id": r.case.id,
                "answerable": r.case.answerable,
                "correctness": r.correctness,
                "det_correct": r.det_correct,
                "judge_correct": r.judge_correct,
                "latency_s": round(r.reply.latency_s, 4),
                "checks": [{"name": c.name, "status": c.status,
                            "detail": c.detail} for c in r.checks],
            }
            for r in board.records
        ],
    }
    return json.dumps(_scrub_tree(payload), indent=2, ensure_ascii=False)
