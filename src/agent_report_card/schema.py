"""Suite loading and strict validation.

Unknown keys, duplicate ids, contradictory fields, and unset ``${VAR}``
references fail fast with the line number, the case id where there is one,
and a one-line fix. All files are UTF-8.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field

import yaml

LINE_KEY = "__line__"


class SchemaError(ValueError):
    pass


class _LineLoader(yaml.SafeLoader):
    """SafeLoader that stamps every mapping with its 1-based line number."""


def _construct_mapping(loader, node, deep=False):
    mapping = yaml.SafeLoader.construct_mapping(loader, node, deep=deep)
    mapping[LINE_KEY] = node.start_mark.line + 1
    return mapping


_LineLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


TOP_KEYS = {"suite", "endpoint", "judge", "gates", "patterns",
            "corpus_manifest", "defaults", "cases"}
ENDPOINT_KEYS = {"method", "path", "request", "response", "headers"}
REQUEST_KEYS = {"question_field"}
RESPONSE_KEYS = {"answer", "contexts", "sources"}
GATE_KEYS = {"min_accuracy", "max_hallucination", "criticals_must_pass"}
PATTERN_KEYS = {"refusal", "unknown", "leak_markers"}
DEFAULTS_KEYS = {"budget_seconds", "max_chars", "tolerance"}
CASE_KEYS = {"id", "question", "expected", "match", "tolerance",
             "must_contain", "must_not_contain", "expected_sources",
             "answerable", "max_chars", "budget_seconds", "tags", "notes"}
MATCH_VALUES = {"exact", "contains", "number", "regex", "judge"}


@dataclass
class EndpointCfg:
    """Defaults match the README's documented default contract exactly:
    contexts and sources map from {"contexts": [{"text", "source"}, ...]}
    out of the box; endpoints without those fields simply yield empty
    lists and the dependent checks render n/a."""
    method: str = "POST"
    path: str = "/ask"
    question_field: str = "question"
    answer_path: str = "answer"
    contexts_path: str | None = "contexts.*.text"
    sources_path: str | None = "contexts.*.source"
    headers: dict = field(default_factory=dict)          # raw, ${VAR} unexpanded
    expanded_headers: dict = field(default_factory=dict)  # ready to send


@dataclass
class Gates:
    min_accuracy: float = 0.80
    max_hallucination: float = 0.05
    criticals_must_pass: bool = True
    explicit: bool = False  # True when the suite set any gate itself


@dataclass
class Patterns:
    refusal: list = field(default_factory=list)
    unknown: list = field(default_factory=list)
    leak_markers: list = field(default_factory=list)


@dataclass
class Case:
    id: str
    question: str
    line: int
    expected: str | None = None
    match: str | None = None
    tolerance: float = 0.0
    must_contain: list = field(default_factory=list)
    must_not_contain: list = field(default_factory=list)
    expected_sources: list = field(default_factory=list)
    answerable: bool = True
    max_chars: int = 4000
    budget_seconds: float | None = None
    tags: list = field(default_factory=list)
    notes: str | None = None

    @property
    def critical(self) -> bool:
        return "critical" in self.tags


@dataclass
class Suite:
    name: str
    path: str
    sha256: str
    endpoint: EndpointCfg
    judge_model: str | None
    gates: Gates
    patterns: Patterns
    corpus_manifest: list
    cases: list


def _err(line, case_id, problem, fix):
    where = f"line {line}" if line else "top level"
    who = f", case '{case_id}'" if case_id else ""
    raise SchemaError(f"{where}{who}: {problem}. Fix: {fix}")


def _check_keys(mapping, allowed, line, case_id, context):
    for key in mapping:
        if key == LINE_KEY:
            continue
        if key not in allowed:
            _err(mapping.get(LINE_KEY, line), case_id,
                 f"unknown key '{key}' in {context}",
                 f"allowed keys are: {', '.join(sorted(allowed))}")


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def expand_headers(raw: dict, line: int) -> dict:
    """Expand ${VAR} references; unset vars fail fast, values are registered
    for scrubbing. Only the variable NAME ever appears in an error."""
    from . import scrub

    expanded = {}
    for key, value in raw.items():
        if key == LINE_KEY:
            continue
        text = str(value)
        for var in re.findall(r"\$\{(\w+)\}", text):
            env = os.environ.get(var)
            if env is None:
                _err(line, None,
                     f"header '{key}' references ${{{var}}} but the "
                     f"environment variable is not set",
                     f"export {var}=... before running, or remove the reference")
            scrub.register(env, var)
            text = text.replace("${" + var + "}", env)
        expanded[key] = text
    return expanded


def load_suite(path: str) -> Suite:
    with open(path, encoding="utf-8") as fh:
        raw_text = fh.read()
    sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    try:
        data = yaml.load(raw_text, Loader=_LineLoader)
    except yaml.YAMLError as exc:
        raise SchemaError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise SchemaError(f"{path}: top level must be a mapping with a 'cases' list")

    _check_keys(data, TOP_KEYS, 1, None, "the suite")

    # endpoint
    ep_raw = data.get("endpoint") or {}
    _check_keys(ep_raw, ENDPOINT_KEYS, ep_raw.get(LINE_KEY, 1), None, "endpoint")
    req = ep_raw.get("request") or {}
    _check_keys(req, REQUEST_KEYS, req.get(LINE_KEY, 1), None, "endpoint.request")
    resp = ep_raw.get("response") or {}
    _check_keys(resp, RESPONSE_KEYS, resp.get(LINE_KEY, 1), None, "endpoint.response")
    headers_raw = ep_raw.get("headers") or {}
    ep_path = str(ep_raw.get("path", "/ask"))
    if not ep_path.startswith("/"):
        _err(ep_raw.get(LINE_KEY, 1), None,
             f"endpoint.path {ep_path!r} must start with '/'",
             "a path may never carry a host, userinfo, or scheme; the host "
             "comes only from --endpoint")
    endpoint = EndpointCfg(
        method=str(ep_raw.get("method", "POST")).upper(),
        path=ep_path,
        question_field=str(req.get("question_field", "question")),
        answer_path=str(resp.get("answer", "answer")),
        # absent key -> the documented default contract; explicit null -> off
        contexts_path=resp.get("contexts", "contexts.*.text"),
        sources_path=resp.get("sources", "contexts.*.source"),
        headers={k: v for k, v in headers_raw.items() if k != LINE_KEY},
    )
    endpoint.expanded_headers = expand_headers(
        headers_raw, headers_raw.get(LINE_KEY, ep_raw.get(LINE_KEY, 1)))

    # gates
    gates_raw = data.get("gates")
    gates = Gates()
    if gates_raw:
        _check_keys(gates_raw, GATE_KEYS, gates_raw.get(LINE_KEY, 1), None, "gates")
        gates = Gates(
            min_accuracy=float(gates_raw.get("min_accuracy", gates.min_accuracy)),
            max_hallucination=float(
                gates_raw.get("max_hallucination", gates.max_hallucination)),
            criticals_must_pass=bool(
                gates_raw.get("criticals_must_pass", gates.criticals_must_pass)),
            explicit=True,
        )

    # patterns
    pat_raw = data.get("patterns") or {}
    _check_keys(pat_raw, PATTERN_KEYS, pat_raw.get(LINE_KEY, 1), None, "patterns")
    patterns = Patterns(
        refusal=_as_list(pat_raw.get("refusal")),
        unknown=_as_list(pat_raw.get("unknown")),
        leak_markers=_as_list(pat_raw.get("leak_markers")),
    )

    # defaults
    def_raw = data.get("defaults") or {}
    _check_keys(def_raw, DEFAULTS_KEYS, def_raw.get(LINE_KEY, 1), None, "defaults")
    d_budget = def_raw.get("budget_seconds")
    d_max_chars = int(def_raw.get("max_chars", 4000))
    d_tol = float(def_raw.get("tolerance", 0.0))

    # judge block
    judge_raw = data.get("judge") or {}
    judge_model = None
    if isinstance(judge_raw, dict):
        _check_keys(judge_raw, {"model"}, judge_raw.get(LINE_KEY, 1), None, "judge")
        judge_model = judge_raw.get("model")

    # cases
    cases_raw = data.get("cases")
    if not cases_raw or not isinstance(cases_raw, list):
        _err(data.get(LINE_KEY, 1), None, "no 'cases' list found",
             "add a cases: list with at least one {id, question} entry")
    seen_ids = {}
    cases = []
    for entry in cases_raw:
        if not isinstance(entry, dict):
            _err(data.get(LINE_KEY, 1), None, "a cases entry is not a mapping",
                 "each case is a mapping with at least a question")
        line = entry.get(LINE_KEY, 0)
        _check_keys(entry, CASE_KEYS, line, entry.get("id"), "a case")
        cid = str(entry.get("id") or f"case-{len(cases) + 1:02d}")
        if cid in seen_ids:
            _err(line, cid, f"duplicate case id (first used on line {seen_ids[cid]})",
                 "give every case a unique id")
        seen_ids[cid] = line
        question = entry.get("question")
        if not question or not str(question).strip():
            _err(line, cid, "case has no question", "add question: ...")
        expected = entry.get("expected")
        match = entry.get("match")
        answerable = bool(entry.get("answerable", True))
        if match is not None and match not in MATCH_VALUES:
            _err(line, cid, f"match '{match}' is not one of {sorted(MATCH_VALUES)}",
                 "pick one, or omit match")
        if match in {"exact", "number", "regex", "judge"} and expected is None:
            _err(line, cid, f"match: {match} needs an expected answer",
                 "add expected: ..., or drop match")
        if match == "contains" and not entry.get("must_contain"):
            _err(line, cid, "match: contains needs a must_contain list",
                 "add must_contain: [...] (an expected answer alone is "
                 "judged semantically; use match: judge for that)")
        if match == "regex":
            try:
                re.compile(str(expected))
            except re.error as exc:
                _err(line, cid, f"expected is not a valid regex ({exc})",
                     "fix the pattern or use a different match mode")
        for field_name in ("must_contain", "must_not_contain"):
            for needle in _as_list(entry.get(field_name)):
                if len(needle) > 2 and needle.startswith("/") and needle.endswith("/"):
                    try:
                        re.compile(needle[1:-1])
                    except re.error as exc:
                        _err(line, cid,
                             f"{field_name} pattern {needle!r} is not a "
                             f"valid regex ({exc})", "fix the pattern")
        if not answerable and (expected is not None or entry.get("must_contain")):
            _err(line, cid,
                 "answerable: false contradicts expected/must_contain",
                 "an unanswerable case is judged on refusal only; "
                 "remove expected and must_contain")
        if expected is not None and match is None:
            match = "judge"  # default scoring route for an expected answer
        cases.append(Case(
            id=cid,
            question=str(question),
            line=line,
            expected=None if expected is None else str(expected),
            match=match,
            tolerance=float(entry.get("tolerance", d_tol)),
            must_contain=_as_list(entry.get("must_contain")),
            must_not_contain=_as_list(entry.get("must_not_contain")),
            expected_sources=_as_list(entry.get("expected_sources")),
            answerable=answerable,
            max_chars=int(entry.get("max_chars", d_max_chars)),
            budget_seconds=(float(entry["budget_seconds"])
                            if entry.get("budget_seconds") is not None
                            else (float(d_budget) if d_budget is not None else None)),
            tags=_as_list(entry.get("tags")),
            notes=entry.get("notes"),
        ))

    return Suite(
        name=str(data.get("suite") or os.path.basename(path)),
        path=path,
        sha256=sha,
        endpoint=endpoint,
        judge_model=judge_model,
        gates=gates,
        patterns=patterns,
        corpus_manifest=_as_list(data.get("corpus_manifest")),
        cases=cases,
    )
