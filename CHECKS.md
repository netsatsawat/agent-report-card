# The check catalog

Generated from `agent_report_card/catalog.py` by `agent-report-card checks --md`.
Do not edit by hand. The catalog is fixed by design: adding a check means
arguing one in by issue, or editing the small source.

14 deterministic checks and 5 judge checks.
Every check is binary per case (pass / fail / n/a), and the report always
shows n/a rows with their reason instead of hiding them.

| check | route | what it catches |
|---|---|---|
| `answered` | code | Dead endpoints, empty replies, and unmappable responses, scored as failures instead of crashes |
| `exact_match` | code | Regressions on short canonical answers |
| `contains_all` | code | The key fact simply missing from the answer |
| `contains_none` | code | Known-wrong figures and forbidden claims: the cheapest hallucination tripwire |
| `numbers_agree` | code | Right-sounding answers carrying wrong numbers |
| `regex_match` | code | Format contracts such as dates, ids, and codes |
| `cites_expected_source` | code | The right answer attributed to the wrong place, or to nothing |
| `no_phantom_citation` | code | Citations to documents that do not exist in your corpus |
| `retrieval_hit` | code | Localization: whether a wrong answer is a retrieval fault or a generation fault |
| `no_error_leak` | code | Stack traces and plumbing served to users as answers |
| `refuses_when_required` | code | The bot answering a question it must decline |
| `answers_when_it_should` | code | Over-refusal on legitimate questions |
| `length_in_bounds` | code | Empty replies and runaway rambles |
| `latency_under` | code | Answers too slow for the seat they are meant to fill |
| `judge_correct` | judge | Paraphrased-but-wrong answers that string matching cannot see |
| `judge_grounded` | judge | Claims the retrieved passages do not support: the hallucination number |
| `judge_refusal` | judge | Refusals that answer anyway in polite words |
| `judge_citation_support` | judge | Decorative citations that do not support the sentence citing them |
| `judge_on_topic` | judge | Dodging and topic drift |

