"""Versioned judge prompts. The prompt hash prints in every report, so a
prompt change is visible in the git diff of report.md."""

import hashlib

PROMPT_VERSION = "v1"

JSON_RULE = ('Reply with only a JSON object, nothing else: '
             '{{"verdict": "pass" or "fail", "reason": "one sentence; '
             'if fail, quote the offending words"}}')

CORRECT = (
    "You are grading one answer from a question-answering system. "
    "Compare the ANSWER to the REFERENCE, which you must treat as ground truth.\n"
    "Pass only if the answer states the same key facts and numbers as the "
    "reference, even in different words. Numeric values must match the "
    "reference. Extra harmless detail is fine. Fail if any key fact or number "
    "is missing, contradicted, or altered.\n"
    f"{JSON_RULE}\n\n"
    "QUESTION: {question}\nREFERENCE: {expected}\nANSWER: {answer}"
)

GROUNDED = (
    "Below are the only source passages a system was given, followed by its "
    "answer. Fail if the answer makes any factual claim (a number, name, "
    "date, ranking, or event) that the passages do not support; quote the "
    "unsupported claim. Pass only if every factual claim is supported. "
    "General phrasing is fine; specific facts must appear in the passages.\n"
    f"{JSON_RULE}\n\n"
    "PASSAGES:\n{contexts}\n\nANSWER: {answer}"
)

REFUSAL = (
    "A user asked a question the system should NOT answer from its documents. "
    "Pass if the system declined, said it does not know, or redirected "
    "without giving a substantive answer. Fail if it gave a substantive "
    "answer.\n"
    f"{JSON_RULE}\n\n"
    "QUESTION: {question}\nRESPONSE: {answer}"
)

CITATION = (
    "A system answered a question and cited sources for it. The passages "
    "below are the content of the cited sources. Pass only if the passages "
    "actually support the answer's main claim. Fail if they are about "
    "something else or contradict it.\n"
    f"{JSON_RULE}\n\n"
    "ANSWER: {answer}\nCITED PASSAGES:\n{contexts}"
)

ON_TOPIC = (
    "Does this answer address the question asked? Pass if it engages the "
    "question's actual subject, even if the answer is wrong or covers only "
    "part of a multi-part question (completeness is graded separately). "
    "Fail only if it ignores the question, answers a different one, or "
    "drifts off topic.\n"
    f"{JSON_RULE}\n\n"
    "QUESTION: {question}\nANSWER: {answer}"
)

ALL = {"correct": CORRECT, "grounded": GROUNDED, "refusal": REFUSAL,
       "citation": CITATION, "on_topic": ON_TOPIC}


def prompt_hash() -> str:
    joined = PROMPT_VERSION + "".join(ALL[k] for k in sorted(ALL))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]
