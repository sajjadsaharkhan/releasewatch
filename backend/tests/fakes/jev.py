"""The fake Jev (engine PRD Appendix A.12).

A transport for ``app.search.jev.JevClient`` that answers ``POST /v1/systemone``
in-process, records every request, and can be told how to answer:

- ``script(prefix, answer)`` — questions whose key starts with ``prefix`` get
  ``answer`` (a dict, or a callable ``(key, question, state) -> dict``).
- ``default(rule)`` — every other question: ``rule(key, question, state) -> dict``.
- ``fail(mode)`` — ``timeout`` | ``http_401`` | ``http_429`` | ``http_500`` |
  ``malformed`` for every call until ``fail(None)``.
- ``calls`` — every request body, in order (``state``, ``model``, ``questions``).
"""

import json
from collections.abc import Callable

import httpx

MODEL = "jev-1.13.0"


def _default_rule(key: str, question: dict, state) -> dict:
    if question["type"] == "noul":
        return {"type": "noul", "noul": 0.9}
    first = next(iter(question["criteria"]))
    return {
        "type": "choice",
        "choice": first,
        "probabilities": {o: (1.0 if o == first else 0.0) for o in question["criteria"]},
        "confidence": 0.95,
    }


class FakeJev(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.calls: list[dict] = []
        self.auth: list[str | None] = []
        self._scripts: list[tuple[str, dict | Callable]] = []
        self._default: Callable = _default_rule
        self._fail: str | None = None

    def script(self, prefix: str, answer: dict | Callable) -> None:
        self._scripts.insert(0, (prefix, answer))

    def default(self, rule: Callable) -> None:
        self._default = rule

    def fail(self, mode: str | None) -> None:
        self._fail = mode

    @property
    def questions(self) -> list[str]:
        """Every question key asked, across calls."""
        return [k for c in self.calls for k in c["questions"]]

    def _answer(self, key: str, question: dict, state) -> dict:
        for prefix, answer in self._scripts:
            if key.startswith(prefix):
                return answer(key, question, state) if callable(answer) else dict(answer)
        return self._default(key, question, state)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.calls.append(body)
        self.auth.append(request.headers.get("authorization"))
        if self._fail == "timeout":
            raise httpx.ReadTimeout("fake Jev timeout", request=request)
        if self._fail and self._fail.startswith("http_"):
            return httpx.Response(int(self._fail[5:]), json={"error": self._fail}, request=request)
        if self._fail == "malformed":
            return httpx.Response(200, json={"unexpected": True}, request=request)
        answers = {k: self._answer(k, q, body["state"]) for k, q in body["questions"].items()}
        return httpx.Response(
            200,
            json={"model": MODEL, "answers": answers, "usage": {"input_tokens": 1}},
            request=request,
        )
