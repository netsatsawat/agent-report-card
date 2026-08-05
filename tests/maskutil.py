"""The golden test's mask: the enumerated run-varying fields.

Masked, per the release criteria: the timestamp, the wall clock, and every
latency value (header cell, p50/p95 row, per-case appendix). Everything
else is pinned byte for byte.
"""

import re

_PATTERNS = [
    (re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC"), "<TIMESTAMP>"),
    (re.compile(r"\d+\.\d{2}s"), "<SECONDS>"),
]


def mask(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
