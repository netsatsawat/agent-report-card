"""agent-report-card CLI: run, demo, init, judge-check, checks."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from importlib import resources
from pathlib import Path

from . import __version__, calibrate, catalog, report_html, scrub
from .checks_code import run_code_checks
from .checks_judge import (DEFAULT_JUDGE, JudgeClient, parse_judge_spec,
                           run_judge_checks)
from .client import EndpointClient
from .report import banner_line, render, scores_sidecar
from .schema import SchemaError, load_suite
from .scoring import CaseRecord, score

EXIT_OK, EXIT_GATE_FAILED, EXIT_ERROR = 0, 1, 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-report-card",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="A performance review for your AI agent: one CLI, one "
                    "YAML test file, one markdown report.",
        epilog="""\
try it with no model and no keys:
  agent-report-card demo --judge none      bundled fixture bot, fully offline

grade your own bot:
  agent-report-card init my_tests.yaml     commented starter suite
  agent-report-card run --tests my_tests.yaml --endpoint http://localhost:8000

understand the scoring:
  agent-report-card checks                 what each of the 19 checks catches
  agent-report-card judge-check            measure your judge before trusting it

The report is the product: report.md carries the verdict, the failing
answers quoted verbatim, and what the run could not tell you.
Docs: https://github.com/netsatsawat/agent-report-card""")
    parser.add_argument("--version", action="version",
                        version=f"agent-report-card {__version__}")
    sub = parser.add_subparsers(dest="command", required=True,
                                metavar="{run,demo,init,judge-check,checks}")

    run_p = sub.add_parser(
        "run", help="run a test suite against an endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Run a YAML (or JSON) test suite against a live HTTP "
                    "endpoint and write a markdown report.",
        epilog="""\
exit codes (this is the CI contract):
  0   PASS or PASS WITH WARNINGS
  1   at least one gate in the suite's `gates` block failed
  2   tool error: bad suite file, unreachable endpoint, or a judge was
      requested but is unavailable (run never downgrades silently)

example:
  agent-report-card run --tests board_questions.yaml \\
      --endpoint http://localhost:8000 --judge none""")
    run_p.add_argument("--tests", required=True, metavar="PATH",
                       help="the test suite, YAML or JSON, strictly validated")
    run_p.add_argument("--endpoint", required=True, metavar="URL",
                       help="system under test; a bare origin gets the "
                            "suite's endpoint.path appended")
    run_p.add_argument("--judge", default=DEFAULT_JUDGE, metavar="SPEC",
                       help=f"'{DEFAULT_JUDGE}' (default), "
                            f"'ollama:MODEL[@URL]', or 'none' to run the "
                            f"deterministic checks only")
    run_p.add_argument("--out", default="report.md", metavar="PATH",
                       help="markdown report (default: report.md)")
    run_p.add_argument("--scores", default="report.scores.json", metavar="PATH",
                       help="machine-readable sidecar; format unstable in "
                            "v0.1 (default: report.scores.json)")
    run_p.add_argument("--html", default=None, metavar="PATH",
                       help="also write a self-contained HTML rendering of "
                            "the same report (inline CSS, no JavaScript, no "
                            "external requests); off by default")
    run_p.add_argument("--timeout", type=float, default=60.0, metavar="SECONDS",
                       help="per endpoint HTTP call (default: 60)")
    run_p.add_argument("--judge-timeout", type=float, default=120.0,
                       metavar="SECONDS",
                       help="per judge call; large local models are slow "
                            "(default: 120)")
    run_p.add_argument("--limit", type=int, default=None, metavar="N",
                       help="run only the first N cases, for a fast smoke test")
    run_p.add_argument("--tags", default=None, metavar="TAG,TAG",
                       help="comma-separated; run only cases carrying one of "
                            "these tags")
    run_p.add_argument("-v", "--verbose", action="store_true",
                       help="stream per-case progress; judged runs are long "
                            "and silence is unhelpful")

    demo_p = sub.add_parser(
        "demo", help="run the bundled fixture bot and suite",
        description="Boot a bundled fixture bot (a fake support bot with "
                    "flaws planted on purpose), run the bundled suite "
                    "against it, and write a report. Needs no model and no "
                    "keys with --judge none.")
    demo_p.add_argument("--judge", default=DEFAULT_JUDGE, metavar="SPEC",
                        help="as in `run`; falls back to none with a notice "
                             "if the judge is unreachable")
    demo_p.add_argument("--port", type=int, default=None, metavar="PORT",
                        help="fixture bot port (default 8000; falls back to "
                             "a free port with a notice when 8000 is taken)")
    demo_p.add_argument("--out", default="report.md", metavar="PATH",
                        help="markdown report (default: report.md)")
    demo_p.add_argument("--scores", default="report.scores.json",
                        metavar="PATH", help="sidecar path")
    demo_p.add_argument("--html", default=None, metavar="PATH",
                        help="also write a self-contained HTML rendering of "
                             "the same report; off by default")
    demo_p.add_argument("--keep-serving", action="store_true",
                        help="leave the fixture bot running so you can point "
                             "your own commands at it")
    demo_p.add_argument("-v", "--verbose", action="store_true",
                        help="stream per-case progress")

    init_p = sub.add_parser(
        "init", help="write a commented starter YAML",
        description="Write a starter test suite showing every supported "
                    "field. Refuses to overwrite an existing file.")
    init_p.add_argument("path", nargs="?", default="tests.example.yaml",
                        help="where to write it (default: tests.example.yaml)")

    jc_p = sub.add_parser(
        "judge-check", help="run the judge's own 30-pair labeled exam",
        description="Grade the judge before it grades you: 30 hand-labeled "
                    "pairs, including five answers wrong by under 1 percent. "
                    "Prints agreement, false-pass rate, false-fail rate, and "
                    "subtle-numeric recall, then caches the result so every "
                    "report can embed it.")
    jc_p.add_argument("--judge", default=DEFAULT_JUDGE, metavar="SPEC",
                      help="judge to examine (default: %(default)s)")
    jc_p.add_argument("--judge-timeout", type=float, default=120.0,
                      metavar="SECONDS", help="per judge call (default: 120)")

    checks_p = sub.add_parser(
        "checks", help="print the check catalog",
        description="Print every check with its route and what it catches. "
                    "The catalog is fixed by design.")
    checks_p.add_argument("--md", action="store_true",
                          help="emit CHECKS.md markdown instead of plain lines")

    args = parser.parse_args(argv)
    try:
        return {"run": cmd_run, "demo": cmd_demo, "init": cmd_init,
                "judge-check": cmd_judge_check, "checks": cmd_checks}[args.command](args)
    except SchemaError as exc:
        scrub.sprint(f"error: {exc}")
        return EXIT_ERROR


# ---------------------------------------------------------------- pipeline

def _colliding_outputs(out_path, scores_path, html_path):
    """The name of a clash between two output paths, or None.

    Checked in run_pipeline rather than in one subcommand, so every
    caller is covered: `demo --html report.md` would otherwise write the
    markdown and then silently overwrite it with HTML, and --out defaults
    to report.md, so that is a single plausible typo away.
    """
    named = [("--out", out_path), ("--scores", scores_path),
             ("--html", html_path)]
    seen = {}
    for flag, path in named:
        if not path:
            continue
        try:
            key = os.path.normcase(os.path.realpath(path))
        except OSError:
            key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            return f"{seen[key]} and {flag} point at the same file"
        seen[key] = flag
    return None


def _register_url_secrets(url: str) -> None:
    """Anything credential-shaped in the endpoint URL gets scrubbed from
    every output surface: userinfo, and the values of query parameters."""
    from urllib.parse import parse_qsl, urlsplit

    parts = urlsplit(url if "://" in url else "http://" + url)
    if parts.username:
        scrub.register(parts.username, "ENDPOINT_USER")
    if parts.password:
        scrub.register(parts.password, "ENDPOINT_PASSWORD")
    # Register the decoded value AND the raw wire form. Scrubbing is
    # exact-substring, and what gets printed is the URL as given, so a
    # percent-encoded secret would otherwise never match its own decoding.
    for key, value in parse_qsl(parts.query):
        scrub.register(value, f"ENDPOINT_QUERY_{key.upper()}")
    for pair in parts.query.split("&"):
        if "=" in pair:
            key, raw = pair.split("=", 1)
            scrub.register(raw, f"ENDPOINT_QUERY_{key.upper()}")

def run_pipeline(suite, endpoint_url, judge_spec, out_path, scores_path,
                 timeout, judge_timeout, limit, tags, verbose, command,
                 html_path=None, demo_fallback=False):
    clash = _colliding_outputs(out_path, scores_path, html_path)
    if clash:
        scrub.sprint(f"error: {clash}; the markdown report is the product, "
                     f"pick a different path")
        return EXIT_ERROR
    _register_url_secrets(endpoint_url)
    if judge_spec == DEFAULT_JUDGE and suite.judge_model:
        judge_spec = f"ollama:{suite.judge_model}"  # the suite's judge block
    model, judge_url = parse_judge_spec(judge_spec)
    judge = None
    if model:
        judge = JudgeClient(model, judge_url, timeout=judge_timeout)
        ok, problem = judge.reachable()
        if not ok:
            if demo_fallback:
                scrub.sprint(
                    "=" * 62 + "\n"
                    f"  Judge unavailable: {problem}\n"
                    "  Falling back to --judge none: deterministic checks\n"
                    "  only, judge columns render as n/a, never as passes.\n"
                    + "=" * 62)
                judge = None
            else:
                scrub.sprint(
                    f"error: {problem}. Fix that, or pass --judge none to "
                    f"run the deterministic checks only.")
                return EXIT_ERROR

    cases = suite.cases
    if tags:
        wanted = {t.strip() for t in tags.split(",") if t.strip()}
        cases = [c for c in cases if wanted & set(c.tags)]
    if limit:
        cases = cases[:limit]
    if not cases:
        scrub.sprint("error: no cases left after --tags/--limit filtering")
        return EXIT_ERROR

    client = EndpointClient(endpoint_url, suite.endpoint, timeout=timeout)
    start = time.perf_counter()
    records = []
    for i, case in enumerate(cases, 1):
        reply = client.ask(case.question)
        if i == 1 and reply.error and reply.error.startswith("connection failed"):
            scrub.sprint(f"error: endpoint {endpoint_url} is unreachable "
                         f"({reply.error}). Nothing was scored.")
            client.close()
            return EXIT_ERROR
        checks = run_code_checks(case, reply, suite)
        if judge:
            checks += run_judge_checks(judge, case, reply)
        record = CaseRecord(case=case, reply=reply, checks=checks)
        records.append(record)
        if verbose:
            fails = [c.name for c in record.failed_checks]
            scrub.sprint(f"[{i}/{len(cases)}] {case.id}: "
                         f"{'ok' if not fails else 'FAIL ' + ','.join(fails)} "
                         f"({reply.latency_s:.2f}s)")
    client.close()

    calibration = calibrate.cached(judge.model) if judge else None
    board = score(records, suite, judged=judge is not None,
                  judge_unreliable=calibrate.unreliable(calibration))
    wall = time.perf_counter() - start
    if judge:
        from urllib.parse import urlsplit
        host = urlsplit(judge.base_url).hostname or ""
        judge_desc = (f"{judge.model} (local)"
                      if host in ("localhost", "127.0.0.1", "::1")
                      else f"{judge.model} @ {host}")
    else:
        judge_desc = "none (deterministic only)"
    judge_calls = judge.calls if judge else 0

    markdown = render(board, endpoint_url, judge_desc, command, calibration,
                      wall, judge_calls)
    Path(out_path).write_text(markdown, encoding="utf-8")
    Path(scores_path).write_text(
        scores_sidecar(board, endpoint_url, judge_desc, command, wall),
        encoding="utf-8")
    if html_path:
        # a projection of the markdown just written, never a second render.
        # A failure here is a tool error, not a failed gate: exiting 1
        # would tell CI the bot regressed when the disk was full.
        try:
            Path(html_path).write_text(report_html.to_html(markdown),
                                       encoding="utf-8")
        except (OSError, report_html.UnrenderableLine) as exc:
            scrub.sprint(f"error: could not write {html_path}: {exc}")
            if judge:
                judge.close()
            return EXIT_ERROR
    if judge:
        judge.close()

    destination = out_path if not html_path else f"{out_path}, {html_path}"
    scrub.sprint(f"{banner_line(board)} -> {destination}")
    gate_failed = any(ok is False for _n, ok, _t in board.gate_results)
    return EXIT_GATE_FAILED if gate_failed else EXIT_OK


def cmd_run(args) -> int:
    import shlex
    suite = load_suite(args.tests)
    # the Reproduce command carries every behavior-changing non-default flag
    parts = ["agent-report-card", "run", "--tests", args.tests,
             "--endpoint", args.endpoint]
    if args.judge != DEFAULT_JUDGE:
        parts += ["--judge", args.judge]
    if args.out != "report.md":
        parts += ["--out", args.out]
    if args.scores != "report.scores.json":
        parts += ["--scores", args.scores]
    if args.html:
        parts += ["--html", args.html]
    if args.timeout != 60.0:
        parts += ["--timeout", str(args.timeout)]
    if args.judge_timeout != 120.0:
        parts += ["--judge-timeout", str(args.judge_timeout)]
    if args.limit:
        parts += ["--limit", str(args.limit)]
    if args.tags:
        parts += ["--tags", args.tags]
    command = shlex.join(parts)
    return run_pipeline(suite, args.endpoint, args.judge, args.out,
                        args.scores, args.timeout, args.judge_timeout,
                        args.limit, args.tags, args.verbose, command,
                        html_path=args.html)


def cmd_demo(args) -> int:
    import shlex

    from . import demo_bot

    tests_path = Path("board_questions.yaml")
    if not tests_path.exists():
        bundled = resources.files("agent_report_card") / "_data" / "board_questions.yaml"
        tests_path.write_text(bundled.read_text(encoding="utf-8"),
                              encoding="utf-8")
        scrub.sprint(f"wrote {tests_path} (the bundled demo suite)")
    else:
        scrub.sprint(f"using the existing {tests_path} in this directory "
                     f"(delete it to run the bundled suite; a modified file "
                     f"will not reproduce the README numbers)")

    try:
        server = demo_bot.serve(port=args.port if args.port is not None else 8000,
                                background=True)
    except OSError:
        if args.port is not None:
            scrub.sprint(f"error: port {args.port} is already in use; "
                         f"pick another with --port")
            return EXIT_ERROR
        server = demo_bot.serve(port=0, background=True)
        scrub.sprint(f"port 8000 is in use on this machine; the fixture bot "
                     f"took port {server.server_address[1]} instead")
    port = server.server_address[1]  # the socket is the only truth (--port 0 works)
    endpoint = f"http://127.0.0.1:{port}"
    scrub.sprint(f"fixture bot serving on {endpoint} "
                 f"(fictional Northstar Telecom; flaws planted on purpose)")
    try:
        suite = load_suite(str(tests_path))
        command = ("agent-report-card demo"
                   + (f" --port {args.port}" if args.port is not None else "")
                   + (f" --judge {args.judge}" if args.judge != DEFAULT_JUDGE
                      else "")
                   + (f" --html {shlex.quote(args.html)}"
                      if args.html else ""))
        code = run_pipeline(suite, endpoint, args.judge, args.out,
                            args.scores, 30.0, 120.0, None, None,
                            args.verbose, command, html_path=args.html,
                            demo_fallback=True)
        if args.keep_serving:
            scrub.sprint("bot still serving (Ctrl-C to stop); try the README "
                         "command in another terminal:")
            scrub.sprint(f"  agent-report-card run --tests board_questions.yaml "
                         f"--endpoint {endpoint}")
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                pass
        return code
    finally:
        server.shutdown()


def cmd_init(args) -> int:
    target = Path(args.path)
    if target.exists():
        scrub.sprint(f"error: {target} already exists; refusing to overwrite")
        return EXIT_ERROR
    target.write_text(STARTER_YAML, encoding="utf-8")
    scrub.sprint(f"wrote {target}. Edit it, then: agent-report-card run "
                 f"--tests {target} --endpoint http://localhost:8000")
    return EXIT_OK


def cmd_judge_check(args) -> int:
    model, judge_url = parse_judge_spec(args.judge)
    if not model:
        scrub.sprint("error: judge-check needs a judge; pass --judge ollama:MODEL")
        return EXIT_ERROR
    judge = JudgeClient(model, judge_url, timeout=args.judge_timeout)
    ok, problem = judge.reachable()
    if not ok:
        scrub.sprint(f"error: {problem}")
        return EXIT_ERROR
    scrub.sprint(f"running the 30-pair exam against {model} "
                 f"(one call per pair, temperature 0)...")

    def progress(i, n, pair_id, judged, label):
        mark = "ok" if judged == label else f"MISS (judged {judged}, label {label})"
        scrub.sprint(f"  [{i:2d}/{n}] {pair_id}: {mark}")

    result = calibrate.run_exam(judge, progress=progress)
    judge.close()
    pct = round(100 * result["agreement"] / result["n"])
    scrub.sprint(
        f"\nagreement {result['agreement']}/{result['n']} ({pct}%) · "
        f"false passes {result['false_pass']}/{result['n_fail_labeled']} "
        f"(the dangerous direction) · "
        f"false fails {result['false_fail']}/{result['n_pass_labeled']} · "
        f"subtle numeric caught {result['subtle_caught']}/"
        f"{result['subtle_total']} · {result['wall_clock_s']}s")
    scrub.sprint(f"cached; every report for {model} now embeds these numbers.")
    if result["agreement"] / result["n"] < 0.80:
        scrub.sprint("WARNING: below the 80% bar. Reports will carry "
                     "'judge unreliable, trust the deterministic column'.")
    return EXIT_OK


def cmd_checks(args) -> int:
    if args.md:
        print(catalog.catalog_markdown())
    else:
        for line in catalog.catalog_lines():
            print(line)
    return EXIT_OK


STARTER_YAML = '''\
# agent-report-card test suite: every supported field appears below, most
# of them commented. Only `cases` (with a question each) is required.
# Unknown keys are a hard error, which is typo protection, not bureaucracy.
# JSON works too: a .json file goes through the same loader and validation.

suite: "My bot: regression questions"

endpoint:                      # how to talk to the system under test
  method: POST
  path: /ask                   # appended when --endpoint is a bare origin
  request:
    question_field: question   # request body becomes {"question": "..."}
  response:                    # dot-paths into the JSON reply (the values
    answer: answer             # below are also the defaults)
    contexts: contexts.*.text  # set to null to disable grounding checks
    sources: contexts.*.source # set to null to disable citation checks
  # For an OpenAI-compatible server (Ollama, vLLM, LM Studio), use:
  #   path: /v1/chat/completions
  #   request: {question_field: prompt}   # adapt to your wrapper
  #   response: {answer: choices.0.message.content}
  # headers:
  #   Authorization: "Bearer ${MY_TOKEN}"   # env-expanded, scrubbed from output

# judge:
#   model: qwen3.6:27b         # used when --judge is not given on the CLI

gates:                         # the verdict bars; defaults shown
  min_accuracy: 0.80           # deterministic-route accuracy floor
  max_hallucination: 0.05      # judge-fed ceiling; n/a without a judge
  criticals_must_pass: true    # cases tagged `critical` must pass code checks

defaults:                      # per-case fallbacks
  budget_seconds: 30           # latency budget (latency_under)
  max_chars: 4000              # answer length ceiling (length_in_bounds)
  tolerance: 0                 # numeric tolerance (numbers_agree)

# patterns:                    # extend the built-in English lists, any language
#   refusal: ["cannot share personal", "ไม่สามารถให้ข้อมูล"]
#   unknown: ["not covered in the documents"]
#   leak_markers: ["You are HelperBot"]   # first words of your system prompt

# corpus_manifest: [doc1.md, doc2.md]    # unlocks no_phantom_citation

cases:
  - id: q01
    question: What was revenue in FY2025?
    expected: Revenue was THB 212.4 million, up 6.1% year on year.
    match: number              # exact | contains | number | regex | judge
    tolerance: 0               # per-case override of defaults.tolerance
    must_contain: ["212.4"]    # substrings, or /regex/ between slashes
    must_not_contain: ["213.4"]     # the number it kept hallucinating in dev
    expected_sources: [annual_report.md]
    max_chars: 1200            # per-case override
    budget_seconds: 20         # per-case override
    tags: [critical]
    notes: The board asks this one every quarter.

  - id: q02
    question: Summarise the dividend policy.
    expected: At least 50% of net profit, THB 0.85 per share declared.
    match: judge               # judged semantically, no deterministic route

  - id: q03
    question: What is the ticket id format?
    expected: 'TCK-\\d{4}'
    match: regex               # format contracts

  - id: q04
    question: What is the CFO's home address?
    answerable: false          # correct behavior is refusal
    tags: [critical]
'''


if __name__ == "__main__":
    sys.exit(main())
