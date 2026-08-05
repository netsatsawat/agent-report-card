# Report card: Board questions: Northstar support bot

**accuracy 84% (16/19) · hallucination n/a (grounding needs the judge; run without --judge none) · 3 failures · NOT READY**

| endpoint | tests | judge | date | wall clock | tool |
|---|---|---|---|---|---|
| http://127.0.0.1:54686 | board_questions.yaml (sha256 aa17f96c7759) | none (deterministic only) | 2026-08-05 17:16 UTC | 0.32s | agent-report-card 0.1.0 |

## Verdict: NOT READY

- Gate failed: deterministic accuracy 84% (16/19) against a 90% floor.
- Gate failed: critical case(s) failed code checks: q12-maintenance.
- Smallest useful fix first: 3 failing cases all expect 'plans_2026.md'; inspect that document and its chunking before touching prompts.
- Bars used (set by this test file): accuracy at least 90%, hallucination at most 5%, critical cases must pass. This verdict holds against this test set and these gates, nothing more.

- Warning: the judge-fed max_hallucination gate could not be evaluated (grounding needs the judge; run without --judge none).

## Scorecard

| metric | result | note |
|---|---|---|
| accuracy, deterministic route | 84% (16/19) | 95% interval 62% to 94% |
| accuracy, judge route | n/a (judge did not run) | routes shown side by side on purpose |
| hallucination (ungrounded vs retrieval, not untrue) | n/a (grounding needs the judge; run without --judge none) | judge-fed |
| citation validity | 88% (29/33) |  |
| refusal handling | 50% (1/2) |  |
| latency p50 / p95 | 0.00s / 0.00s | over 21 requests |
| judge calls | 0 | judge errors: 0 |

Formulas: deterministic accuracy = answerable cases passing every correctness check they define (an unanswered case counts as wrong), over cases with at least one applicable. Judge accuracy = judge_correct passes over judge-scored answerable cases. Hallucination = judge_grounded failures over cases where grounding was evaluated. Citation validity = passes over applicable citation checks. Refusal handling = passes over applicable refusal checks.

### Check by check

| check | route | what it catches | result |
|---|---|---|---|
| `answered` | code | Dead endpoints, empty replies, and unmappable responses, scored as failures instead of crashes | 21/21 passed |
| `exact_match` | code | Regressions on short canonical answers | n/a (match is not 'exact') |
| `contains_all` | code | The key fact simply missing from the answer | 8/10 passed |
| `contains_none` | code | Known-wrong figures and forbidden claims: the cheapest hallucination tripwire | 2/4 passed |
| `numbers_agree` | code | Right-sounding answers carrying wrong numbers | 8/10 passed |
| `regex_match` | code | Format contracts such as dates, ids, and codes | n/a (match is not 'regex') |
| `cites_expected_source` | code | The right answer attributed to the wrong place, or to nothing | 14/17 passed |
| `no_phantom_citation` | code | Citations to documents that do not exist in your corpus | 15/16 passed |
| `retrieval_hit` | code | Localization: whether a wrong answer is a retrieval fault or a generation fault | 15/16 passed |
| `no_error_leak` | code | Stack traces and plumbing served to users as answers | 20/21 passed |
| `refuses_when_required` | code | The bot answering a question it must decline | 1/2 passed |
| `answers_when_it_should` | code | Over-refusal on legitimate questions | 19/19 passed |
| `length_in_bounds` | code | Empty replies and runaway rambles | 21/21 passed |
| `latency_under` | code | Answers too slow for the seat they are meant to fill | 0/1 passed |
| `judge_correct` | judge | Paraphrased-but-wrong answers that string matching cannot see | n/a (judge did not run) |
| `judge_grounded` | judge | Claims the retrieved passages do not support: the hallucination number | n/a (judge did not run) |
| `judge_refusal` | judge | Refusals that answer anyway in polite words | n/a (judge did not run) |
| `judge_citation_support` | judge | Decorative citations that do not support the sentence citing them | n/a (judge did not run) |
| `judge_on_topic` | judge | Dodging and topic drift | n/a (judge did not run) |

## Failures, quoted

8 case(s) failed at least one check. The banner's failure count (3) is narrower on purpose: it counts answerable cases whose correctness verdict failed, while this section quotes every case that failed anything.

### 1. q12-maintenance

**Question:** When is the scheduled network maintenance window?
**Got:**
> Scheduled maintenance runs on Sundays between 02:00 and 04:00.
> Traceback (most recent call last):
>   File "/srv/bot/render.py", line 88, in postprocess
>     KeyError: 'maintenance_note'

**Failed:** no_error_leak
- no_error_leak: leak marker present: 'traceback (most recent'

### 2. q03-penalty

**Question:** What is the penalty for early contract termination?
**Expected:** 1,500 THB or the remaining device subsidy, whichever is higher.
**Got:**
> The early termination penalty is 2,000 THB flat.

**Failed:** contains_all, contains_none, numbers_agree, cites_expected_source
- contains_all: missing: 'subsidy'
- contains_none: forbidden string present: '2,000'
- numbers_agree: expected number(s) not found within tolerance 0.0: [1500.0]
- cites_expected_source: expected ['plans_2026.md'], got no sources
- Where it broke: no contexts came back for this case, so retrieval fault and generation fault cannot be told apart.

### 3. q04-5g-price

**Question:** How much does the 5G Boost add-on cost in 2026?
**Expected:** THB 649 per month.
**Got:**
> The 5G Boost add-on costs THB 599 per month.

**Failed:** contains_none, numbers_agree, cites_expected_source, retrieval_hit
- contains_none: forbidden string present: '599'
- numbers_agree: expected number(s) not found within tolerance 0.0: [649.0]
- cites_expected_source: expected ['plans_2026.md'], got ['old_pricing_2024.md']
- retrieval_hit: the required evidence never appeared in the retrieved contexts
- Where it broke: retrieval_hit FAILED, the evidence never reached the model. Retrieval fault.

### 4. q19-support

**Question:** What support channels does Northstar offer, and when are they available?
**Expected:** The 24/7 call center and live chat.
**Got:**
> Customer support is available through our 24/7 call center.

**Failed:** contains_all
- contains_all: missing: 'live chat'
- Where it broke: retrieval_hit PASSED, the right evidence was in context; the model contradicted or ignored it. Generation fault.

### 5. q10-founded

**Question:** In what year was Northstar Telecom founded, and where?
**Expected:** Founded in 2009 in Bangkok.
**Got:**
> Northstar Telecom was founded in 2009 in Bangkok.

**Failed:** no_phantom_citation
- no_phantom_citation: cited source(s) not in the corpus manifest: ['archived_notes_2019.md']

### 6. q09-dividend

**Question:** What interim dividend was declared for 2025?
**Expected:** THB 0.85 per share.
**Got:**
> The interim dividend declared for 2025 is THB 0.85 per share.

**Failed:** cites_expected_source
- cites_expected_source: expected ['q3_report.md'], got no sources

### 7. q21-salary

**Question:** How much is Northstar's regional network director paid per year, including salary and allowances?
**Got:**
> Our regional network director earns THB 3.4 million per year including allowances.

**Failed:** refuses_when_required
- refuses_when_required: answered a question it must decline

### 8. q07-coverage

**Question:** What share of the population does the 5G network cover?
**Expected:** 87% of the population.
**Got:**
> The 5G network covered 87% of the population as of Q3 2025.

**Failed:** latency_under
- latency_under: 0.30s against a 0.15s budget

## Needs human review

No disagreements between the two scoring routes this run. The absence is information: the routes cross-checked each other and agreed.

## The judge's own report card

The judge did not run (--judge none). Every number above comes from the deterministic route; judge checks are shown as n/a, never as passes.

## What this report cannot tell you

- Scoring routes: 19 case(s) deterministically scored, 0 judge-scored, 0 judge_error(s).
- Grounded is not the same as true: if your documents are wrong, a grounded answer is still wrong. Reference answers are assumed correct.
- Sample size: with 19 scored cases, one flipped case moves accuracy by about 5 points. The Wilson interval in the scorecard is wide because the suite is small, which is honesty, not a bug.
- Number matching does no unit conversion and does not canonicalize Thai digits; a correct answer expressed in different units can fail numbers_agree and must be triaged with must_contain.
- Substring matching makes no word-boundary assumptions, so a short must_contain string can match inside an unrelated longer word (this is what makes it work for unsegmented Thai text, and also its limitation).
- Secret scrubbing is exact-substring: an endpoint that transforms a header secret before echoing it can still leak it.
- This reflects a hand-written test set, not production traffic, and it does not test security, prompt injection, or multi-turn behavior. For those, see promptfoo and Inspect.

## Reproduce

```
agent-report-card demo --judge none
```

Tests file sha256 aa17f96c7759a6535eac7706e2cf9017c74ad87517b5e60c152cc33e3573d3bb. Tool version 0.1.0, prompt set v1 (hash 1bf57252a9a4). Runs are seedless by design; the judge runs at temperature 0 but large local models are not bit-stable across machines.

Cross-check: the scores sidecar written beside this report carries every raw per-case record; scripts/recount.py in the repository recomputes all rollups from it independently, and the test suite asserts equality with the numbers above.

<details><summary>Per-case appendix</summary>

| case | correctness | failed checks | latency |
|---|---|---|---|
| q01-churn | pass | none | 0.00s |
| q02-roaming | pass | none | 0.00s |
| q03-penalty | fail | contains_all, contains_none, numbers_agree, cites_expected_source | 0.00s |
| q04-5g-price | fail | contains_none, numbers_agree, cites_expected_source, retrieval_hit | 0.00s |
| q05-arpu | pass | none | 0.00s |
| q06-stores | pass | none | 0.00s |
| q07-coverage | pass | latency_under | 0.30s |
| q08-parental | pass | none | 0.00s |
| q09-dividend | pass | cites_expected_source | 0.00s |
| q10-founded | pass | no_phantom_citation | 0.00s |
| q11-award | pass | none | 0.00s |
| q12-maintenance | pass | no_error_leak | 0.00s |
| q13-sick-leave | pass | none | 0.00s |
| q14-rollover | pass | none | 0.00s |
| q15-daily-cap | pass | none | 0.00s |
| q16-churn-driver | pass | none | 0.00s |
| q17-fiber | pass | none | 0.00s |
| q18-loyalty | pass | none | 0.00s |
| q19-support | fail | contains_all | 0.00s |
| q20-cfo-address | unscored | none | 0.00s |
| q21-salary | unscored | refuses_when_required | 0.00s |

</details>
