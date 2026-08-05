"""The check catalog: the single source of truth.

The `checks` subcommand, the generated CHECKS.md, and the report's
check-by-check table all render from this table, so code and docs cannot
drift. The catalog is fixed by design; adding a check means arguing one in
by issue, or editing this small file.
"""

# (name, route, what it catches)
CHECKS = [
    ("answered", "code",
     "Dead endpoints, empty replies, and unmappable responses, scored as failures instead of crashes"),
    ("exact_match", "code",
     "Regressions on short canonical answers"),
    ("contains_all", "code",
     "The key fact simply missing from the answer"),
    ("contains_none", "code",
     "Known-wrong figures and forbidden claims: the cheapest hallucination tripwire"),
    ("numbers_agree", "code",
     "Right-sounding answers carrying wrong numbers"),
    ("regex_match", "code",
     "Format contracts such as dates, ids, and codes"),
    ("cites_expected_source", "code",
     "The right answer attributed to the wrong place, or to nothing"),
    ("no_phantom_citation", "code",
     "Citations to documents that do not exist in your corpus"),
    ("retrieval_hit", "code",
     "Localization: whether a wrong answer is a retrieval fault or a generation fault"),
    ("no_error_leak", "code",
     "Stack traces and plumbing served to users as answers"),
    ("refuses_when_required", "code",
     "The bot answering a question it must decline"),
    ("answers_when_it_should", "code",
     "Over-refusal on legitimate questions"),
    ("length_in_bounds", "code",
     "Empty replies and runaway rambles"),
    ("latency_under", "code",
     "Answers too slow for the seat they are meant to fill"),
    ("judge_correct", "judge",
     "Paraphrased-but-wrong answers that string matching cannot see"),
    ("judge_grounded", "judge",
     "Claims the retrieved passages do not support: the hallucination number"),
    ("judge_refusal", "judge",
     "Refusals that answer anyway in polite words"),
    ("judge_citation_support", "judge",
     "Decorative citations that do not support the sentence citing them"),
    ("judge_on_topic", "judge",
     "Dodging and topic drift"),
]

CODE_CHECKS = [c for c in CHECKS if c[1] == "code"]
JUDGE_CHECKS = [c for c in CHECKS if c[1] == "judge"]
WHAT = {name: what for name, _route, what in CHECKS}
ROUTE = {name: route for name, route, _what in CHECKS}

# Checks whose pass/fail participates in the deterministic correctness verdict.
CORRECTNESS_CODE = ("exact_match", "contains_all", "contains_none",
                    "numbers_agree", "regex_match")

# Severity order for the report's failure section (lower sorts first).
SEVERITY = {
    "answered": 0, "no_error_leak": 0,                      # plumbing
    "exact_match": 1, "contains_all": 1, "contains_none": 1,
    "numbers_agree": 1, "regex_match": 1, "judge_correct": 1,  # wrong fact
    "judge_grounded": 2, "no_phantom_citation": 2,          # hallucination
    "cites_expected_source": 3, "judge_citation_support": 3, "retrieval_hit": 3,
    "refuses_when_required": 3, "answers_when_it_should": 3, "judge_refusal": 3,
    "length_in_bounds": 4, "latency_under": 4, "judge_on_topic": 4,  # style
}


def catalog_lines():
    """One line per check: name, route, what it catches."""
    return [f"{name:<24} {route:<6} {what}" for name, route, what in CHECKS]


def catalog_markdown():
    """CHECKS.md content, generated."""
    lines = [
        "# The check catalog",
        "",
        "Generated from `agent_report_card/catalog.py` by `agent-report-card checks --md`.",
        "Do not edit by hand. The catalog is fixed by design: adding a check means",
        "arguing one in by issue, or editing the small source.",
        "",
        f"{len(CODE_CHECKS)} deterministic checks and {len(JUDGE_CHECKS)} judge checks.",
        "Every check is binary per case (pass / fail / n/a), and the report always",
        "shows n/a rows with their reason instead of hiding them.",
        "",
        "| check | route | what it catches |",
        "|---|---|---|",
    ]
    for name, route, what in CHECKS:
        lines.append(f"| `{name}` | {route} | {what} |")
    lines.append("")
    return "\n".join(lines)
