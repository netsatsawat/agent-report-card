# Changelog

Notable changes per release. Numbers quoted here come from committed
artifacts in [`reports/`](reports/), not from memory.

## Unreleased

Nothing yet.

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
