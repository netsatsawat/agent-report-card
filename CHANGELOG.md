# Changelog

Notable changes per release. Numbers quoted here come from committed
artifacts in [`reports/`](reports/), not from memory.

## Unreleased

Nothing yet.

## 0.2.0 — 2026-08-07

Opens the 0.2 line. Judge measurement, per PRD 7.1.

### Added

- **The judge's exam now breaks down by category.** One aggregate hid the
  failure that matters: a judge scoring 28/30 while missing four of the
  five subtle-numeric pairs reported as 93% correct and was useless at
  exactly the job this tool exists for. Every report with a calibrated
  judge now carries a per-category table.
- **Cohen's kappa beside raw agreement.** The exam is balanced 15/15, so a
  judge answering at random scores about 50% raw. Kappa calls that 0.00.
  Computed from the stored per-pair record, so an exam sat before this
  release breaks down and scores without being re-run.
- Every rate carries its denominator and a 95% Wilson interval, and no
  percentage is printed for a category with fewer than five pairs.
  `unit_swap` has two and `non_refusal` has one; a rate there is noise
  wearing a decimal point, so those rows show the tally and say why.
  Even a perfect small category admits its uncertainty: 5/5 bounds to
  57% to 100%, not to certainty.
- `scoring.separable()`: whether two judges' intervals are far enough
  apart for 30 items to tell them apart at all. Groundwork for judge
  comparison, which must answer "too close to separate" rather than rank.

### Fixed

- `wilson()` could return a lower bound above the rate it was drawn
  around. At zero successes the arithmetic landed on 2.8e-17 rather than
  0, so a 0/5 category produced an interval excluding its own point
  estimate. Rounding hid it in the report; asserting `lo <= p <= hi`
  across every k/n found it. Bounds are now clamped to the point estimate
  as well as to [0, 1].

## 0.1.2 — 2026-08-06

### Added

- `--html PATH` on `run` and `demo`: a self-contained HTML rendering of
  the same report, for the stakeholder who would rather receive an
  attachment than a markdown file. Inline CSS, zero JavaScript, no
  external requests of any kind, a `@media print` stylesheet so it makes
  a clean PDF, and light/dark via `prefers-color-scheme`. Off by default;
  the markdown report is still the product.

### How it avoids becoming a second source of truth

The HTML is a projection of the markdown string `render()` already
returned, never a second reading of the scoreboard, so it cannot contain
a number the markdown does not. Three tests hold that line: `report_html`
is parsed to assert it imports nothing from the package (an import of the
scoreboard would recreate the second surface), every committed report
must convert with an unrecognized line raising rather than being skipped,
and the number tokens in the HTML must equal the markdown's exactly.

Because the report quotes answers written by the system under test, the
converter escapes before applying the report's own markers, passes
through only two allowlisted raw-HTML lines matched in full, emits no
attribute carrying text from the run, and ships a Content-Security-Policy
whose `style-src` is the hash of the stylesheet actually emitted.

### Fixed

- Every tool failure now exits 2 with an actionable message. A missing,
  unreadable, non-UTF-8 or wrongly-typed suite file previously escaped as
  a Python traceback and exited 1, which is the code CI reads as "a gate
  failed", so a typo in `--tests` reported that the bot had regressed. An
  unwritable `--out` or `--scores` did the same. A catch-all now makes it
  impossible for any internal error to claim exit 1.
- The report's cross-check claim is true again: `scripts/recount.py`
  scored an unanswered case differently from the runner, so the two could
  disagree while the report asserted they matched.
- The judge calibration cache is keyed on the host as well as the model,
  so a report can no longer cite an exam that a different machine's judge
  sat under the same model name.
- A duplicated YAML key is refused instead of silently keeping the last
  one, which could drop an entire `cases:` block without a word.
- An endpoint URL carrying a query string no longer has the suite's path
  appended inside the query, which sent every request to `/`.
- Reports now say what each number is not: the appendix explains what
  `correctness` covers, the latency row prints the slowest request
  alongside a nearest-rank p95 that can sit below it, refusal cases read
  `refused` or `did not refuse` rather than `unscored`, `n/a` is labelled
  untested rather than cleared, and a demo run says the graded company is
  fictional.

## 0.1.1 — 2026-08-06

First release on PyPI: `pip install agent-report-card`. No change to the
check catalog, the scoring, or the report format.

### Added

- `--help` that documents itself: every flag on every subcommand carries
  its description and default, the top-level help shows worked examples
  grouped by intent, and `run --help` states the exit-code contract that
  CI depends on. A test fails the build if a flag ever ships without help
  text.
- `SECURITY.md`: what the tool reads, what it sends where, how secret
  scrubbing works and precisely where it fails, and an honest note that
  prompt injection from the system under test into the judge is inherent
  to LLM-as-judge and undefended in v0.1.
- PyPI trusted publishing (`.github/workflows/publish.yml`). No API token
  exists in the repository, in GitHub secrets, or on a developer machine.
  The workflow re-runs the full suite and the README-claims verifier
  before uploading.

### Notes

Published as 0.1.1 rather than 0.1.0 because `v0.1.0` was tagged before
the publishing pipeline existed. Publishing "0.1.0" would have uploaded a
build from a later commit than the tag pointed at, and PyPI never allows
re-uploading a version, so the mismatch would have been permanent and
invisible. The rule is now in the PRD as FR-1a and RC-11: the tagged tree
is the tree that gets built.

## 0.1.0 — 2026-08-06

The initial build, tagged and released on GitHub but never published to
PyPI (see above).

### Added

- RAG QA mode: point the CLI at an HTTP endpoint with a hand-written YAML
  (or JSON) test suite and get `report.md`, a one-page verdict with the
  failing answers quoted verbatim.
- 14 deterministic checks and 5 local-judge checks, a fixed catalog with
  no plugin API. Generated into [`CHECKS.md`](CHECKS.md) from the same
  table the code runs.
- Accuracy computed by two independent routes. The deterministic route
  wins the verdict; disagreements are surfaced for a human rather than
  averaged away.
- Verdicts of PASS / PASS WITH WARNINGS / NOT READY from the thresholds
  in your own YAML, with exit codes 0, 1, and 2 for CI.
- The judge's own report card: a 30-pair hand-labeled exam including five
  answers wrong by under one percent, with the result embedded in every
  report it grades.
- Retrieval-versus-generation localization on every failure, secret
  scrubbing across every output surface, and a bundled fixture bot whose
  planted flaws reproduce the documented numbers from real execution.
