# PRD: agent-report-card v0.1

| | |
|---|---|
| Product | agent-report-card, RAG QA mode |
| Version | v0.1 (first public release) |
| Status | Approved for build |
| Owner | Satsawat Natakarnkitkul |
| Date | 2026-08-05 |
| Provenance | Synthesized from a five-agent design panel (competitive research, three independent designs, scoring judge), then hardened by a four-lens adversarial review (19 confirmed findings applied). PLAN.md holds the design rationale and the amendment record. |

## 1. Problem and opportunity

Teams shipping RAG bots and agents cannot answer "is it safe to ship" with
evidence a non-engineer can read. The August 2026 eval landscape leaves the
gap open: ragas emits a DataFrame, promptfoo (now OpenAI-owned) a web grid,
DeepEval a terminal line plus a cloud share link, Inspect `.eval` logs,
Langfuse and LangSmith dashboards. No incumbent generates the document
practitioners actually circulate: a one-page narrative with the verdict up
top and the failing answers quoted. Teams hand-write that page today.

Three tailwinds: OpenAI Evals shuts down 2026-11-30, forcing migrations and
making "your eval harness should not be someone's product" timely; ragas's
top issue class is API-key friction, making "no keys ever" a headline
guarantee; DeepEval's 50+ metrics produce documented decision paralysis,
making a small fixed catalog a feature.

## 2. Product definition

One CLI. It takes a hand-written YAML test file and a live HTTP endpoint,
runs a fixed catalog of binary checks (deterministic code plus a local
LLM judge), and writes `report.md`: a one-page markdown verdict a
stakeholder reads without installing anything, committed to git, diffable
in pull requests. The promised command line is a contract, verbatim:

```
agent-report-card run --tests board_questions.yaml --endpoint http://localhost:8000
→ accuracy 84% · hallucination 6% · 3 failures → report.md
```

This command runs literally against the bundled demo (FR-42, RC-8) and
against any user endpoint with their own file and URL substituted.

### Product principles

1. The report is the product, not the exhaust.
2. No API keys, ever, by default. Local judge first, not local-possible.
3. Deterministic checks are the backbone. The judge is never the sole
   authority on numeric facts. Judge-fed inputs to the verdict are
   disclosed as such, render n/a without a judge, and degrade to warnings
   when the judge fails its own calibration.
4. Decision-oriented, not score-oriented: ship or do not ship, with the
   three reasons quoted.
5. Honesty is a feature: the tool grades its own judge and prints the
   result in every report.
6. Not a framework, not a platform: no plugins, no dashboard, no cloud.

## 3. Users

- **Primary: the builder.** An engineer or advanced analyst with a running
  RAG bot on an HTTP endpoint. Writes the YAML, runs the CLI, fixes what
  the report quotes.
- **Secondary: the reader.** A product owner, CTO, or client who receives
  report.md and decides. Never installs anything; the report must stand
  alone.
- **Tertiary: the estate.** sovereign-rag consumes the exit code as its CI
  regression gate; thai-rag-bench will import the citation-faithfulness
  check; the companion article demonstrates the tool.

## 4. Goals and non-goals

### Goals (release-blocking; each traces to release criteria)

- G1. A stranger goes from install to a readable demo report, offline,
  with no model and no keys, in one command. The elapsed time is
  measured, quoted in the README from a real run, and never estimated.
  (RC-2, RC-6)
- G2. The README's promised command works verbatim against the demo:
  `demo --keep-serving` serves the fixture bot on port 8000 and
  materializes `board_questions.yaml`, and the command exits per contract.
  (FR-42, RC-8)
- G3. Every number quoted in the README is produced by a committed,
  re-runnable artifact and asserted by CI. (RC-5, RC-6)
- G4. Every report names its judge, prints the judge's measured error
  rate, and states its own limits. (FR-36, JR-2, RC-3)
- G5. sovereign-rag can gate CI on the exit code alone. (FR-3, RC-2)

### Non-goals for v0.1 (each with its reason)

- Agent-trace mode: v0.2 as the roadmap promises; the scores sidecar is
  the only groundwork and is documented as unstable.
- Baseline diffing and regression deltas: v0.3; thresholds-plus-exit-code
  is the entire CI story now.
- Web UI, dashboards, interactive HTML, cloud sync: platform is the
  anti-goal. (A static single-file HTML export of the same document is
  the first v0.1.1 candidate; see section 12.)
- Model or prompt comparison matrices: promptfoo owns it; wrong question
  for a ship decision.
- Public benchmarks: Inspect and OpenBench own it; they grade models, this
  grades your application.
- Synthetic test-set generation: ragas's complexity trap; a hand-written
  20-to-40 question file is the feature.
- Plugin or custom-check API: the sprawl vector; extension means arguing a
  check in or out of the catalog by issue, or editing the small source.
- Cloud judge adapters (OpenAI, Anthropic): local by default, no keys ever
  read. The judge URL flag accepts what it accepts; no false "localhost
  only" enforcement is claimed.
- Multi-turn conversations, streaming endpoints, auth beyond one bearer
  header, concurrency, embedding-similarity checks, Windows promises.
- Thai word segmentation and Thai judge calibration: thai-rag-bench's job
  (section 8 states exactly what does ship).

## 5. Functional requirements

### 5.1 CLI and packaging

- FR-1. Console script `agent-report-card`, package `agent_report_card`,
  subcommands `run`, `demo`, `init`, `judge-check`, `checks`. Python
  3.10+, dependencies `pyyaml` and `httpx` only. MIT license, LICENSE
  file committed. v0.1 publishes to PyPI at the release tag; before
  publication the README's install path is clone plus `pip install -e .`,
  and the README states which one it is quoting.
- FR-2. `run` accepts `--tests`, `--endpoint`, `--judge` (default
  `ollama:qwen3.6:27b` at `http://localhost:11434`; `none` is a
  first-class mode), `--out` (default report.md), `--scores` (default
  report.scores.json), `--timeout` (per endpoint HTTP call, default 60s),
  `--judge-timeout` (per judge call, default 120s; judge calls on large
  local models legitimately run long), `--limit`, `--tags`, `-v`
  (per-case progress; long judge runs must never be silent).
- FR-3. Exit codes: 0 = verdict PASS or PASS WITH WARNINGS, 1 = any gate
  failed, 2 = tool error (invalid YAML, unreachable endpoint, or judge
  unreachable at `run` startup when a judge was requested; the error
  names `--judge none` as the fallback, and `run` never falls back
  silently). Scores never crash the tool.
- FR-4. `demo` boots the bundled fixture bot (stdlib http.server, default
  port 8000), materializes `board_questions.yaml` in the working
  directory if no file of that name exists, runs it against the bot, and
  writes the report. If Ollama is unreachable, `demo` (unlike `run`)
  falls back to `--judge none` with a loud printed banner; the stranger
  path must never error. `--keep-serving` leaves the bot up for the
  verbatim command; `--port` overrides.
- FR-5. `init` writes a fully commented starter YAML including the
  OpenAI-compatible `choices.0.message.content` mapping example.
- FR-6. `judge-check` runs the labeled calibration set against the
  configured judge and prints agreement, false-pass rate, false-fail
  rate, and subtle-numeric recall separately; result cached per model and
  prompt hash.
- FR-7. `checks` prints the catalog (name, route, one-line "what it
  catches"); CHECKS.md is generated from the same table so code and docs
  cannot drift.

### 5.2 Test-suite YAML

- FR-8. Top-level keys: `suite`, `endpoint` (optional mapping block),
  `judge`, `gates`, `patterns` (suite extensions to the built-in
  `refusal`, `unknown`, and `leak_markers` lists, in any language),
  `corpus_manifest`, `cases`. Only `cases` and each case's `question` are
  required.
- FR-9. Endpoint mapping: method, path, request field name, dot-path
  response mapping for answer, contexts, and sources (`*` maps over
  lists), plus headers with `${VAR}` environment expansion. Every
  expanded value is scrubbed from all rendered output (report, scores
  sidecar, console, error messages) by exact-substring replacement with
  its `${VAR}` name at render time, unit-tested under RC-1. Limitation
  stated in the report's limits section: scrubbing is exact-substring, so
  an endpoint that transforms and echoes a secret can still leak it. An
  unset `${VAR}` is a fail-fast validation error naming the variable
  (name only, never a value) before any request is sent.
- FR-10. Per-case fields: `id`, `question`, `expected`, `match` (exact,
  contains, number, regex, judge), `tolerance`, `must_contain`,
  `must_not_contain`, `expected_sources`, `answerable: false`,
  `max_chars`, `budget_seconds`, `tags`. `critical` tag participates in
  the verdict.
- FR-11. Validation is strict and friendly: unknown keys, duplicate ids,
  and contradictory fields fail fast with the line number, the case id,
  and a one-line fix. All files are UTF-8.

### 5.3 Checks: deterministic route (14)

Every check is binary, records its route, and has a one-line "what it
catches" that appears in `checks` output and the report. The catalog is
fixed; the two lexicon checks (FR-22, FR-23) are a recorded amendment
over the original 12-check plan (see PLAN.md) so that refusal behavior is
testable without a judge and in any language.

- FR-12. `answered`: HTTP 2xx, non-blank answer, within timeout. A 2xx
  response whose body is not valid JSON, or whose answer dot-path
  resolves to nothing, fails `answered` with the mapping error recorded
  and quoted in the failure block; the run continues (never exit 2).
  Missing contexts or sources paths degrade the checks that need them to
  per-case n/a, never crash.
- FR-13. `exact_match`: normalized equality when `match: exact`.
  Normalization everywhere: NFC unicode, casefold, whitespace collapse,
  no word-boundary assumptions.
- FR-14. `contains_all`: every `must_contain` present after
  normalization.
- FR-15. `contains_none`: no `must_not_contain` present after
  normalization.
- FR-16. `numbers_agree`: every number in the gold appears in the answer
  within tolerance, canonicalizing thousands separators, currency
  prefixes, and percent forms (1,500 / 1500 / THB1500 / 3.2%). No unit
  conversion, and no Thai-digit (๑๒๓) canonicalization in v0.1; both
  stated in limits.
- FR-17. `regex_match` when `match: regex`.
- FR-18. `cites_expected_source`: a reported source matches
  `expected_sources`.
- FR-19. `no_phantom_citation`: every cited id exists in
  `corpus_manifest`; n/a without a manifest. Never inferred from sources
  seen during the run.
- FR-20. `retrieval_hit`: when contexts return, at least one contains a
  required string or expected source. Exists for localization: its
  pass/fail combined with the correctness verdict yields the
  "retrieval fault vs generation fault" line in every failure block.
- FR-21. `no_error_leak`: built-in pattern list (Traceback, "as an AI
  language model", unrendered tool-call JSON, "<|", stack-frame paths)
  plus suite-supplied `patterns.leak_markers`.
- FR-22. `refuses_when_required`: for `answerable: false` cases, the
  answer matches the refusal lexicon (built-in English list plus
  `patterns.refusal`).
- FR-23. `answers_when_it_should`: answerable cases do not match the
  refusal lexicon; catches over-refusal.
- FR-24. `length_in_bounds` with per-case `max_chars` override.
- FR-25. `latency_under` with per-case `budget_seconds` override; latency
  always recorded regardless.

### 5.4 Checks: judge route (5)

- FR-26. `judge_correct`: same key facts as the gold; the judged accuracy
  headline.
- FR-27. `judge_grounded`: every factual claim supported by returned
  contexts; failures are the hallucination number; the unsupported claim
  is quoted. When no contexts are mapped, renders n/a with an
  explanation, never estimated.
- FR-28. `judge_refusal`: confirms flagged refusals actually declined
  (semantic second route over FR-22's lexicon).
- FR-29. `judge_citation_support`: the cited passage supports the
  sentence citing it.
- FR-30. `judge_on_topic`: the answer addresses the question asked.
- FR-31. Judge transport: Ollama HTTP API, temperature 0, one binary
  question per call, strict JSON verdict with a quoted reason. Any
  per-call failure (JSON parse, timeout, connection error, non-200)
  gets one retry, then the check is recorded `judge_error`: excluded
  from denominators, counted and disclosed, never coerced to pass or
  fail.
- FR-32. Prompts live in `prompts.py` with a version string; the prompt
  hash prints in every report.

### 5.5 Scoring and verdict

- FR-33. Accuracy computed by two independent routes (deterministic and
  judge), both always reported side by side. The deterministic route wins
  the verdict; every per-case disagreement is listed under "needs human
  review", never silently resolved.
- FR-34. Rollups, with their formulas printed in the report:
  hallucination rate = grounding failures over cases where grounding
  could be checked; citation and refusal rates per the catalog; latency
  p50/p95. A Wilson 95% interval accompanies accuracy, unit-tested
  against externally computed reference values.
- FR-35. Verdict levels and gate wiring:
  - Gate inputs are explicit: `min_accuracy` uses deterministic-route
    accuracy; `criticals_must_pass` counts only code-route check
    failures on `critical`-tagged cases; `max_hallucination` is
    judge-fed and disclosed as such in the report.
  - NOT READY / FAIL: any gate fails. PASS: all gates pass and no
    warning conditions. PASS WITH WARNINGS (exit 0): all hard gates
    pass but at least one of: route disagreements exist, judge_error
    count > 0, the judge failed calibration (JR-3), or a configured
    judge-fed gate could not be evaluated (`--judge none` or judge
    unreliable; never a silent pass).
  - When JR-3 fires, a failing `max_hallucination` gate downgrades from
    NOT READY to a warning, with the downgrade stated on the verdict
    line.
  - Defaults (documented in the report): min_accuracy 0.80,
    max_hallucination 0.05, criticals_must_pass true. The verdict always
    carries the fixed phrase "against this test set and these gates".

### 5.6 Report

- FR-36. Structure, in order: banner line and metadata; Verdict with up
  to three plain-English reasons and, when the evidence supports it, a
  "smallest useful fix first" bullet; Scorecard (both accuracy routes
  side by side, all rollups with formulas, full check table); Failures
  quoted verbatim, severity-ordered (plumbing > wrong fact >
  hallucination > citation > style), each with the localization line and
  the judge's quoted reason; Needs human review (rendered even when
  empty); The judge's own report card; Honest limits; Reproduce. Main
  body targets two pages; the per-case appendix lives in a collapsed
  details block.
- FR-37. Honest limits must enumerate, populated with the run's
  specifics: judge model and calibration numbers (or their absence);
  counts of code-scored vs judge-scored vs judge_error verdicts;
  "grounded is not the same as true: if your documents are wrong, a
  grounded answer is still wrong"; sample-size arithmetic spelled out
  ("with 20 cases, one flipped case moves accuracy by 5 points"); no
  unit conversion and no Thai-digit canonicalization in number matching;
  no word segmentation (substring matches can cross Thai word
  boundaries); secret scrubbing is exact-substring; what this tool does
  not test (security, injection, multi-turn), naming promptfoo and
  Inspect. Reproduce contains the exact command, tests-file sha256, tool
  and prompt versions, and the note that runs are seedless by design.
- FR-38. Renderer rules, asserted by the golden test: every percentage
  carries its fraction; not-applicable rows render as "n/a (reason)" and
  never vanish; quotes are verbatim, truncated at 600 characters with an
  ellipsis note; no em dashes; the hallucination caption itself says
  "ungrounded versus retrieval, not untrue".
- FR-39. `report.scores.json` sidecar carries per-case records and
  rollups for the exit-code gate and future v0.3 diffing; documented
  unstable in v0.1.

### 5.7 Demo and fixtures

- FR-40. Fixture bot: stdlib http.server, keyword retrieval over six
  short markdown docs including a stale-pricing decoy, deterministic
  planted flaws covering each failure class (wrong number, decoy-sourced
  answer, ungrounded claim, phantom citation, missing citation, answered
  unanswerable, slow path via a fixed simulated latency, leaked
  traceback) plus one correctly handled refusal.
- FR-41. Banner numbers, defined and sourced: the banner's "N failures"
  counts answerable cases failing the correctness verdict. The demo
  suite is tuned so (a) the deterministic route yields correctness
  16/19 = 84% and exactly 3 correctness failures, asserted against a
  fresh `--judge none` run in CI; (b) the judged run reproduces the full
  banner including hallucination 1/16 = 6%, committed as the sample
  report (RC-6) that the README quotes; (c) `--judge none` output
  renders the hallucination line as n/a per FR-27, never a substituted
  number. README and demo report both carry the sentence that these
  numbers come from a bundled fixture bot with deliberately planted
  failures.
- FR-42. The contract command runs verbatim: with `demo --keep-serving`
  active (port 8000, `board_questions.yaml` materialized), the promised
  command executes against the fixture bot and exits per FR-3.

## 6. Non-functional requirements

- NFR-1. Runs fully offline in `--judge none` mode; no telemetry, no
  network calls except to the user's endpoint and judge URL.
- NFR-2. No API key is read from anywhere; there is no env var the tool
  looks for except explicit `${VAR}` references in the user's YAML.
- NFR-3. Sequential execution; wall clock printed in the report header.
  No unmeasured time claim anywhere in the docs; the README quotes
  measured runs only.
- NFR-4. Built and tested on macOS and Linux; CI on the free GitHub
  runner covers everything except live-judge calls, and says so.
- NFR-5. Source small enough to read end to end (~1,400 lines across
  schema, client, checks, judge, scoring, report), because "edit the
  source" is the honest extension story.

## 7. The judge's own accountability

- JR-1. Calibration set: 30 hand-labeled pairs, 15 pass / 15 fail,
  including correct paraphrase, unit swap, verbose-but-correct, and five
  subtle-numeric-wrong pairs off by under 1% (the six-cent-miss class
  documented by agent-failure-lab's verifier experiment).
- JR-2. Every report embeds the cached calibration numbers for the judge
  in use, or the sentence "judge not calibrated, run
  agent-report-card judge-check".
- JR-3. Below 80% calibration agreement, the verdict line itself carries
  "judge unreliable this run, trust the deterministic column", and
  judge-fed gates downgrade per FR-35.
- JR-4. Wording discipline everywhere: 30 items supports "measured error
  rate on this labeled set", never "calibrated". Judge-only failures are
  labeled "judge-flagged", visually distinct from code-verified.

## 8. Language support in v0.1

What ships beyond English, stated exactly:

- LS-1. All inputs and outputs are UTF-8; questions, expected answers,
  `must_contain` strings, and reports may be in any language, including
  Thai, and render verbatim.
- LS-2. The normalization pipeline (NFC, casefold, whitespace and
  thousands-separator handling) makes the substring- and number-based
  checks well-defined for Thai text without word segmentation, because
  matching is substring-based, never token-based. The caveat is stated
  in every report's limits: a substring match can cross Thai word
  boundaries, so a short `must_contain` string can match inside an
  unrelated longer word; segmentation-aware matching is
  thai-rag-bench's job. Unit tests cover Thai-script fixtures for
  contains, numbers (THB forms; Thai digits ๑๒๓ are not canonicalized,
  stated in limits), and length checks.
- LS-3. Refusal, unknown-admission, and leak patterns: built-in lists are
  English; the `patterns` block extends them per suite in any language,
  so a Thai bot's refusals are testable deterministically (FR-22,
  FR-23) by supplying Thai phrases.
- LS-4. The judge inherits whatever languages the local model handles;
  the default qwen3.6:27b advertises multilingual coverage including
  Thai, so judged checks run on Thai suites. The calibration set is
  English-only in v0.1, and every report's limits section states that
  judge reliability was measured on English pairs only.
- LS-5. Not in v0.1, deferred to thai-rag-bench: Thai word segmentation,
  Thai-labeled calibration pairs, Thai judge benchmarking, and any claim
  of measured Thai judge quality. The demo corpus and sample suites are
  English.

## 9. Verification and release criteria

Release requires all of the following green, in a fresh venv:

- RC-1. Unit tests: every deterministic check table-driven (including
  Thai fixtures), schema validation errors (including unset `${VAR}`),
  secret scrubbing across report, sidecar, console, and error text,
  dot-path mapper including the OpenAI-compatible shape and
  malformed-2xx bodies, scoring formulas, gate logic including every
  PASS WITH WARNINGS trigger, Wilson interval vs reference values, judge
  JSON parsing including malformed-retry, transport-failure, and
  judge_error paths (recorded transports, no live model).
- RC-2. e2e test: boots the real fixture bot over HTTP, runs the bundled
  suite with `--judge none`, asserts the exact planted failure vector,
  the rollups, and the process exit codes for all three FR-3 outcomes
  (0 via relaxed gates, 1 via the default gates failing on the planted
  flaws, 2 via an unreachable endpoint).
- RC-3. Golden-file test pins the demo report byte-for-byte except an
  enumerated mask list: timestamp, wall clock, and all latency values
  (header, p50/p95, per-case appendix). Fraction-with-percent and
  no-em-dash assertions included.
- RC-4. `scripts/recount.py` independently recomputes all rollups from
  the scores sidecar; equality asserted; the cross-check is stated in the
  report footer.
- RC-5. `scripts/verify_readme_claims.py`: re-runs the deterministic demo
  and fails on drift between README-quoted deterministic numbers
  (accuracy, failure count) and fresh output, and fails if any other
  README-quoted number (hallucination, timings) differs from the
  committed judged artifacts it cites. Wired into CI.
- RC-6. Committed artifacts: the no-judge demo report, one judged sample
  report labeled with machine, model, and prompt hash (source of the
  banner's 6% and the README's measured timings), and the calibration
  JSON for the default judge produced by a real `judge-check` run.
- RC-7. README rewritten from the scaffold: line one is the no-keys
  guarantee; the quoted banner comes from RC-6 artifacts with the
  fixture disclosure sentence; a "what your endpoint must return"
  section specifies the request shape, the response dot-path mapping,
  and which checks unlock when contexts and sources are mapped.
- RC-8. Contract-command test: with `demo --keep-serving` active, the
  verbatim README command runs and exits per contract (G2, FR-42).

## 10. Milestones

Ordered build (~29h ceiling; the deterministic product stands alone by
milestone M4):

1. M1 schema + endpoint client + scrubbing + tests (4.5h)
2. M2 deterministic checks (14) + normalization + tests (4.5h)
3. M3 scoring, gates, verdict levels, Wilson (3h)
4. M4 fixture bot + tuned demo suite + e2e and contract-command tests
   (3.5h) — demoable
5. M5 report renderer + golden test (4h)
6. M6 recount + README-claims verifier + CI (1.5h)
7. M7 judge client + prompts + transport discipline (4h)
8. M8 calibration set + judge-check + report wiring (3h)
9. M9 README + generated CHECKS.md + init + committed artifacts (2h)
10. M10 stretch only: stability probe (rendered as "probe, n=3", never a
    percentage), demo polish.

## 11. Risks

1. Judge wall clock on a 27B model: mitigated by -v, --limit, the
   separate judge timeout, first-class no-judge tier, printed wall
   clock; risk of first-run abandonment remains.
2. Judge grounding quality: mitigated structurally (binary prompts,
   temperature 0, calibration disclosure, deterministic backstop, gate
   downgrade under JR-3); if calibration lands under 80%, the README
   narrows the claim.
3. Endpoint diversity: the user's second run is where adoption dies;
   mitigated by the dot-path mapper, init, and RC-7's required
   endpoint-contract README section. Streaming is out and stated.
4. Verdict over-trust: fixed hedge phrase, Wilson interval with one plain
   explanatory sentence.
5. Scope creep: this PRD and the generated catalog are the contract;
   sibling repos integrate by example, never by dependency.

## 12. Future versions

- v0.1.1 candidates (only if users ask): static single-file HTML export
  of the same report (same section order, inline CSS, zero JavaScript,
  no server; a second rendering of the document, never a dashboard, for
  the stakeholder who receives it by email), OpenAI-compatible judge URL
  option for LM Studio and vLLM, `judge_complete` for multi-part
  questions, per-category calibration breakdown.
- v0.2: agent-trace mode ingesting agent-failure-lab-style per-step
  JSONL; requires the lab to version its format first.
- v0.3: baseline diffing against a stored scores sidecar, fail-the-build
  on regression, trend lines across committed reports.
