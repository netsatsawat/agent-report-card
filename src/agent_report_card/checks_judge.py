"""The judge route: local Ollama, temperature 0, one binary question per
call, strict JSON verdicts.

Any per-call failure (JSON parse, timeout, connection error, non-200) gets
one retry; a second failure records the check as ``judge_error``, which is
excluded from denominators, counted, and disclosed, never coerced to a pass
or a fail.
"""

from __future__ import annotations

import json
import re

import httpx

from . import prompts
from .checks_code import CheckResult, PASS, FAIL, JUDGE_ERROR
from .client import EndpointReply
from .schema import Case

DEFAULT_JUDGE = "ollama:qwen3.6:27b"
DEFAULT_URL = "http://localhost:11434"


def parse_judge_spec(spec: str) -> tuple[str | None, str]:
    """'ollama:MODEL[@URL]' or 'none' -> (model or None, base_url)."""
    if spec in (None, "", "none"):
        return None, DEFAULT_URL
    body = spec[len("ollama:"):] if spec.startswith("ollama:") else spec
    if "@" in body:
        model, url = body.split("@", 1)
        return model, url.rstrip("/")
    return body, DEFAULT_URL


class JudgeClient:
    def __init__(self, model: str, base_url: str = DEFAULT_URL,
                 timeout: float = 120.0, transport=None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.calls = 0
        # Thinking models spend minutes deliberating before a one-word
        # verdict; ask Ollama to skip it. Models that reject the field get
        # one automatic fallback without it.
        self._disable_think = True
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def close(self):
        self._client.close()

    def reachable(self) -> tuple[bool, str]:
        """(ok, problem). Distinguishes a dead server from a missing model,
        so the error can say `ollama pull MODEL` instead of a mystery."""
        try:
            r = self._client.get(self.base_url + "/api/tags", timeout=5.0)
        except httpx.HTTPError as exc:
            return False, f"no Ollama server at {self.base_url} ({exc})"
        if r.status_code != 200:
            return False, f"{self.base_url}/api/tags returned HTTP {r.status_code}"
        try:
            names = [m.get("name", "") for m in r.json().get("models", [])]
        except (ValueError, KeyError, AttributeError):
            return True, ""  # non-Ollama-shaped server; let calls decide
        if names and self.model not in names and \
                f"{self.model}:latest" not in names:
            return False, (f"model '{self.model}' is not pulled on "
                           f"{self.base_url}; run: ollama pull {self.model}")
        return True, ""

    def _chat(self, prompt: str) -> str:
        self.calls += 1
        body = {"model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "format": "json",
                "options": {"temperature": 0}}
        if self._disable_think:
            body["think"] = False
        response = self._client.post(self.base_url + "/api/chat", json=body)
        if response.status_code == 400 and self._disable_think:
            self._disable_think = False
            del body["think"]
            response = self._client.post(self.base_url + "/api/chat", json=body)
        response.raise_for_status()
        return response.json()["message"]["content"]

    def verdict(self, prompt: str) -> tuple[str, str]:
        """Returns (status, reason) with status in pass/fail/judge_error."""
        attempts = [prompt, prompt + "\nReply with only the JSON object, nothing else."]
        last_problem = ""
        for attempt in attempts:
            try:
                content = self._chat(attempt)
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_problem = f"judge call failed: {exc}"
                continue
            parsed = _extract_json(content)
            if parsed and str(parsed.get("verdict", "")).lower() in ("pass", "fail"):
                return (PASS if str(parsed["verdict"]).lower() == "pass" else FAIL,
                        str(parsed.get("reason", "")))
            last_problem = f"judge reply was not a pass/fail JSON verdict: {content[:120]!r}"
        return JUDGE_ERROR, last_problem


def _extract_json(content: str):
    text = content.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\{.*?\}", text, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                return None
    return None


def run_judge_checks(judge: JudgeClient, case: Case,
                     reply: EndpointReply) -> list[CheckResult]:
    """The five judge checks, each n/a when its inputs are absent."""
    results = []
    answered = bool(reply.answer.strip()) and not reply.error

    def add(name, applicable, na_reason, prompt_key, **fields):
        if not applicable:
            results.append(CheckResult(name, "na", na_reason))
            return
        status, reason = judge.verdict(prompts.ALL[prompt_key].format(**fields))
        results.append(CheckResult(name, status, reason))

    add("judge_correct",
        answered and case.answerable and case.expected is not None,
        "no expected answer" if case.answerable else "case is answerable: false",
        "correct", question=case.question, expected=case.expected,
        answer=reply.answer)

    add("judge_grounded",
        answered and case.answerable and bool(reply.contexts),
        "no contexts returned (grounding cannot be checked)",
        "grounded", contexts="\n---\n".join(reply.contexts), answer=reply.answer)

    add("judge_refusal",
        answered and not case.answerable,
        "case is answerable",
        "refusal", question=case.question, answer=reply.answer)

    add("judge_citation_support",
        answered and bool(reply.sources) and bool(reply.contexts),
        "no citations returned" if not reply.sources else "no contexts returned",
        "citation", answer=reply.answer,
        contexts="\n---\n".join(reply.contexts))

    add("judge_on_topic",
        answered and case.answerable,
        "case is answerable: false" if not case.answerable else "no answer to check",
        "on_topic", question=case.question, answer=reply.answer)

    return results
