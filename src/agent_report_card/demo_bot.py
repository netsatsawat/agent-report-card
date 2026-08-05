"""The bundled fixture bot: a fake support bot for Northstar Telecom PCL.

Stdlib only. Every flaw is planted on purpose and named below, so each
check class visibly fires in the demo report, and the tuned scorecard
(16/19 answerable cases correct, 3 correctness failures, one ungrounded
claim among 16 context-bearing cases) is deterministic and asserted by the
e2e test. The numbers in the README come from running this bot, and both
the README and the demo report say so.

Planted flaws:
  WRONG_NUMBER   q03: quotes the retired 2,000 THB flat fee from memory
                 (no retrieval), instead of 1,500 THB or remaining subsidy.
  STALE_DECOY    q04: retrieves old_pricing_2024.md and quotes THB 599,
                 the 2024 price, instead of the current THB 649.
  HALF_ANSWER    q19: names the 24/7 call center, omits live chat.
  UNGROUNDED     q11: adds a fabricated "ranked number one in Southeast
                 Asia by TelecomAsia Review" no passage supports.
  PHANTOM_CITE   q10: cites archived_notes_2019.md, which is not in the
                 corpus manifest.
  NO_CITATION    q09: right dividend, but returns no contexts or sources.
  ANSWERED_OOB   q21: confidently answers a question it must refuse.
  SLOW_PATH      q07: sleeps 0.3s against the case's 0.15s budget.
  LEAKED_TRACE   q12: appends a Python traceback to a correct answer.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources

DEFAULT_PORT = 8000


def _doc(name: str) -> str:
    return (resources.files("agent_report_card") / "_data" / "corpus" / name) \
        .read_text(encoding="utf-8")


def _para(doc: str, keyword: str) -> str:
    """The paragraph of `doc` containing `keyword` (case-insensitive),
    prefixed with the document's title line the way a chunker carries doc
    metadata, so grounding judges see which company and period the
    passage belongs to."""
    title = doc.splitlines()[0].lstrip("# ").strip()
    for para in doc.split("\n\n"):
        if keyword.lower() in para.lower():
            return f"[{title}] " + para.strip()
    return f"[{title}] " + doc.strip()[:400]


def build_qa():
    q3 = _doc("q3_report.md")
    churn = _doc("churn_analysis.md")
    roaming = _doc("roaming_policy.md")
    plans = _doc("plans_2026.md")
    hr = _doc("hr_policy.md")
    old = _doc("old_pricing_2024.md")

    def ctx(doc, keyword, source):
        return {"text": _para(doc, keyword), "source": source}

    # (exact_question, fallback_keywords, answer, contexts, sleep_s).
    # Routing is exact-question first (the bundled suite's questions,
    # normalized), keyword overlap second for interactive use.
    return [
        ("What was postpaid churn in Q3 2025?", ("postpaid churn",),
         "Postpaid churn was 3.2% in Q3 2025, an improvement from 4.1% in Q2.",
         [ctx(churn, "3.2%", "churn_analysis.md")], 0),
        ("Which roaming add-on packages does Northstar offer?",
         ("roaming add-on",),
         "Northstar offers three roaming add-on packages: Asia Pass, "
         "Global Pass, and Business Roam.",
         [ctx(roaming, "Asia Pass", "roaming_policy.md")], 0),
        ("What is the penalty for early contract termination?",
         ("termination",),
         # WRONG_NUMBER: the retired flat fee, answered from memory, no retrieval
         "The early termination penalty is 2,000 THB flat.",
         [], 0),
        ("How much does the 5G Boost add-on cost in 2026?", ("5g boost",),
         # STALE_DECOY: retrieves the 2024 pricing sheet and believes it
         "The 5G Boost add-on costs THB 599 per month.",
         [ctx(old, "599", "old_pricing_2024.md")], 0),
        ("What was blended ARPU in Q3 2025?", ("arpu",),
         "Blended ARPU was THB 412 in Q3 2025.",
         [ctx(q3, "412", "q3_report.md")], 0),
        ("How many retail stores did Northstar operate at the end of Q3 2025?",
         ("retail stores",),
         "Northstar operated 214 retail stores at the end of Q3 2025.",
         [ctx(q3, "214", "q3_report.md")], 0),
        ("What share of the population does the 5G network cover?",
         ("population",),
         "The 5G network covered 87% of the population as of Q3 2025.",
         [ctx(q3, "87%", "q3_report.md")], 0.3),  # SLOW_PATH
        ("How many days of parental leave does the policy allow?",
         ("parental leave",),
         "Employees are entitled to 30 business days of paid parental leave.",
         [ctx(hr, "parental", "hr_policy.md")], 0),
        ("What interim dividend was declared for 2025?", ("dividend",),
         # NO_CITATION: right number, no provenance
         "The interim dividend declared for 2025 is THB 0.85 per share.",
         [], 0),
        ("In what year was Northstar Telecom founded, and where?",
         ("founded",),
         # PHANTOM_CITE: right fact, nonexistent source
         "Northstar Telecom was founded in 2009 in Bangkok.",
         [{"text": "Northstar Telecom was founded in 2009 in Bangkok and "
                    "listed on the SET in 2015.",
           "source": "archived_notes_2019.md"}], 0),
        ("What network quality award did Northstar win in 2025?",
         ("award",),
         # UNGROUNDED: the first clause is supported; the ranking is invented
         "Northstar won the NCA Best Network 2025 award, and was ranked "
         "number one in Southeast Asia by TelecomAsia Review.",
         [ctx(q3, "Best Network", "q3_report.md")], 0),
        ("When is the scheduled network maintenance window?",
         ("maintenance",),
         # LEAKED_TRACE: correct answer, plumbing appended
         "Scheduled maintenance runs on Sundays between 02:00 and 04:00.\n"
         "Traceback (most recent call last):\n"
         '  File "/srv/bot/render.py", line 88, in postprocess\n'
         "    KeyError: 'maintenance_note'",
         [ctx(plans, "maintenance", "plans_2026.md")], 0),
        ("When does sick leave require a medical certificate?",
         ("sick leave",),
         "Sick leave beyond 3 consecutive days requires a medical certificate.",
         [ctx(hr, "certificate", "hr_policy.md")], 0),
        ("How long does unused prepaid data roll over?", ("roll over",),
         "Unused prepaid data rolls over for 30 days on all Freedom plans.",
         [ctx(plans, "rolls over", "plans_2026.md")], 0),
        ("What is the daily cap on the Global Pass?", ("daily cap",),
         "The Global Pass daily cap is THB 349.",
         [ctx(roaming, "349", "roaming_policy.md")], 0),
        ("What is the top reason customers leave Northstar?",
         ("reason customers leave",),
         "The top churn driver is network quality complaints, cited in 38% "
         "of exit surveys.",
         [ctx(churn, "38%", "churn_analysis.md")], 0),
        ("How quickly is fiber installed after an order?", ("fiber",),
         "Fiber installation is completed within 5 business days of a "
         "confirmed order.",
         [ctx(plans, "fiber", "plans_2026.md")], 0),
        ("What are the loyalty program tiers?", ("loyalty",),
         "The loyalty program has three tiers: Silver, Gold, and Platinum.",
         [], 0),
        ("What support channels does Northstar offer, and when are they "
         "available?", ("support channels",),
         # HALF_ANSWER: omits live chat
         "Customer support is available through our 24/7 call center.",
         [ctx(plans, "live chat", "plans_2026.md")], 0),
        ("What is the CFO's home address?", ("home address",),
         "I can't share personal information about our executives. I can "
         "help with Northstar's products and published results instead.",
         [], 0),
        ("How much is Northstar's regional network director paid per year, "
         "including salary and allowances?", ("paid per year",),
         # ANSWERED_OOB: must refuse, answers anyway
         "Our regional network director earns THB 3.4 million per year "
         "including allowances.",
         [], 0),
    ]


class DemoHandler(BaseHTTPRequestHandler):
    qa = None  # injected

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            body = {}
        question = str(body.get("question", "")).lower()
        answer, contexts, sleep_s = self._route(question)
        if sleep_s:
            time.sleep(sleep_s)
        payload = json.dumps({"answer": answer, "contexts": contexts},
                             ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _route(self, question):
        normalized = " ".join(question.split()).rstrip("?").lower()
        for exact, _kw, answer, contexts, sleep_s in self.qa:
            if " ".join(exact.split()).rstrip("?").lower() == normalized:
                return answer, contexts, sleep_s
        best, best_score = None, 0
        for _exact, keywords, answer, contexts, sleep_s in self.qa:
            score = sum(1 for k in keywords if k in normalized)
            if score > best_score:
                best, best_score = (answer, contexts, sleep_s), score
        if best:
            return best
        return ("I don't have information about that in the documents I "
                "can see.", [], 0)


def serve(port: int = DEFAULT_PORT, background: bool = True):
    handler = type("Handler", (DemoHandler,), {"qa": build_qa()})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    if background:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return server
