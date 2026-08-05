"""Dot-path mapper and endpoint client, including the OpenAI-compatible
shape and malformed 2xx bodies (which must fail `answered`, never crash)."""

import json
import unittest

import httpx

from agent_report_card.client import EndpointClient, dig
from agent_report_card.schema import EndpointCfg


class TestDig(unittest.TestCase):
    def test_plain_and_nested(self):
        self.assertEqual(dig({"answer": "x"}, "answer"), "x")
        self.assertEqual(dig({"a": {"b": 1}}, "a.b"), 1)
        self.assertIsNone(dig({"a": 1}, "missing"))

    def test_openai_compatible_shape(self):
        data = {"choices": [{"message": {"content": "hello"}}]}
        self.assertEqual(dig(data, "choices.0.message.content"), "hello")

    def test_star_maps_over_lists(self):
        data = {"contexts": [{"text": "t1", "source": "s1"},
                             {"text": "t2", "source": "s2"}]}
        self.assertEqual(dig(data, "contexts.*.text"), ["t1", "t2"])
        self.assertEqual(dig(data, "contexts.*.source"), ["s1", "s2"])
        self.assertIsNone(dig({"contexts": "notalist"}, "contexts.*.text"))


def transport_returning(payload, status=200, raw=None):
    def handler(request):
        if raw is not None:
            return httpx.Response(status, content=raw)
        return httpx.Response(status, json=payload)
    return httpx.MockTransport(handler)


def make_client(transport, cfg=None):
    cfg = cfg or EndpointCfg(contexts_path="contexts.*.text",
                             sources_path="contexts.*.source")
    return EndpointClient("http://test", cfg, transport=transport)


class TestEndpointClient(unittest.TestCase):
    def test_happy_path(self):
        payload = {"answer": "42",
                   "contexts": [{"text": "ctx", "source": "doc.md"}]}
        reply = make_client(transport_returning(payload)).ask("q")
        self.assertIsNone(reply.error)
        self.assertEqual(reply.answer, "42")
        self.assertEqual(reply.contexts, ["ctx"])
        self.assertEqual(reply.sources, ["doc.md"])

    def test_malformed_2xx_body_is_a_case_failure_not_a_crash(self):
        reply = make_client(transport_returning(None, raw=b"<html>oops")).ask("q")
        self.assertIn("not valid JSON", reply.error)

    def test_answer_path_resolving_to_nothing(self):
        reply = make_client(transport_returning({"reply": "x"})).ask("q")
        self.assertIn("resolved to nothing", reply.error)

    def test_non_2xx(self):
        reply = make_client(transport_returning({"answer": "x"}, status=503)).ask("q")
        self.assertEqual(reply.error, "HTTP 503")

    def test_path_appended_only_to_bare_origin(self):
        cfg = EndpointCfg()
        bare = EndpointClient("http://host:8000", cfg)
        self.assertEqual(bare.url, "http://host:8000/ask")
        pathful = EndpointClient("http://host:8000/api/v2/query", cfg)
        self.assertEqual(pathful.url, "http://host:8000/api/v2/query")

    def test_scheme_less_endpoint_gets_http(self):
        client = EndpointClient("localhost:8000", EndpointCfg())
        self.assertEqual(client.url, "http://localhost:8000/ask")
        # a full request through a scheme-less base must also work
        cfg = EndpointCfg(contexts_path=None, sources_path=None)
        c = EndpointClient("test", cfg,
                           transport=transport_returning({"answer": "ok"}))
        self.assertEqual(c.ask("q").answer, "ok")


if __name__ == "__main__":
    unittest.main()
