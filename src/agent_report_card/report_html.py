"""A self-contained HTML rendering of report.md.

This module is a projection of the markdown, never a second reading of the
scoreboard. Its only input is the string `report.render()` already
returned, so every character it emits derives from characters the markdown
already contained: the HTML cannot show a number, a verdict, a gate reason,
or a quoted answer that the markdown does not. Drift between the two
renderings is not policed by discipline, it is unrepresentable.

Two consequences worth stating, because both are load-bearing:

* This module imports nothing from the package. A test parses it and fails
  if that ever changes, because an import of the scoreboard would recreate
  the second surface this design exists to prevent. The verdict strings
  below are mirrored from `scoring` for the same reason, with a test
  asserting they stay in sync.
* `render()` scrubs secrets before returning, so escaping here always
  happens after scrubbing. That order matters: escaping first would break
  the exact-substring match for any secret containing `&`, `<`, or a
  quote, and the leak would then be invisible. This module must never
  call the scrubber itself.

The grammar accepted is exactly the closed set `report.py` emits. An
unrecognized line raises rather than being skipped: a silently dropped
line is the one way a projection can still lie.
"""

from __future__ import annotations

import base64
import hashlib
import re
from html import escape

# Mirrored from scoring.VERDICT_PASS / VERDICT_WARN / VERDICT_FAIL. Not
# imported, so this module stays a pure string transform; a test asserts
# the two definitions agree.
VERDICTS = {"PASS": "pass", "PASS WITH WARNINGS": "warn", "NOT READY": "fail"}

# The only raw HTML report.py emits, matched on full-line equality. A
# permissive "starts with <" rule would let a bot's answer smuggle a
# closing tag through the blockquote.
RAW_HTML = ("<details><summary>Per-case appendix</summary>", "</details>")

META_HEADERS = ["endpoint", "tests", "judge", "date", "wall clock", "tool"]

JUDGE_FLAG = " (judge-flagged)"


class UnrenderableLine(ValueError):
    """A markdown line the projection does not recognize."""


# --------------------------------------------------------------- inline

_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def _inline(text: str) -> str:
    """Escape first, then apply the report's own small marker vocabulary.

    Escaping before marker substitution is the whole point: by the time
    `**` or a backtick is interpreted, any markup the system under test
    produced is already inert text.
    """
    out = escape(text, quote=True)
    out = _CODE.sub(lambda m: f"<code>{m.group(1)}</code>", out)
    out = _BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", out)
    return out


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_delimiter(line: str) -> bool:
    return re.fullmatch(r"\|(?:\s*:?-+:?\s*\|)+", line.strip()) is not None


# --------------------------------------------------------------- blocks

def _banner(line: str) -> str | None:
    """The one bold line whose last segment is a verdict."""
    parts = line.strip().strip("*").split(" · ")
    state = VERDICTS.get(parts[-1].strip())
    if state is None:
        return None
    metrics = "".join(f"<span>{_inline(p)}</span>" for p in parts[:-1])
    return (f'<div class="banner banner--{state}">'
            f'<strong class="verdict">{escape(parts[-1].strip())}</strong>'
            f'<p class="metrics">{metrics}</p></div>')


def _meta_table(header: list[str], rows: list[list[str]]) -> str | None:
    """The header table as a grid, but only when it is exactly the shape
    expected. A ragged row means some cell contained a pipe, and zipping
    it against the headers would drop and mislabel values; fall back to
    the generic table, which is lossless."""
    if (header != META_HEADERS or len(rows) != 1
            or len(rows[0]) != len(header)):
        return None
    pairs = "".join(f"<dt>{escape(k)}</dt><dd>{_inline(v)}</dd>"
                    for k, v in zip(header, rows[0]))
    return f'<dl class="meta">{pairs}</dl>'


def _table(header: list[str], rows: list[list[str]]) -> str:
    meta = _meta_table(header, rows)
    if meta:
        return meta
    head = "".join(f"<th>{_inline(c)}</th>" for c in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
        for r in rows)
    return (f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def _heading3(text: str) -> str:
    """Failure headings carry an optional judge-flagged chip."""
    if text.endswith(JUDGE_FLAG):
        base = text[: -len(JUDGE_FLAG)]
        return (f"<h3>{_inline(base)}"
                f'<span class="tag">judge-flagged</span></h3>')
    return f"<h3>{_inline(text)}</h3>"


def _body(markdown: str) -> tuple[list[str], str, str]:
    """Returns (html blocks, document title, verdict state)."""
    lines = markdown.split("\n")
    out: list[str] = []
    title, state = "Report card", ""
    seen_h1 = False
    in_failures = False
    open_failure = False
    i = 0

    def close_failure():
        nonlocal open_failure
        if open_failure:
            out.append("</section>")
            open_failure = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped in RAW_HTML:
            close_failure()
            out.append(stripped)
            i += 1
            continue

        if stripped.startswith("# "):
            title = stripped[2:].strip()
            out.append(f"<h1>{_inline(title)}</h1>")
            seen_h1 = True
            i += 1
            continue

        if stripped.startswith("## "):
            close_failure()
            text = stripped[3:].strip()
            in_failures = text.startswith("Failures, quoted")
            out.append(f"<h2>{_inline(text)}</h2>")
            i += 1
            continue

        if stripped.startswith("### "):
            close_failure()
            if in_failures:
                out.append('<section class="failure">')
                open_failure = True
            out.append(_heading3(stripped[4:].strip()))
            i += 1
            continue

        if stripped.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>"
                       + escape("\n".join(block), quote=True)
                       + "</code></pre>")
            continue

        if stripped.startswith("|"):
            header = _cells(lines[i])
            i += 1
            if i < len(lines) and _is_delimiter(lines[i]):
                i += 1
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            out.append(_table(header, rows))
            continue

        if stripped.startswith("> "):
            quoted = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                # drop the marker and the single separator space only: the
                # rest is the answer's own indentation, which the stylesheet
                # preserves with pre-wrap because a quoted traceback is
                # evidence and its shape is part of it
                rest = lines[i].strip()[1:]
                quoted.append(rest[1:] if rest.startswith(" ") else rest)
                i += 1
            out.append("<blockquote>"
                       + escape("\n".join(quoted), quote=True)
                       + "</blockquote>")
            continue

        if stripped.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(f"<li>{_inline(lines[i].strip()[2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        if stripped.startswith("**") and seen_h1 and not state:
            banner = _banner(stripped)
            if banner:
                out.append(banner)
                state = stripped.strip("*").split(" · ")[-1].strip()
                i += 1
                continue

        if not stripped.startswith(("<", "#", "|", ">")):
            out.append(f"<p>{_inline(stripped)}</p>")
            i += 1
            continue

        raise UnrenderableLine(repr(line))

    close_failure()
    return out, title, state


# ----------------------------------------------------------------- page

CSS = """\
:root{--page:54rem;--measure:40rem;
--font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue","Noto Sans","Noto Sans Thai",Arial,sans-serif;
--mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
--ink:#1a1a19;--ink-soft:#41413f;--ink-faint:#6b6b68;
--rule:#e3e3e0;--rule-strong:#c2c2be;--bg:#fff;--bg-soft:#fafaf8;--bg-quote:#fafaf8}
@media (prefers-color-scheme:dark){:root{--ink:#e6edf3;--ink-soft:#b8c0c9;--ink-faint:#8b939c;
--rule:#2a2f36;--rule-strong:#454c55;--bg:#0d1117;--bg-soft:#151a21;--bg-quote:#151a21}}
html{font-size:100%;-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;padding:2.5rem 1.25rem 5rem;background:var(--bg);color:var(--ink);
font-family:var(--font);font-size:1rem;line-height:1.62;overflow-wrap:break-word}
.report{max-width:var(--page);margin:0 auto}
.report p,.report li{max-width:var(--measure)}
h1,h2,h3{line-height:1.25;font-weight:600}
h1{font-size:1.5rem;letter-spacing:-.012em;margin:0 0 1.25rem}
h2{font-size:1.15rem;margin:2.75rem 0 .9rem;padding-top:.85rem;border-top:1px solid var(--rule)}
h3{font-size:1rem;margin:1.6rem 0 .5rem;display:flex;flex-wrap:wrap;align-items:baseline;gap:.5rem}
p{margin:0 0 .9rem}
ul{margin:0 0 1rem;padding-left:1.15rem}
li{margin:0 0 .3rem}
code{font-family:var(--mono);font-size:.875em;background:var(--bg-soft);
padding:.1em .35em;border-radius:3px}
pre{margin:0 0 1.25rem;padding:.85rem 1rem;background:var(--bg-soft);
border:1px solid var(--rule);border-radius:3px;overflow-x:auto}
pre code{background:none;padding:0;font-size:.8125rem}
.banner{margin:0 0 1.5rem;padding:.9rem 1.1rem;border:1px solid var(--rule);
border-left:5px solid var(--edge);background:var(--tint);border-radius:3px}
.banner--pass{--edge:#1baf7a;--tint:#ebf7f1;--state:#0e6b4b}
.banner--warn{--edge:#e8a112;--tint:#fdf5e6;--state:#7a5405}
.banner--fail{--edge:#c4362c;--tint:#fdeeeb;--state:#9c1f18}
@media (prefers-color-scheme:dark){.banner--pass{--tint:#0f2a20;--state:#4fd6a4}
.banner--warn{--tint:#2b2110;--state:#f0c05a}
.banner--fail{--tint:#2e1512;--state:#f08276}}
.banner .verdict{display:block;margin:0 0 .35rem;color:var(--state);
font-size:1.05rem;font-weight:700;letter-spacing:.03em}
.banner .metrics{display:flex;flex-wrap:wrap;gap:.15rem 1.1rem;margin:0;
max-width:none;color:var(--ink-soft);font-size:.9375rem;font-variant-numeric:tabular-nums}
.banner .metrics>span{flex:0 1 auto;min-width:0}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(11.5rem,1fr));
gap:.75rem 1.5rem;margin:0;font-size:.875rem}
.meta dt{color:var(--ink-faint);font-size:.75rem;letter-spacing:.06em;text-transform:uppercase}
.meta dd{margin:.1rem 0 0;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.table-wrap{margin:0 0 1.5rem;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.875rem;font-variant-numeric:tabular-nums}
thead th{padding:.5rem .85rem .5rem 0;border-bottom:1px solid var(--rule-strong);
color:var(--ink-faint);font-weight:600;font-size:.75rem;letter-spacing:.06em;
text-transform:uppercase;text-align:left;white-space:nowrap}
tbody td{padding:.5rem .85rem .5rem 0;border-bottom:1px solid var(--rule);vertical-align:top}
tbody td:first-child{white-space:nowrap}
blockquote{margin:.35rem 0 1rem;padding:.75rem 1rem;border-left:3px solid var(--rule-strong);
background:var(--bg-quote);font-size:.9375rem;line-height:1.55;
white-space:pre-wrap;overflow-wrap:break-word;max-width:var(--measure)}
.failure{margin:0 0 2rem}
.tag{padding:.1em .55em;border:1px solid #8a5cf6;border-radius:999px;background:#f3eefe;
color:#6d3fd4;font-size:.6875rem;font-weight:600;letter-spacing:.04em;
text-transform:uppercase;white-space:nowrap}
@media (prefers-color-scheme:dark){.tag{background:#1e1730;color:#b79bfa}}
details{margin:0 0 1.5rem}
summary{cursor:pointer;color:var(--ink-soft);font-size:.9375rem}
@page{margin:15mm 14mm}
@media print{:root{color-scheme:light;--ink:#000;--ink-soft:#333;--ink-faint:#555;
--rule:#ccc;--rule-strong:#888;--bg:#fff;--bg-soft:#fff;--bg-quote:#fff}
body{padding:0;font-size:10.5pt;line-height:1.45}
.report,.report p,.report li,blockquote{max-width:none}
.banner{border:1px solid #999;border-left:4pt solid #333;
-webkit-print-color-adjust:exact;print-color-adjust:exact}
h1{font-size:16pt}h2{font-size:12pt;margin-top:1.4rem}
h1,h2,h3,summary{break-after:avoid}
.failure,blockquote,tr,.banner,.meta{break-inside:avoid}
p,li,blockquote{orphans:2;widows:2}
thead{display:table-header-group}
details{display:block}details>*{display:revert}}
"""


def _csp() -> str:
    digest = hashlib.sha256(CSS.encode("utf-8")).digest()
    return ("default-src 'none'; style-src 'sha256-"
            + base64.b64encode(digest).decode() + "'; "
            "base-uri 'none'; form-action 'none'")


def to_html(markdown: str) -> str:
    """Render report.md as one self-contained HTML document.

    No JavaScript, no external requests, no attributes carrying text from
    the run. The only input is the markdown itself.
    """
    blocks, title, state = _body(markdown)
    doc_title = escape(title) + (f" · {escape(state)}" if state else "")
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{_csp()}">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        f"<title>{doc_title}</title>\n"
        f"<style>{CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        '<main class="report">\n'
        + "\n".join(blocks)
        + "\n</main>\n</body>\n</html>\n"
    )
