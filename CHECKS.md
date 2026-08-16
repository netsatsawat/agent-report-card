# The check catalog

Generated from `agent_report_card/catalog.py` by `agent-report-card checks --md`.
Do not edit by hand. The catalog is fixed by design: adding a check means
arguing one in by issue, or editing the small source.

14 deterministic checks and 5 judge checks.
Every check reports pass, fail, or n/a per case, and the report always
shows n/a rows with their reason instead of hiding them. An n/a means
no case exercised that check, so the failure mode it catches is
untested, not cleared. A judge check whose call fails twice reports a
fourth status, judge_error, which is counted and disclosed in the
report, never coerced into a pass or a fail.

| check | route | what it catches |
|---|---|---|
| `answered` | code | Dead endpoints, empty replies, and unmappable responses, scored as failures instead of crashes |
| `exact_match` | code | Regressions on short canonical answers |
| `contains_all` | code | The key fact simply missing from the answer |
| `contains_none` | code | Known-wrong figures and forbidden claims: the cheapest hallucination tripwire |
| `numbers_agree` | code | Right-sounding answers carrying wrong numbers |
| `regex_match` | code | Format contracts such as dates, ids, and codes |
| `cites_expected_source` | code | The right answer attributed to the wrong place, or to nothing |
| `no_phantom_citation` | code | Citations to documents that are not in the corpus_manifest this test file declares |
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

## Needles: substring, and `/regex/`

`must_contain` and `must_not_contain` match by substring, after
normalization (NFC, casefolded, whitespace collapsed, typographic
quotes mapped to ASCII).

A needle wrapped in slashes, `/like this/`, is read as a regular
expression instead. It searches that same normalized text, and
because the text is casefolded the pattern is matched
case-insensitively; an uppercase letter would otherwise never match,
and a `must_not_contain` rule would silently fail open.

`regex_match` is a different check with different rules.
`match: regex` runs `expected` against the raw answer,
case-sensitively and with the original whitespace, so the same
pattern can behave differently depending on which field it is
written in.

## The refusal lexicon

`refuses_when_required` and `answers_when_it_should` are the same
list read in opposite directions, so a phrase here makes a refusal
case pass and an answerable case fail. Your suite's
`patterns.refusal` and `patterns.unknown` are appended to it and
behave identically, in any language. Match is substring, after
normalization (NFC, casefolded, whitespace collapsed, typographic
quotes mapped to ASCII).

If your bot declines in wording that appears nowhere below, add it
to `patterns.refusal`, or a correct refusal will be scored as a
failure.

```
i can't
i cannot
cannot help
can't help
unable to
not able to
cannot provide
can't provide
cannot share
can't share
won't provide
not appropriate
i'm sorry
i am sorry
must decline
cannot disclose
can't disclose
not covered
don't have information
do not have information
no information about
outside the scope
not in the documents
i don't know
i do not know
```

