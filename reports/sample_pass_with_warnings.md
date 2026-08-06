# Report card · Release regression: Northstar support bot, flaw-free subset

**accuracy 100% (11/11) · hallucination n/a (grounding needs the judge; drop --judge none to evaluate it) · 0 failures · PASS WITH WARNINGS**

| endpoint | tests | judge | date | wall clock | tool |
|---|---|---|---|---|---|
| http://localhost:8123 | release_questions.yaml (sha256 92fcf23338ba) | none (deterministic only) | 2026-08-06 04:06 UTC | 0.02s | agent-report-card 0.1.1 |

Demo run. The graded system is the fixture bot bundled with this tool, a fictional Northstar Telecom support bot with flaws planted on purpose so the report has something to find. Every company, document, figure and failure below is synthetic.

## Verdict: PASS WITH WARNINGS

- Gate passed: deterministic accuracy 100% (11/11) against the 80% floor.
- Gate passed: all 2 critical-tagged cases passed their code checks.
- Bars used (set by this test file): accuracy at least 80%, hallucination at most 5%, cases tagged critical must pass every code check, a leaked trace or a blown latency budget included. This verdict holds against this test set and these gates, nothing more.

- Warning: the judge-fed max_hallucination gate could not be evaluated (grounding needs the judge; drop --judge none to evaluate it).

## Scorecard

| metric | result | note |
|---|---|---|
| accuracy, deterministic route | 100% (11/11) | 95% interval 74% to 100% |
| accuracy, judge route | n/a (judge did not run) | routes shown side by side on purpose |
| hallucination (ungrounded vs retrieval, not untrue) | n/a (grounding needs the judge; drop --judge none to evaluate it) | judge-fed |
| citation validity | 100% (20/20) | per check, not per citation; judge_citation_support joins this denominator on a judged run |
| refusal handling | 100% (1/1) | per check, not per case: 1 refusal case, plus judge_refusal on a judged run |
| latency p50 / p95 / slowest | 0.00s / 0.00s / 0.00s | over 12 requests; p95 is nearest-rank, so on a suite this small it can sit below the slowest request |
| judge calls | 0 | judge errors: 0 |

Formulas: deterministic accuracy = answerable cases (the ones this test file says the bot should answer rather than decline) passing every correctness check they define, which means exact_match, contains_all, contains_none, numbers_agree and regex_match (an unanswered case counts as wrong), over cases with at least one applicable. Judge accuracy = judge_correct passes over judge-scored answerable cases; only a case that declares an expected answer is judge-scored, so this denominator is usually smaller than the deterministic one and the two percentages are not over the same cases. Hallucination = judge_grounded failures over cases where grounding was evaluated. Citation validity = passes over applicable citation checks. Refusal handling = passes over applicable refusal checks.

### Check by check

| check | route | what it catches | result |
|---|---|---|---|
| `answered` | code | Dead endpoints, empty replies, and unmappable responses, scored as failures instead of crashes | 12/12 passed |
| `exact_match` | code | Regressions on short canonical answers | n/a (match is not 'exact') |
| `contains_all` | code | The key fact simply missing from the answer | 5/5 passed |
| `contains_none` | code | Known-wrong figures and forbidden claims: the cheapest hallucination tripwire | 1/1 passed |
| `numbers_agree` | code | Right-sounding answers carrying wrong numbers | 6/6 passed |
| `regex_match` | code | Format contracts such as dates, ids, and codes | n/a (match is not 'regex') |
| `cites_expected_source` | code | The right answer attributed to the wrong place, or to nothing | 10/10 passed |
| `no_phantom_citation` | code | Citations to documents that do not exist in your corpus | 10/10 passed |
| `retrieval_hit` | code | Localization: whether a wrong answer is a retrieval fault or a generation fault | 10/10 passed |
| `no_error_leak` | code | Stack traces and plumbing served to users as answers | 12/12 passed |
| `refuses_when_required` | code | The bot answering a question it must decline | 1/1 passed |
| `answers_when_it_should` | code | Over-refusal on legitimate questions | 11/11 passed |
| `length_in_bounds` | code | Empty replies and runaway rambles | 12/12 passed |
| `latency_under` | code | Answers too slow for the seat they are meant to fill | n/a (no budget_seconds set; latency recorded anyway) |
| `judge_correct` | judge | Paraphrased-but-wrong answers that string matching cannot see | n/a (judge did not run) |
| `judge_grounded` | judge | Claims the retrieved passages do not support: the hallucination number | n/a (judge did not run) |
| `judge_refusal` | judge | Refusals that answer anyway in polite words | n/a (judge did not run) |
| `judge_citation_support` | judge | Decorative citations that do not support the sentence citing them | n/a (judge did not run) |
| `judge_on_topic` | judge | Dodging and topic drift | n/a (judge did not run) |

An n/a row means no case in this test file exercised that check, so the failure mode it catches is untested here, not cleared.

## Failures, quoted

No case failed a check on this run.

## Needs human review

Only the deterministic route ran, so nothing was cross-checked. A judged run grades the answerable cases a second way and lists any case the two routes disagree on here.

## The judge's own report card

The judge did not run (--judge none). Every number above comes from the deterministic route; judge checks are shown as n/a, never as passes.

## What this report cannot tell you

- Scoring routes: 11 cases deterministically scored, 0 judge-scored, 0 judge errors.
- Grounded is not the same as true: if your documents are wrong, a grounded answer is still wrong. Reference answers are assumed correct.
- Sample size: with 11 scored cases, one flipped case moves accuracy by about 9 points. The Wilson interval in the scorecard is wide because the suite is small, which is honesty, not a bug.
- Number matching does no unit conversion and does not canonicalize Thai digits; a correct answer expressed in different units can fail numbers_agree and must be triaged with must_contain.
- Substring matching makes no word-boundary assumptions, so a short must_contain string can match inside an unrelated longer word (this is what makes it work for unsegmented Thai text, and also its limitation).
- Secret scrubbing is exact-substring: an endpoint that transforms a header secret before echoing it can still leak it.
- This reflects a hand-written test set, not production traffic, and it does not test security, prompt injection, or multi-turn behavior. For those, see promptfoo and Inspect.

## Reproduce

```
agent-report-card run --tests examples/release_questions.yaml --endpoint http://localhost:8123 --judge none
```

Tests file sha256 92fcf23338ba8d383989feb107359339d1ff9ca6ef95244fabcc4d6fda4b00ae. Tool version 0.1.1, prompt set v1 (hash 1bf57252a9a4). Runs are seedless by design; the judge runs at temperature 0 but large local models are not bit-stable across machines.

Cross-check: the scores sidecar written beside this report carries every raw per-case record; scripts/recount.py in the repository recomputes all rollups from it independently, and the test suite asserts equality with the numbers above.

<details><summary>Per-case appendix</summary>

Correctness is the verdict on the answer alone, from the five content checks named under Formulas, or refused / did not refuse for a case this test file marks answerable: false. A case can read pass here and still have failed a citation, grounding, leak, refusal or latency check; those are in the next column, and they are what the criticals gate keys on.

| case | correctness | failed checks | latency |
|---|---|---|---|
| r01-churn | pass | none | 0.00s |
| r02-roaming | pass | none | 0.00s |
| r03-arpu | pass | none | 0.00s |
| r04-stores | pass | none | 0.00s |
| r05-parental | pass | none | 0.00s |
| r06-sick-leave | pass | none | 0.00s |
| r07-rollover | pass | none | 0.00s |
| r08-daily-cap | pass | none | 0.00s |
| r09-churn-driver | pass | none | 0.00s |
| r10-fiber | pass | none | 0.00s |
| r11-loyalty | pass | none | 0.00s |
| r12-cfo-address | refused | none | 0.00s |

</details>
