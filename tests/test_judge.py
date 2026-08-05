"""Judge client: JSON parse discipline, retry, judge_error on transport
failures. All offline via recorded transports; no model needed."""

import unittest

import httpx

from agent_report_card.checks_judge import (JudgeClient, parse_judge_spec,
                                            run_judge_checks)
from agent_report_card.client import EndpointReply
from agent_report_card.schema import Case


def judge_with_replies(replies):
    """A JudgeClient whose Ollama returns each reply in sequence."""
    replies = list(replies)

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        content = replies.pop(0) if replies else "{}"
        if isinstance(content, Exception):
            raise content
        return httpx.Response(200, json={"message": {"content": content}})

    return JudgeClient("test-model", "http://judge",
                       transport=httpx.MockTransport(handler))


class TestParseSpec(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(parse_judge_spec("none"), (None, "http://localhost:11434"))
        self.assertEqual(parse_judge_spec("ollama:qwen3.6:27b"),
                         ("qwen3.6:27b", "http://localhost:11434"))
        self.assertEqual(parse_judge_spec("ollama:m@http://host:1234"),
                         ("m", "http://host:1234"))


class TestVerdictParsing(unittest.TestCase):
    def test_clean_json(self):
        judge = judge_with_replies(['{"verdict": "pass", "reason": "fine"}'])
        self.assertEqual(judge.verdict("p"), ("pass", "fine"))

    def test_fenced_json(self):
        judge = judge_with_replies(['```json\n{"verdict": "fail", "reason": "wrong"}\n```'])
        self.assertEqual(judge.verdict("p"), ("fail", "wrong"))

    def test_retry_then_success(self):
        judge = judge_with_replies(
            ["I think the answer looks right overall.",
             '{"verdict": "pass", "reason": "ok"}'])
        self.assertEqual(judge.verdict("p")[0], "pass")
        self.assertEqual(judge.calls, 2)

    def test_double_garbage_is_judge_error_never_coerced(self):
        judge = judge_with_replies(["nonsense", "still nonsense"])
        status, reason = judge.verdict("p")
        self.assertEqual(status, "judge_error")
        self.assertIn("not a pass/fail JSON verdict", reason)

    def test_transport_failure_is_judge_error(self):
        judge = judge_with_replies(
            [httpx.ConnectError("boom"), httpx.ConnectError("boom")])
        status, reason = judge.verdict("p")
        self.assertEqual(status, "judge_error")
        self.assertIn("judge call failed", reason)


class TestApplicability(unittest.TestCase):
    def test_na_reasons_when_inputs_absent(self):
        judge = judge_with_replies(
            ['{"verdict": "pass", "reason": ""}'] * 10)
        case = Case(id="c", question="q", line=1, expected="42")
        reply = EndpointReply(answer="42")  # no contexts, no sources
        results = {c.name: c for c in run_judge_checks(judge, case, reply)}
        self.assertEqual(results["judge_correct"].status, "pass")
        self.assertEqual(results["judge_grounded"].status, "na")
        self.assertEqual(results["judge_citation_support"].status, "na")
        self.assertEqual(results["judge_refusal"].status, "na")

    def test_unanswerable_routes_to_refusal(self):
        judge = judge_with_replies(['{"verdict": "fail", "reason": "answered"}'])
        case = Case(id="c", question="q", line=1, answerable=False)
        reply = EndpointReply(answer="The salary is 3.4 million")
        results = {c.name: c for c in run_judge_checks(judge, case, reply)}
        self.assertEqual(results["judge_refusal"].status, "fail")
        self.assertEqual(results["judge_correct"].status, "na")


if __name__ == "__main__":
    unittest.main()
