# agent-report-card v0.1 build plan

> **Amended 2026-08-05, post-PRD adversarial review (19 confirmed findings).**
> PRD.md is now the binding contract; this file remains as the design
> rationale. Deliberate deviations from the original plan, recorded per this
> file's own change rule: (1) the deterministic catalog grows from 12 to 14,
> adding `refuses_when_required` and `answers_when_it_should` as lexicon
> checks (needed so the demo's answered-unanswerable flaw is visible without
> a judge, and so Thai refusal phrases are testable deterministically via the
> new top-level `patterns` block, which also carries `leak_markers`,
> `refusal`, and `unknown` extensions); (2) the fixture bot's default port
> changes from 8765 to 8000 and `demo` materializes `board_questions.yaml`
> in the working directory, so the README's promised command runs verbatim
> against the demo; (3) the banner's hallucination number is judge-route
> only: the deterministic demo reproduces accuracy and the failure count,
> the committed judged sample report supplies the 6%, and `--judge none`
> output renders hallucination as n/a; (4) PASS WITH WARNINGS has defined
> triggers and exits 0 (exit 1 is strictly a failed gate); the
> `max_hallucination` gate is disclosed as judge-fed, is n/a without a
> judge, and downgrades to a warning when the judge fails calibration;
> (5) header secrets are actively scrubbed from all rendered output at
> render time, unit-tested, with the exact-substring limitation stated;
> (6) judge transport failures follow the retry-then-judge_error path, a
> separate judge timeout exists, and `run` fails fast (exit 2) when the
> judge is unreachable at startup; (7) packaging is explicit (MIT, PyPI at
> release, editable install before); (8) a static single-file HTML export
> (same document, inline CSS, no JS) is the first v0.1.1 candidate;
> (9) the suite schema also carries a top-level `defaults` block
> (budget_seconds, max_chars, tolerance) and a per-case `notes` field,
> both shown in the init starter; (10) post-build adversarial review
> (49 confirmed findings) tightened semantics: an unanswered answerable
> case scores as a wrong answer, the criticals gate renders n/a when no
> case is tagged critical, response mapping defaults now match the
> documented default contract, the suite's judge block is honored when
> the CLI flag is not given, and match: contains requires must_contain.
>
> **Amended again 2026-08-06 at release.** A final four-lens review of
> scripts, sample data, renderer templates, and safety confirmed 15 more
> findings, all fixed: the gallery now runs on a fixed port so a committed
> report's header, sidecar, log, and Reproduce command cannot contradict
> each other; judge free-text is flattened and capped before it can inject
> structure into a markdown bullet; `endpoint.path` must start with `/` so
> a suite file can never smuggle a host and send your headers elsewhere;
> and the localization line no longer claims "no contexts came back" when
> contexts did. Shipped alongside: documented `--help` with the exit-code
> contract, `SECURITY.md`, and PyPI trusted publishing.
>
> **The versioning rule, learned the hard way.** v0.1.0 was tagged before
> the publish workflow existed, so publishing "0.1.0" would have meant
> uploading a build from a later commit than the tag pointed at. Because
> PyPI never allows re-uploading a version, that inconsistency would have
> been permanent and undetectable to anyone comparing the two. The fix was
> to ship 0.1.1 rather than rewrite a published tag, and the rule is now
> in the PRD as FR-1a and RC-11: the tagged tree is the tree that gets
> built, verified before the tag is pushed.

Written 2026-08-05, from a design panel: one competitive-research pass over the
August 2026 eval landscape, three independent designs (minimal-first,
report-first, estate-integration-first), and a judge that scored them, named
what to graft, and flagged ten honesty problems before a line of code exists.
This file is the working contract for the build. When a decision here fights a
clever idea mid-build, this file wins unless it is edited first.

## What v0.1 is

A single CLI that takes a hand-written YAML test file and a live HTTP endpoint,
runs the checks that matter for a RAG QA bot, and writes a one-page markdown
report a stakeholder can read without installing anything: verdict up top,
failing cases quoted verbatim, and the tool's own limits stated inside the
report it generates. Local Ollama judge by default, zero API keys ever,
deterministic checks as the backbone so the judge is never the sole authority.

The README's promised command line is a contract and must work verbatim:

```
agent-report-card run --tests board_questions.yaml --endpoint http://localhost:8000
→ accuracy 84% · hallucination 6% · 3 failures → report.md
```

## Why this is worth building (research, compressed)

- Nobody ships the report. ragas emits a DataFrame, promptfoo a web grid plus
  HTML/JSON/CSV, DeepEval a terminal line plus a cloud share link, Inspect
  `.eval` logs, Langfuse/LangSmith dashboards. Hamel Husain's evals FAQ says
  the artifact teams need is a progress narrative with failures quoted, and no
  incumbent generates that document. A committed-to-git report.md is an empty
  niche.
- The timing wedge is real: OpenAI Evals shuts down 2026-11-30, and promptfoo
  was acquired by OpenAI in March 2026. "Your eval harness should not be
  someone's product" lands as lived news.
- The complaint patterns map directly to features: OpenAI-key friction (ragas's
  top issue class) → no keys ever; 50+ metrics → decision paralysis (DeepEval)
  → a small fixed catalog; no error localization on failures (the documented
  Langfuse/LangSmith gap) → the retrieval-vs-generation line in every failure
  block; judge reliability undocumented everywhere → the judge's own report
  card printed in every run.
- What incumbents own and we do not touch: comparison matrices (promptfoo),
  public benchmarks (Inspect/OpenBench), observability (Langfuse et al.),
  metric plugin libraries (DeepEval), red-teaming (promptfoo-in-OpenAI,
  Giskard), synthetic test generation (ragas).

## The verdict that picked this shape

Design 2 (report-first) is the backbone: it was the only design built backwards
from the report, which is the product's entire thesis. Scores: D1 minimal 41,
D2 report-first 40, D3 estate-first 38; D2 wins on differentiation (9/10) and
takes the named grafts below from the other two. Buildability risk in D2 is
managed by the build order: the deterministic product is complete and
demoable before the judge layer starts.

Grafted from D3 (estate-first): the engineered demo banner asserted by CI, the
five subtle-numeric calibration pairs, "The judge's own report card" section
with prompt hash, manifest-gated `no_phantom_citation`, `numbers_agree`
canonicalization, Wilson intervals tested against external reference values,
and the stale-data decoy document in the demo corpus.

Grafted from D1 (minimal): the `checks` subcommand generated from the same
table as the docs, demo auto-fallback to no-judge with a loud banner,
severity-ordered failures, the n/a rendering rule, fraction-with-percent
enforcement, and the calibration warning surfacing on the verdict line itself.

Not grafted, deliberately: D3's trace subcommand (v0.2 stays v0.2), the
--leaky flag, the --seed shuffle, D1's per-run 12-probe calibration (the
cached 30-pair judge-check is strictly better), and a second endpoint format
as code (the dot-path mapper already covers OpenAI-compatible shapes).

## Package shape

- Python 3.10+, package `agent_report_card`, console script `agent-report-card`.
- Dependencies: `pyyaml` + `httpx` only. No SDKs, no keys, no env vars read
  except explicit `${VAR}` expansion in YAML headers (redacted from reports).
- MIT. Installed via `pip install agent-report-card` or pipx once published;
  `pip install -e .` from clone until then.

## CLI surface

Four subcommands plus `checks`, argparse, no plugins.

1. `agent-report-card run --tests FILE --endpoint URL`
   Flags: `--judge SPEC` (default `ollama:qwen3.6:27b` at
   http://localhost:11434; `--judge none` is a first-class mode), `--out PATH`
   (default report.md), `--scores PATH` (default report.scores.json, the v0.3
   diffing seam, documented unstable), `--timeout SECS` (default 60),
   `--limit N`, `--tags T,T`, `-v` (per-case progress; judge runs are slow and
   silence is unacceptable).
   Exit codes: 0 verdict PASS, 1 gates failed (sovereign-rag's CI hook without
   pulling v0.3 forward), 2 tool or endpoint error.
2. `agent-report-card demo [--judge none] [--keep-serving]`
   Boots the bundled fixture bot (stdlib http.server, port 8765), runs the
   bundled suite, writes report.md. Auto-falls back to no-judge with a loud
   banner when Ollama is unreachable; the stranger path must never error.
3. `agent-report-card init`
   Writes a heavily commented starter YAML showing every field, including the
   OpenAI-compatible `choices.0.message.content` mapping example.
4. `agent-report-card judge-check [--judge SPEC]`
   Runs the 30-pair labeled calibration set, prints accuracy, false-pass rate
   (the dangerous direction), false-fail rate, and subtle-numeric recall
   separately. Caches per model + prompt hash; every report embeds the cached
   numbers or says "judge not calibrated".
5. `agent-report-card checks`
   Prints the catalog, one line per check: name, route, what it catches.
   CHECKS.md is generated from the same table so the two cannot drift.

## YAML schema

Top-level: `suite`, `endpoint` (optional mapping block), `judge` (optional),
`gates` (optional thresholds), `corpus_manifest` (optional list of legitimate
source ids), `cases` (required). Unknown keys are a hard error with the line
number and case id. No synthetic generation, ever: a 20-to-40 question
hand-written file is the feature.

```yaml
suite: "Board questions: HR policy bot"

endpoint:
  method: POST
  path: /ask                     # appended to a bare --endpoint origin
  request:
    question_field: question     # body becomes {"question": "..."}
  response:                      # dot-paths; `*` maps over lists
    answer: answer               # or choices.0.message.content
    contexts: contexts.*.text    # optional; unlocks grounding checks
    sources: contexts.*.source   # optional; unlocks citation checks
  headers:
    Authorization: "Bearer ${ARC_TOKEN}"   # env-expanded, never in the report

gates:                           # verdict bars; defaults documented in report
  min_accuracy: 0.80
  max_hallucination: 0.05
  criticals_must_pass: true

corpus_manifest: [hr-policy-2025.md, leave-faq.md]

cases:
  - id: leave-01
    question: "How many days of parental leave does the policy allow?"
    expected: "30 business days"
    match: number                # exact | contains | number | regex | judge
    must_contain: ["30"]
    must_not_contain: ["90"]     # the known hallucination tripwire
    expected_sources: ["hr-policy-2025.md"]
    tags: [policy, critical]

  - id: oob-01
    question: "What is our CEO's home address?"
    answerable: false            # correct behavior is refusal
    tags: [safety, critical]
```

## Check catalog

Fixed, no plugin API. The README says "the checks that matter"; the generated
catalog carries the exact count, and no rounded check count is ever quoted as
a feature. Every check is binary pass/fail with a one-line "what it catches",
and records which route computed it.

Deterministic route (pure Python, 12):

1. `answered`: HTTP 2xx, non-blank answer, within timeout. Dead endpoints are
   errors, not failures.
2. `exact_match`: normalized equality (NFC, casefold, whitespace collapse)
   when `match: exact`.
3. `contains_all`: every `must_contain` present after normalization.
4. `contains_none`: no `must_not_contain` present. The cheapest hallucination
   tripwire.
5. `numbers_agree`: every number in the gold appears in the answer within
   tolerance, canonicalizing 1,500 / 1500 / THB1500 / 3.2%. The judge is never
   sole authority on numeric facts; this check is why.
6. `regex_match`: `match: regex` against `expected` as pattern.
7. `cites_expected_source`: a reported source matches `expected_sources`.
8. `no_phantom_citation`: every cited id exists in `corpus_manifest`; n/a
   without a manifest. (Replaces the unsound "union of sources seen this run"
   idea, which a colliding fabrication would pass.)
9. `retrieval_hit`: when contexts return, at least one contains a
   `must_contain` string or an expected source name. Exists to localize:
   retrieval_hit pass + wrong answer = generation fault; retrieval_hit fail =
   retrieval fault. This line prints in every failure block.
10. `no_error_leak`: fixed pattern list (Traceback, "as an AI language model",
    unrendered tool-call JSON, "<|", stack-frame paths) plus suite additions.
11. `length_in_bounds`: 1 to 4000 chars default, per-case override.
12. `latency_under`: wall clock under the gate when set; always recorded.

Judge route (local Ollama, binary verdicts, 5):

13. `judge_correct`: same key facts as the gold. The judged accuracy headline.
14. `judge_grounded`: every factual claim supported by returned contexts.
    Failures are the hallucination number. When no contexts are mapped this is
    n/a with an explanation, never estimated. (The panel's proposed
    `judge_hallucination` fallback was cut: without retrieval visibility it is
    a coin flip dressed as a check.)
15. `judge_refusal`: for `answerable: false`, did the system decline rather
    than answer around the refusal regex.
16. `judge_citation_support`: does the cited passage support the claim citing
    it. The check thai-rag-bench will reuse.
17. `judge_on_topic`: does the answer address the question asked.

Stretch only, first cut if hours run out: `stability_probe` (re-ask 3
answerable cases, compare extracted numbers; renders as "probe, n=3" with the
fraction, never as a stability percentage).

Rollups, with formulas printed in the report: accuracy per route (deterministic
wins the score; disagreements are surfaced, never resolved), hallucination
rate, citation rate, refusal accuracy, latency p50/p95, Wilson 95% interval on
accuracy at suite N.

## Judge design

- Transport: Ollama HTTP API, temperature 0, no SDK. One binary question per
  call, never a combined rubric. Prompts live in `prompts.py` with a version
  string; the prompt hash prints in every report so prompt changes are visible
  in git diffs of report.md.
- Every prompt demands strict JSON `{"verdict": "...", "reason": "..."}` where
  the reason must quote the offending words; the quotes feed the failure
  blocks directly.
- Parse discipline: strip fences and thinking tags, one retry with a terser
  nudge, then the case is `judge_error`: excluded from denominators, counted
  in its own line, never coerced to pass or fail.
- Calibration: `fixtures/judge_calibration.yaml`, 30 hand-labeled pairs, 15
  pass / 15 fail, deliberately including correct paraphrase, unit swap
  (business vs calendar days), verbose-but-correct, and 5 subtle-numeric-wrong
  pairs off by under 1% (the six-cent-miss class agent-failure-lab documented:
  its verifier caught the big slips and missed the small ones). Subtle-numeric
  recall reports separately. Below 80% agreement, the verdict line itself
  carries "judge unreliable this run, trust the deterministic column."
- Wording discipline: 30 items supports "measured error rate on this labeled
  set", not "calibrated". A case failing only on a judge check is labeled
  "judge-flagged", visually distinct from code-verified failures.

## Report structure

report.md, main body under two pages, designed to be forwarded by a CTO who
reads only the first screen. Headings in order:

1. Title + one banner line in the README grammar, then a metadata table
   (endpoint, tests sha, judge + prompt version, date, tool version, wall
   clock).
2. **Verdict**: PASS / PASS WITH WARNINGS / NOT READY, from the YAML gates
   (deterministic, no LLM in the verdict), up to three plain-English reasons
   with fractions, the phrase "against this test set and these gates", and
   when the evidence supports it a "smallest useful fix first" bullet.
3. **Scorecard**: both accuracy routes side by side (the compute-twice rule
   made visible), hallucination, citations, refusals, latency, plus the full
   check table. Not-applicable rows render as "n/a (no refusal cases)", never
   vanish. The hallucination caption itself says "ungrounded versus retrieval,
   not untrue": the scoreboard is what gets screenshotted, so the disclosure
   lives on the scoreboard, not only in the limits.
4. **Failures, quoted**: the centerpiece, severity-ordered (plumbing > wrong
   fact > hallucination > citation > style). Per failure: question, expected,
   verbatim answer (truncated at 600 chars), named failed checks, the judge's
   quoted reason, and the retrieval-vs-generation localization line.
5. **Needs human review**: every route disagreement, both verdicts shown,
   framed as "the tool does not know; you decide." Rendered even when empty,
   because absence is information.
6. **The judge's own report card**: model, temperature, prompt hash,
   calibration numbers with subtle-numeric recall broken out, and one sentence
   translating them into how much to trust the judge columns.
7. **Honest limits**: routes and counts, judge_error count, "grounded is not
   true: if your documents are wrong, a grounded answer is still wrong",
   sample-size arithmetic spelled out ("with 20 cases, one flipped case moves
   accuracy by 5 points"), no unit conversion in number matching, what this
   tool does not test (security, injection, multi-turn) with promptfoo and
   Inspect named.
8. **Reproduce**: exact command, tests-file sha256, seedless by design,
   per-case appendix in a details block. report.scores.json carries the same
   numbers for the exit-code gate and future v0.3 diffing.

Renderer rules enforced by the golden test: every percentage carries its
fraction, verbatim quotes never paraphrased, zero em dashes in generated
output.

## Demo

`agent-report-card demo` is the whole pitch in one command: a fixture HR-policy
bot (stdlib http.server, keyword retrieval over 6 short markdown docs,
including a stale `old_pricing_2024.md` decoy) with deterministic planted
flaws, one per check class: a wrong number, an answer sourced from the decoy
doc, one fabricated ungrounded claim, one citation to a nonexistent doc, one
correct-but-uncited answer, one confident answer to an `answerable: false`
question, one slow path, one leaked Traceback. One refusal handled correctly
so the report is not all red.

The suite is tuned so the deterministic route reproduces the README banner
exactly: 16/19 answerable cases correct (84%), 1/16 context-bearing cases
ungrounded (6%), 3 failures. Both README and demo report must carry the
sentence that these numbers come from a bundled fixture bot with deliberately
planted failures; without it the banner reads as results from a real system.

Two tiers: `demo --judge none` completes offline in about a minute;
full `demo` with Ollama produces the judged report and prints its own wall
clock. No minutes estimate appears in the README until measured on the actual
machine; the README quotes a measured run.

## Verification (house rules, non-negotiable)

- `make verify` runs: unit tests (stdlib-mocked judge via injectable
  transport), a no-judge demo run, and `scripts/check_demo_expectations.py`
  asserting the scores sidecar matches the committed expected failure vector.
  Every planted flaw is a regression test on the checks themselves.
- Compute-twice, three ways: (a) `scripts/recount.py` independently recomputes
  all rollups from report.scores.json and a test asserts equality, with the
  cross-check stated in the report footer; (b) accuracy exists as two semantic
  routes in every run with disagreements listed; (c) the Wilson interval
  implementation is unit-tested against externally computed reference values
  with provenance comments.
- `scripts/verify_readme_claims.py` re-runs the deterministic demo and fails
  if any number quoted in the README drifts from fresh output.
- A golden-file test pins the demo report (modulo timestamp), including the
  fraction-with-percent and no-em-dash assertions.
- e2e test boots the real bot over real HTTP and asserts the planted
  scorecard for the no-judge path.
- CI (GitHub Actions, free runner): tests + verify_readme_claims with
  `--judge none`. CI honestly documented as not covering the judge; judged
  sample reports are labeled with machine, model, and prompt hash.
- Build in a fresh `.venv`; everything must be executable before any commit
  claims it works.

## Build sequence (~29h against the 30h ceiling)

1. `schema.py` + `client.py`: YAML load, strict line-numbered validation,
   dot-path response mapper, env-expanded redacted headers, tests. ~4h.
2. `checks_code.py`: the 12 deterministic checks, numbers_agree
   canonicalization, no_phantom_citation, one normalization pipeline,
   table-driven tests including Thai NFC cases. ~4h.
3. `scoring.py`: route resolution, rollups, gates, verdict levels, Wilson
   interval vs reference values. ~3h.
4. `demo_bot.py` + fixtures corpus + demo suite tuned to the 84/6/3 banner,
   e2e test asserting the planted scorecard. ~3.5h.
   **Checkpoint: end-to-end demoable with --judge none around hour 14.**
5. `report.py`: the product. Verdict block, localization lines,
   severity-ordered quoted failures, n/a rows, style enforcement, scores
   sidecar, golden test. ~4h.
6. `recount.py` + `verify_readme_claims.py` + CI workflow. ~1.5h.
7. `checks_judge.py` + `prompts.py`: versioned hashed prompts, strict parse,
   retry-then-judge_error, the 5 judge checks. ~4h.
8. Calibration: hand-label the 30 pairs well (including the 5 subtle-numeric),
   judge-check command, per-model cache, judge's report card section wired
   into every report with the warning threshold. ~3h.
9. README rewrite (line one: no API keys, ever, by default), generated
   CHECKS.md + `checks` subcommand, init template, committed demo report and
   judged sample report. ~2h.
10. Stretch, in order, only if under 29h: demo fallback polish, stability
    probe, OpenAI-compatible worked example in init.

Steps 1 to 6 (~20h) already yield the honest, CI-verified, screenshotable
deterministic product; the judge layer is additive risk, not existential risk.

## Out of scope for v0.1, each with its reason

- Agent-trace mode: v0.2 as the README promises; the scores sidecar is the
  only groundwork, documented unstable.
- Baseline diffing / fail-on-regression: v0.3; exit code 1 on gate failure is
  the entire CI concession now.
- Web UI, dashboards, HTML output, cloud sync: the identity is no platform;
  markdown or nothing.
- Comparison matrices, public benchmarks, observability, red-teaming,
  synthetic test generation: incumbents own them (see research).
- Plugin API / custom check registration: the sprawl vector. Extension means
  arguing a check in or out of the catalog by issue, or editing the small
  source.
- Cloud judge adapters: local by default, no keys ever read. (Not "localhost
  only": the judge URL flag accepts what it accepts, and we do not claim an
  enforcement that does not exist.)
- Embedding-similarity checks, multi-turn, streaming endpoints, auth beyond a
  bearer header, concurrency, Windows promises, Thai-aware tokenization
  (thai-rag-bench's job; the normalization limitation is stated in limits).

## Article

"Why Your AI Agent Needs a Performance Review (Literally)", as the scaffold
promises. The arc: open with the artifact itself (paste the demo verdict
block); the empty-niche argument with Hamel's progress-narrative FAQ; the
timing wedge (OpenAI Evals dies 2026-11-30, promptfoo belongs to OpenAI, a
markdown file cannot be deprecated); the trust move (the judge takes the exam
it grades, and every report prints its judge's error rate, including the
subtle-numeric misses carried over from agent-failure-lab's verifier lesson);
close with the one-command offline demo. Pre-sales framing: this is the
one-page document that ends the "is it safe to ship" meeting.

## Risks, with mitigations already in the design

1. Judge wall clock (tens of calls on a 27B model): -v progress, --limit,
   first-class no-judge tier, wall clock printed, no unmeasured time claims.
2. Judge quality on grounding: calibration measured every run, judge-flagged
   vs code-verified labeling, deterministic gates, numbers never judge-only.
   If calibration lands under ~80%, say so in the README and narrow the claim.
3. Endpoint diversity: the second run (their bot, not the demo) is where
   adoption dies. Mitigations: dot-path mapper with the OpenAI-compatible
   example, init template, a crisp "what your endpoint must return" section.
   Streaming is unsupported and stated.
4. Verdict over-trust: "against this test set and these gates" is fixed
   language, Wilson intervals print, and the wide interval at N=20 gets one
   plain explanatory sentence so it reads as honesty, not a bug.
5. Scope creep from siblings and strangers: this file plus the generated
   catalog are the written contract. thai-rag-bench drives Thai in its own
   repo; sovereign-rag integration stays an example mapping, never a
   dependency.
