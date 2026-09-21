# Security

## Supported versions

v0.2.x is the current line. Fixes land on `main` and ship in the next tag.

## What this tool does with your data

Worth knowing before you point it at a production endpoint.

- **No API keys are read from anywhere.** There is no environment variable
  the tool looks for on its own. The only environment access is explicit
  `${VAR}` references you write in your own suite's `endpoint.headers`
  block, and an unset variable is a fail-fast error naming the variable,
  never its value.
- **No telemetry.** The only outbound requests are to the endpoint you
  pass on the command line and the judge URL you configure. Nothing is
  reported anywhere, and `--judge none` runs fully offline.
- **Header secrets are scrubbed from every output surface** (report,
  scores sidecar, console, error messages) by exact-substring replacement
  with the `${VAR}` placeholder, and the same applies to credentials in
  the endpoint URL's userinfo or query string. The limitation is stated in
  every generated report: replacement is exact-substring, so an endpoint
  that transforms a secret before echoing it can still leak it.
- **Answers and retrieved contexts are sent to the judge URL** for
  grading. If the answers under test may carry sensitive content, keep the
  judge local (the default) rather than pointing it at a remote host. Every
  judged report names the judge and says whether it was local.
- **Reports quote your bot's answers verbatim.** Treat a generated
  `report.md` with the same care as the data your bot handles before
  committing it to a public repository.
- **A suite file cannot redirect requests.** `endpoint.path` must begin
  with `/`, validated at load time, so a test file can never smuggle a
  host or userinfo into the URL and send your headers somewhere else.
- **The bundled fixture bot binds loopback only** (`127.0.0.1`) and serves
  invented data about a fictional company.

## Known limitations

The judge is an LLM reading text produced by the system under test, so a
sufficiently adversarial answer could attempt to influence its verdict.
This is inherent to LLM-as-judge and is not defended against in v0.2. It
is one reason the deterministic route wins the verdict, the judge is never
the sole authority on a number, and every judge-only failure is labeled
as such in the report.

This tool tests accuracy, grounding, citations, and refusal behavior. It
does **not** test prompt injection, jailbreaks, or other security
properties of your bot. For that, see promptfoo or Giskard.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting on this repository
(Security → Report a vulnerability) rather than opening a public issue.
If that is unavailable, reach the author through
[satsawat.ai](https://satsawat.ai).

Expect an acknowledgement within a week. This is a small, single-maintainer
project, so please set expectations accordingly.
