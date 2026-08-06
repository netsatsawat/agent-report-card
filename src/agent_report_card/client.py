"""The endpoint client: one POST per question, dot-path response mapping.

The mapper is deliberately tiny. A dot-path walks dicts by key and lists by
integer index; a ``*`` segment maps the rest of the path over a list. That
is enough for both the bundled demo shape and OpenAI-compatible servers
(``choices.0.message.content``).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import httpx

from .schema import EndpointCfg


@dataclass
class EndpointReply:
    answer: str = ""
    contexts: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    status: int | None = None
    latency_s: float = 0.0
    error: str | None = None  # mapping or transport problem, quoted in the report


def dig(obj, path: str):
    """Resolve a dot-path against parsed JSON. Returns None when absent."""
    if path is None:
        return None
    current = obj
    parts = path.split(".")
    for i, part in enumerate(parts):
        if part == "*":
            if not isinstance(current, list):
                return None
            rest = ".".join(parts[i + 1:])
            if not rest:
                return current
            out = [dig(item, rest) for item in current]
            return [v for v in out if v is not None]
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            return None
    return current


def _as_str_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


class EndpointClient:
    def __init__(self, base_url: str, cfg: EndpointCfg, timeout: float = 60.0,
                 transport=None):
        self.cfg = cfg
        self.timeout = timeout
        if "://" not in base_url:
            base_url = "http://" + base_url  # scheme-less endpoints just work
        parts = urlsplit(base_url)
        # rebuild from parts: string concatenation would append the suite's
        # path after a query string, sending every request to /
        path = parts.path if parts.path not in ("", "/") else cfg.path
        self.url = urlunsplit((parts.scheme, parts.netloc, path.rstrip("/")
                               if path != "/" else path,
                               parts.query, parts.fragment))
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def close(self):
        self._client.close()

    def ask(self, question: str) -> EndpointReply:
        body = {self.cfg.question_field: question}
        start = time.perf_counter()
        try:
            response = self._request(body)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            try:
                response = self._request(body)  # one retry on connection error
            except httpx.HTTPError as exc:
                return EndpointReply(error=f"connection failed: {exc}",
                                     latency_s=time.perf_counter() - start)
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            return EndpointReply(error=f"request failed: {exc}",
                                 latency_s=time.perf_counter() - start)
        elapsed = time.perf_counter() - start

        reply = EndpointReply(status=response.status_code, latency_s=elapsed)
        if not (200 <= response.status_code < 300):
            reply.error = f"HTTP {response.status_code}"
            return reply
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError):
            reply.error = "response body is not valid JSON"
            return reply
        answer = dig(data, self.cfg.answer_path)
        if answer is None:
            reply.error = (f"answer path '{self.cfg.answer_path}' resolved to "
                           f"nothing in the response")
            return reply
        reply.answer = str(answer)
        reply.contexts = _as_str_list(dig(data, self.cfg.contexts_path))
        reply.sources = _as_str_list(dig(data, self.cfg.sources_path))
        return reply

    def _request(self, body):
        return self._client.request(
            self.cfg.method, self.url, json=body,
            headers=self.cfg.expanded_headers or None)
