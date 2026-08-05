"""The HTML export is a projection of report.md, and these tests are what
make that true rather than aspirational.

Three guarantees are enforced here:
  1. Purity: report_html imports nothing from the package, so it cannot
     read the scoreboard and cannot become a second renderer.
  2. Totality: every line shape the markdown emits is handled, and an
     unknown one raises instead of vanishing from the HTML.
  3. Parity: the numbers in the HTML are exactly the numbers in the
     markdown, in the same order.
Plus escaping, because the report quotes text the system under test wrote.
"""

import ast
import inspect
import re
import unittest
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from agent_report_card import report_html, scoring
from agent_report_card.report_html import UnrenderableLine, to_html

REPO = Path(__file__).resolve().parent.parent
REPORTS = sorted((REPO / "reports").glob("*.md"))


def text_of(html: str) -> str:
    """Visible text, the way a reader sees it.

    Every step here exists because skipping it produced a false result:
    leaving <style> in leaks CSS lengths into the number stream;
    replacing tags with "" instead of " " fuses adjacent numbers into
    values that appear in neither document; and skipping the unescape
    lets numeric character references contribute their own digits, since
    an escaped apostrophe is literally `&#x27;`.
    """
    body = re.sub(r"(?s)<style>.*?</style>", " ", html)
    body = re.sub(r"(?s)<head>.*?</head>", " ", body)
    return unescape(re.sub(r"<[^>]+>", " ", body))


NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


class Structure(HTMLParser):
    """What the browser would actually build, so tests can assert on
    elements and attributes rather than on substrings that may be inert
    escaped text."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.attrs: list[tuple[str, str, str]] = []  # (tag, name, value)
        self._text: list[str] = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for name, value in attrs:
            self.attrs.append((tag, name, value or ""))

    def handle_data(self, data):
        self._text.append(data)

    @property
    def text(self) -> str:
        return "".join(self._text)

    @property
    def event_handlers(self):
        return [a for a in self.attrs if a[1].startswith("on")]

    @property
    def fetching_attrs(self):
        """Attributes that would make the document reach the network."""
        return [a for a in self.attrs
                if a[1] in ("src", "href", "srcset", "action", "data",
                            "poster", "background")]


class TestPurity(unittest.TestCase):
    def test_imports_nothing_from_the_package(self):
        tree = ast.parse(inspect.getsource(report_html))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(
                    node.level, 0,
                    "report_html must not import from the package: the HTML "
                    "is a projection of report.md, never a second reading of "
                    "the scoreboard")
                modules.add((node.module or "").split(".")[0])
        self.assertLessEqual(modules - {"__future__"},
                             {"base64", "hashlib", "re", "html"})

    def test_mirrored_verdicts_match_scoring(self):
        # not imported, so a rename in scoring must fail here loudly
        self.assertEqual(
            set(report_html.VERDICTS),
            {scoring.VERDICT_PASS, scoring.VERDICT_WARN, scoring.VERDICT_FAIL})


class TestTotality(unittest.TestCase):
    def test_every_committed_report_converts(self):
        self.assertTrue(REPORTS, "no committed reports to check")
        for path in REPORTS:
            with self.subTest(report=path.name):
                to_html(path.read_text(encoding="utf-8"))

    def test_unknown_line_raises_rather_than_vanishing(self):
        with self.assertRaises(UnrenderableLine):
            to_html("# T\n\n<script>alert(1)</script>\n")

    def test_only_the_allowlisted_raw_html_passes_through(self):
        # a future report.py change that emits new raw HTML must fail here
        for path in REPORTS:
            raw = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
                   if ln.strip().startswith("<")]
            for line in raw:
                self.assertIn(line, report_html.RAW_HTML, path.name)


class TestParity(unittest.TestCase):
    def test_numbers_match_the_markdown_exactly(self):
        for path in REPORTS:
            with self.subTest(report=path.name):
                markdown = path.read_text(encoding="utf-8")
                self.assertEqual(
                    NUMBER.findall(markdown),
                    NUMBER.findall(text_of(to_html(markdown))),
                    "the HTML shows different numbers than report.md")

    def test_prose_survives_too_not_just_numbers(self):
        """Numbers alone would let a digitless section vanish unnoticed."""
        markers = re.compile(r"^[#>\-\s|]+|[*`|]")
        for path in REPORTS:
            with self.subTest(report=path.name):
                markdown = path.read_text(encoding="utf-8")
                want = [markers.sub(" ", ln).split()
                        for ln in markdown.splitlines()]
                words = [w for line in want for w in line if w.isalpha()]
                seen = text_of(to_html(markdown))
                missing = [w for w in set(words) if w not in seen]
                self.assertEqual([], missing,
                                 "words present in report.md are absent "
                                 "from the HTML")

    def test_the_committed_html_matches_the_committed_markdown(self):
        """The README showcases this file; it must not drift from its own
        report between gallery runs."""
        html = REPO / "reports" / "demo_report.html"
        markdown = REPO / "reports" / "demo_report.md"
        self.assertTrue(html.exists(), "reports/demo_report.html is missing")
        self.assertEqual(
            html.read_text(encoding="utf-8"),
            to_html(markdown.read_text(encoding="utf-8")),
            "reports/demo_report.html is stale; regenerate with `make gallery`")

    def test_an_indented_quoted_line_keeps_its_shape(self):
        # a quoted traceback is evidence; its indentation is part of it
        html = to_html("# T\n\n> Traceback (most recent call last):\n"
                       '>   File "/srv/bot/render.py", line 88\n'
                       ">     KeyError: 'x'\n")
        self.assertIn('  File "/srv/bot/render.py", line 88',
                      Structure(html).text)
        self.assertIn("    KeyError: 'x'", Structure(html).text)

    def test_a_pipe_in_a_metadata_cell_does_not_drop_values(self):
        md = ("# T\n\n"
              "| endpoint | tests | judge | date | wall clock | tool |\n"
              "|---|---|---|---|---|---|\n"
              "| http://x | a|b | j | d | 1s | t |\n")
        text = Structure(to_html(md)).text
        for value in ("http://x", "a", "b", "j", "1s", "t"):
            self.assertIn(value, text)

    def test_verdict_and_headings_survive(self):
        markdown = (REPO / "reports" / "demo_report_judged.md").read_text(
            encoding="utf-8")
        html = to_html(markdown)
        self.assertIn("banner--fail", html)
        for heading in re.findall(r"^## (.+)$", markdown, re.M):
            self.assertIn(heading.split(":")[0][:20], text_of(html))


class TestEscaping(unittest.TestCase):
    HOSTILE = (
        "# Report card · t\n\n"
        "## Failures, quoted\n\n"
        "### 1. q01\n\n"
        "**Got:**\n\n"
        "> <script>alert('xss')</script>\n"
        "> <img src=x onerror=alert(1)>\n"
        "> </details><h1>injected\n"
        '> He said "quoted" & <b>bold</b>\n\n'
    )

    def setUp(self):
        self.html = to_html(self.HOSTILE)

    def test_no_live_markup_from_the_answer(self):
        # structural, not substring: `onerror=` as escaped text inside a
        # blockquote is inert, and asserting on its absence would be a
        # false alarm. What matters is that no ELEMENT carries it.
        parsed = Structure(self.html)
        self.assertNotIn("script", parsed.tags)
        self.assertNotIn("img", parsed.tags)
        self.assertEqual([], parsed.event_handlers)
        # the answer's markup survived only as text
        self.assertIn("<script>alert('xss')</script>", parsed.text)

    def test_the_text_is_still_readable(self):
        self.assertIn("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;",
                      self.html)
        self.assertIn("&amp;", self.html)

    def test_a_smuggled_closing_tag_cannot_end_the_appendix(self):
        # </details> inside an answer must not terminate a real one
        self.assertEqual(self.html.count("</details>"), 0)
        self.assertIn("</details>", Structure(self.html).text)


class TestSelfContainment(unittest.TestCase):
    def setUp(self):
        self.html = to_html(
            (REPO / "reports" / "demo_report_judged.md").read_text(
                encoding="utf-8"))

    def test_no_external_requests_of_any_kind(self):
        # a URL printed as text (the endpoint) is not a request; an
        # attribute that fetches one is. Assert on the latter.
        parsed = Structure(self.html)
        self.assertEqual([], parsed.fetching_attrs)
        css = re.search(r"(?s)<style>(.*?)</style>", self.html).group(1)
        for token in ("url(", "@import", "//"):
            self.assertNotIn(token, css, f"stylesheet reaches out via {token}")

    def test_no_javascript(self):
        parsed = Structure(self.html)
        self.assertNotIn("script", parsed.tags)
        self.assertEqual([], parsed.event_handlers)
        self.assertNotIn("javascript:", self.html.lower())

    def test_declares_charset_and_a_content_security_policy(self):
        self.assertIn('<meta charset="utf-8">', self.html)
        self.assertIn("default-src 'none'", self.html)
        self.assertIn("style-src 'sha256-", self.html)

    def test_the_csp_hash_matches_the_stylesheet_actually_shipped(self):
        import base64
        import hashlib
        css = re.search(r"(?s)<style>(.*?)</style>", self.html).group(1)
        digest = base64.b64encode(
            hashlib.sha256(css.encode("utf-8")).digest()).decode()
        self.assertIn(f"'sha256-{digest}'", self.html,
                      "the CSP hash does not cover the stylesheet as emitted, "
                      "so a browser would block the styles")


if __name__ == "__main__":
    unittest.main()
