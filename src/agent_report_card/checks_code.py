"""The 14 deterministic checks, as pure functions over (case, reply, suite).

Normalization everywhere: NFC unicode, casefold, whitespace collapse, no
word-boundary assumptions (which is what keeps the substring checks
well-defined for Thai text; the caveat that substrings can cross Thai word
boundaries is stated in every report's limits). Number matching
canonicalizes thousands separators, currency prefixes, and percent forms;
it does no unit conversion and does not map Thai digits, both stated in
limits.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .client import EndpointReply
from .schema import Case, Suite

PASS, FAIL, NA = "pass", "fail", "na"
JUDGE_ERROR = "judge_error"

BUILTIN_REFUSAL = [
    "i can't", "i cannot", "cannot help", "can't help", "unable to",
    "not able to", "cannot provide", "can't provide", "cannot share",
    "can't share", "won't provide", "not appropriate", "i'm sorry",
    "i am sorry", "must decline", "cannot disclose", "can't disclose",
]
BUILTIN_UNKNOWN = [
    "not covered", "don't have information", "do not have information",
    "no information about", "outside the scope", "not in the documents",
    "i don't know", "i do not know",
]
BUILTIN_LEAK = [
    "traceback (most recent", "internal server error", "exception:",
    "as an ai language model", "<|", 'file "/',
    '"tool_calls"', '"function_call"', '"tool_call_id"',
]


@dataclass
class CheckResult:
    name: str
    status: str            # pass | fail | na | judge_error
    detail: str = ""       # evidence, quoted in the report on failure


_QUOTE_MAP = str.maketrans({"’": "'", "‘": "'",
                            "“": '"', "”": '"'})


def normalize(text: str) -> str:
    """NFC, casefold, whitespace collapse, and typographic quotes mapped to
    ASCII (LLMs routinely emit U+2019 in "can't", which must still match
    the refusal lexicon)."""
    text = unicodedata.normalize("NFC", str(text)).translate(_QUOTE_MAP)
    return re.sub(r"\s+", " ", text.casefold()).strip()


# Commas count only as real thousands grouping (so "options 5,6" is two
# numbers, not 56), and a '-' glued to a preceding digit or word is a range
# or identifier hyphen, not a minus sign (2019-2024, 2026-08-05, TCK-42).
_NUM_RE = re.compile(
    r"(?<![\d.])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\d.])-?\d+(?:\.\d+)?")


def extract_numbers(text: str) -> list[float]:
    """All numeric literals, commas stripped. THB1,500 yields 1500.0."""
    out = []
    for m in _NUM_RE.finditer(text):
        token = m.group(0)
        if token.startswith("-") and m.start() > 0 \
                and (text[m.start() - 1].isalnum()
                     or text[m.start() - 1] in ".,"):
            token = token[1:]
        out.append(float(token.replace(",", "")))
    return out


def _contains(haystack_norm: str, needle: str) -> bool:
    """Substring containment; /.../ needles are treated as regex.
    The haystack arrives normalized, so it is already casefolded; the regex
    is matched case-insensitively to suit, or an uppercase letter in the
    pattern could never match and a must_not_contain rule would silently
    fail open. The separate `match: regex` check runs against the raw
    answer instead; CHECKS.md states both.
    Patterns are validated at suite load time, so re.error here would be a
    bug; guard anyway rather than crash mid-run."""
    if len(needle) > 2 and needle.startswith("/") and needle.endswith("/"):
        try:
            return re.search(needle[1:-1], haystack_norm,
                             re.IGNORECASE) is not None
        except re.error:
            return False
    return normalize(needle) in haystack_norm


def _source_match(cited: str, declared: str) -> bool:
    """Case-insensitive substring in either direction, matching the
    normalization posture of every other check."""
    a, b = cited.casefold().strip(), declared.casefold().strip()
    return a in b or b in a


def _matches_any(answer_norm: str, phrases: list[str]) -> str | None:
    for phrase in phrases:
        if _contains(answer_norm, phrase):
            return phrase
    return None


def run_code_checks(case: Case, reply: EndpointReply, suite: Suite) -> list[CheckResult]:
    results = []
    answer_norm = normalize(reply.answer)
    refusal_lexicon = BUILTIN_REFUSAL + BUILTIN_UNKNOWN + \
        suite.patterns.refusal + suite.patterns.unknown

    # answered
    if reply.error:
        results.append(CheckResult("answered", FAIL, reply.error))
    elif not reply.answer.strip():
        results.append(CheckResult("answered", FAIL, "empty answer"))
    else:
        results.append(CheckResult("answered", PASS))
    responded = results[0].status == PASS

    def na_unless(condition, name, reason):
        """Append an n/a result and return False when a check does not apply."""
        if condition and responded:
            return True
        if not condition:
            results.append(CheckResult(name, NA, reason))
        else:
            results.append(CheckResult(name, NA, "no answer to check"))
        return False

    # exact_match
    if na_unless(case.match == "exact", "exact_match", "match is not 'exact'"):
        ok = answer_norm == normalize(case.expected)
        results.append(CheckResult("exact_match", PASS if ok else FAIL,
                                   "" if ok else "normalized answer differs from expected"))

    # contains_all
    if na_unless(bool(case.must_contain), "contains_all", "no must_contain listed"):
        missing = [s for s in case.must_contain if not _contains(answer_norm, s)]
        results.append(CheckResult(
            "contains_all", FAIL if missing else PASS,
            f"missing: {', '.join(repr(m) for m in missing)}" if missing else ""))

    # contains_none
    if na_unless(bool(case.must_not_contain), "contains_none", "no must_not_contain listed"):
        hit = _matches_any(answer_norm, case.must_not_contain)
        results.append(CheckResult(
            "contains_none", FAIL if hit else PASS,
            f"forbidden string present: {hit!r}" if hit else ""))

    # numbers_agree
    gold_numbers = extract_numbers(case.expected) if case.expected else []
    if na_unless(case.match == "number" and bool(gold_numbers),
                 "numbers_agree",
                 "match is not 'number'" if case.match != "number"
                 else "the expected answer contains no numbers to compare"):
        got = extract_numbers(reply.answer)
        missing = [g for g in gold_numbers
                   if not any(abs(a - g) <= case.tolerance for a in got)]
        results.append(CheckResult(
            "numbers_agree", FAIL if missing else PASS,
            (f"expected number(s) not found within tolerance "
             f"{case.tolerance}: {missing}") if missing else ""))

    # regex_match
    if na_unless(case.match == "regex", "regex_match", "match is not 'regex'"):
        ok = re.search(case.expected, reply.answer) is not None
        results.append(CheckResult("regex_match", PASS if ok else FAIL,
                                   "" if ok else f"pattern {case.expected!r} not found"))

    # cites_expected_source
    if na_unless(bool(case.expected_sources), "cites_expected_source",
                 "no expected_sources listed"):
        hit = any(_source_match(src, exp)
                  for exp in case.expected_sources for src in reply.sources)
        results.append(CheckResult(
            "cites_expected_source", PASS if hit else FAIL,
            "" if hit else (f"expected {case.expected_sources}, "
                            f"got {reply.sources or 'no sources'}")))

    # no_phantom_citation
    if na_unless(bool(suite.corpus_manifest) and bool(reply.sources),
                 "no_phantom_citation",
                 "no corpus_manifest" if not suite.corpus_manifest else "no sources returned"):
        phantoms = [s for s in reply.sources
                    if not any(_source_match(s, m) for m in suite.corpus_manifest)]
        results.append(CheckResult(
            "no_phantom_citation", FAIL if phantoms else PASS,
            f"cited source(s) not in the corpus manifest: {phantoms}" if phantoms else ""))

    # retrieval_hit
    needles = case.must_contain or []
    if na_unless(bool(reply.contexts) and (bool(needles) or bool(case.expected_sources)),
                 "retrieval_hit",
                 "no contexts returned" if not reply.contexts
                 else "nothing to look for (no must_contain or expected_sources)"):
        ctx_norm = normalize(" ".join(reply.contexts))
        hit = (any(_contains(ctx_norm, n) for n in needles)
               or any(_source_match(src, exp)
                      for exp in case.expected_sources for src in reply.sources)
               or any(normalize(exp) in ctx_norm
                      for exp in case.expected_sources))
        results.append(CheckResult(
            "retrieval_hit", PASS if hit else FAIL,
            "" if hit else "the required evidence never appeared in the retrieved contexts"))

    # no_error_leak
    if responded:
        leak_list = BUILTIN_LEAK + suite.patterns.leak_markers
        hit = _matches_any(answer_norm, leak_list)
        results.append(CheckResult(
            "no_error_leak", FAIL if hit else PASS,
            f"leak marker present: {hit!r}" if hit else ""))
    else:
        results.append(CheckResult("no_error_leak", NA, "no answer to check"))

    # refuses_when_required / answers_when_it_should
    refused = _matches_any(answer_norm, refusal_lexicon)
    if not case.answerable:
        if responded:
            results.append(CheckResult(
                "refuses_when_required", PASS if refused else FAIL,
                "" if refused else "answered a question it must decline"))
        else:
            results.append(CheckResult("refuses_when_required", NA, "no answer to check"))
        results.append(CheckResult("answers_when_it_should", NA,
                                   "case is answerable: false"))
    else:
        results.append(CheckResult("refuses_when_required", NA, "case is answerable"))
        if responded:
            results.append(CheckResult(
                "answers_when_it_should", FAIL if refused else PASS,
                f"refusal phrasing on an answerable question: {refused!r}"
                if refused else ""))
        else:
            results.append(CheckResult("answers_when_it_should", NA, "no answer to check"))

    # length_in_bounds
    if responded:
        n = len(reply.answer)
        ok = 1 <= n <= case.max_chars
        results.append(CheckResult(
            "length_in_bounds", PASS if ok else FAIL,
            "" if ok else f"{n} chars, limit {case.max_chars}"))
    else:
        results.append(CheckResult("length_in_bounds", NA, "no answer to check"))

    # latency_under
    if case.budget_seconds is None:
        results.append(CheckResult("latency_under", NA,
                                   "no budget_seconds set; latency recorded anyway"))
    else:
        ok = reply.latency_s <= case.budget_seconds
        results.append(CheckResult(
            "latency_under", PASS if ok else FAIL,
            "" if ok else f"{reply.latency_s:.2f}s against a "
                          f"{case.budget_seconds:.2f}s budget"))

    return results
