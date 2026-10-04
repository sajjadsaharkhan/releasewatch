"""JevClient — every call to Jev (slice 13, engine PRD Appendix A.7).

Jev is TypeSafe's System One model: ``POST {JEV_BASE_URL}/v1/systemone`` with a
``state`` and a map of typed questions, answered per question key (a ``noul``
returns ``{"noul": p}``, a ``choice`` returns ``{"choice", "probabilities",
"confidence"}``).

One rule for callers (principle S2, BR-S02): every method returns a
``JevOutcome``. ``ok`` false means "behave as if Jev were off" — there is no
exception path to the user. The request path never retries and has a 1.5 s
budget; background jobs get 10 s and up to 4 retries with backoff on
429/529/5xx/timeouts.

Instructions stay in English (Jev reads them best); the state stays in the
original language. Logs carry purpose, size, latency and outcome — never the
state or the instructions.
"""

import asyncio
import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("app.search.jev")

DEFAULT_MODEL = "jev-1.13.0"
REQUEST_TIMEOUT = 1.5
JOB_TIMEOUT = 10.0
JOB_RETRIES = 4
#: Questions per call; above it, calls are split and run in parallel (A.7).
MAX_QUESTIONS = 20
#: Failure reasons a background job retries (429 rate limit, 529 overloaded, 5xx, timeouts).
RETRYABLE = {"timeout", "network", "http_429", "http_529", "http_5xx"}

#: Description excerpts sent to Jev (A.7).
RERANK_DESCRIPTION_CHARS = 400
JUDGE_DESCRIPTION_CHARS = 600

#: Test seam (Appendix A.12): the fake Jev in ``tests/`` replaces the transport.
transport_override: httpx.AsyncBaseTransport | None = None

RERANK_QUESTION = (
    "The state is a search query typed into a software issue tracker. Does `issue` describe the "
    "problem the user is searching for? Wording and language (Persian/English, transliterated "
    "words) may differ."
)
JUDGE_QUESTION = (
    "The state is a new report being written. How does `existing_issue` relate to it? Wording "
    "and language may differ."
)
JUDGE_CRITERIA = {
    "same": "Same underlying problem: same feature and the same faulty behaviour",
    "related": "Same feature or area, but a different faulty behaviour, platform or condition",
    "unrelated": "A different feature or problem",
}
COMMENT_QUESTION = (
    "What does `comment` contribute to understanding the problem described in `issue`?"
)
COMMENT_CRITERIA = {
    "this_problem": "Adds technical detail about this issue's problem: symptom, cause, "
    "reproduction, scope, error, or fix",
    "other_problem": "Mainly discusses a different, related problem or another project",
    "process": "Coordination, planning, assignment, product or priority decisions, no "
    "technical content",
    "ack": "Agreement, thanks, acknowledgement or status ping",
}


@dataclass(frozen=True)
class JevOutcome:
    ok: bool
    #: Answers by question key when ``ok``.
    answers: dict[str, dict] | None = None
    #: Why it failed: ``timeout``, ``http_401``, ``http_429``, ``http_5xx``,
    #: ``malformed``, ``no_key``, ``network``.
    reason: str | None = None
    model: str | None = None
    latency_ms: int = 0


@dataclass(frozen=True)
class JevItem:
    """One candidate as Jev sees it: never more than a title and an excerpt."""

    id: int | str
    title: str
    description: str = ""
    type: str = "bug"


def _excerpt(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


class JevClient:
    def __init__(
        self, api_key: str | None, model: str = DEFAULT_MODEL, proxy_url: str | None = None
    ) -> None:
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        #: Settings → Configuration proxy, when enabled for Jev's host (never logged).
        self.proxy_url = proxy_url

    # ── Transport ─────────────────────────────────────────────────────────────

    async def _post_once(self, payload: dict, timeout: float) -> JevOutcome:
        url = settings.JEV_BASE_URL.rstrip("/") + "/v1/systemone"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=transport_override,
                proxy=None if transport_override else self.proxy_url,
            ) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            return JevOutcome(False, reason="timeout", latency_ms=_ms(start))
        except httpx.HTTPError:
            return JevOutcome(False, reason="network", latency_ms=_ms(start))
        if resp.status_code != 200:
            code = resp.status_code
            reason = "http_5xx" if code >= 500 and code != 529 else f"http_{code}"
            return JevOutcome(False, reason=reason, latency_ms=_ms(start))
        try:
            body = resp.json()
            answers = body["answers"]
            if not isinstance(answers, dict):
                raise TypeError
        except (ValueError, KeyError, TypeError):
            return JevOutcome(False, reason="malformed", latency_ms=_ms(start))
        return JevOutcome(True, answers=answers, model=body.get("model"), latency_ms=_ms(start))

    async def _post(self, payload: dict, *, background: bool) -> JevOutcome:
        if not self.api_key:
            return JevOutcome(False, reason="no_key")
        timeout = JOB_TIMEOUT if background else REQUEST_TIMEOUT
        attempts = 1 + (JOB_RETRIES if background else 0)
        outcome = JevOutcome(False, reason="network")
        for attempt in range(attempts):
            outcome = await self._post_once(payload, timeout)
            if outcome.ok or outcome.reason not in RETRYABLE or attempt == attempts - 1:
                break
            await _sleep(min(8.0, 0.5 * 2**attempt))
        return outcome

    async def ask(
        self,
        state: Any,
        questions: Mapping[str, dict],
        *,
        purpose: str,
        background: bool = False,
    ) -> JevOutcome:
        """Send ``questions`` (split into calls of ``MAX_QUESTIONS``, run in
        parallel) about ``state``. ``ok`` only if every call succeeded."""
        keys = list(questions)
        chunks = [keys[i : i + MAX_QUESTIONS] for i in range(0, len(keys), MAX_QUESTIONS)] or [[]]
        start = time.perf_counter()
        outcomes = await asyncio.gather(
            *(
                self._post(
                    {
                        "state": state,
                        "model": self.model,
                        "questions": {k: questions[k] for k in chunk},
                    },
                    background=background,
                )
                for chunk in chunks
            )
        )
        failed = next((o for o in outcomes if not o.ok), None)
        answers: dict[str, dict] = {}
        for o in outcomes:
            answers.update(o.answers or {})
        model = next((o.model for o in outcomes if o.model), None)
        result = (
            JevOutcome(False, reason=failed.reason, latency_ms=_ms(start))
            if failed
            else JevOutcome(True, answers=answers, model=model, latency_ms=_ms(start))
        )
        logger.info(
            "jev_call purpose=%s n_questions=%d latency_ms=%d ok=%s reason=%s model=%s",
            purpose,
            len(keys),
            result.latency_ms,
            result.ok,
            result.reason,
            result.model or self.model,
        )
        return result

    # ── Questions (A.7) ───────────────────────────────────────────────────────

    async def ping(self) -> JevOutcome:
        """Settings → Test connection: one tiny Noul."""
        return await self.ask(
            "ping",
            {"ping": {"type": "noul", "instructions": "Is the state a greeting?"}},
            purpose="test",
            background=False,
        )

    async def rerank(self, query: str, items: Sequence[JevItem]) -> tuple[JevOutcome, dict]:
        """Search rerank: one Noul per candidate. Returns ``(outcome, {id: score})``."""
        questions = {
            f"c_{it.id}": {
                "type": "noul",
                "instructions": {
                    "issue": {
                        "title": it.title,
                        "description": _excerpt(it.description, RERANK_DESCRIPTION_CHARS),
                    },
                    "question": RERANK_QUESTION,
                },
            }
            for it in items
        }
        outcome = await self.ask(query, questions, purpose="rerank")
        if not outcome.ok:
            return outcome, {}
        try:
            scores = {it.id: float(outcome.answers[f"c_{it.id}"]["noul"]) for it in items}
        except (KeyError, TypeError, ValueError):
            return JevOutcome(False, reason="malformed", latency_ms=outcome.latency_ms), {}
        return outcome, scores

    async def judge_same(
        self,
        draft_title: str,
        draft_description: str,
        items: Sequence[JevItem],
        *,
        background: bool = False,
    ) -> tuple[JevOutcome, dict]:
        """Same-problem judge (slice 14 wires it). ``{id: (verdict, confidence, probabilities)}``."""
        questions = {
            f"c_{it.id}": {
                "type": "choice",
                "instructions": {
                    "existing_issue": {
                        "title": it.title,
                        "description": _excerpt(it.description, JUDGE_DESCRIPTION_CHARS),
                        "type": it.type,
                    },
                    "question": JUDGE_QUESTION,
                },
                "criteria": JUDGE_CRITERIA,
            }
            for it in items
        }
        state = {"new_report": {"title": draft_title, "description": draft_description}}
        outcome = await self.ask(state, questions, purpose="judge_same", background=background)
        if not outcome.ok:
            return outcome, {}
        try:
            verdicts = {
                it.id: (
                    a["choice"],
                    float(a.get("confidence", 0.0)),
                    dict(a.get("probabilities") or {}),
                )
                for it in items
                for a in [outcome.answers[f"c_{it.id}"]]
            }
        except (KeyError, TypeError, ValueError):
            return JevOutcome(False, reason="malformed", latency_ms=outcome.latency_ms), {}
        return outcome, verdicts

    async def classify_comment(
        self,
        issue_title: str,
        issue_description: str,
        comment: str,
        *,
        background: bool = True,
    ) -> tuple[JevOutcome, tuple[str, float] | None]:
        """Comment classification (A.6): ``(label, confidence)``."""
        state = {
            "issue": {
                "title": issue_title,
                "description": _excerpt(issue_description, JUDGE_DESCRIPTION_CHARS),
            },
            "comment": comment,
        }
        questions = {
            "kind": {
                "type": "choice",
                "instructions": COMMENT_QUESTION,
                "criteria": COMMENT_CRITERIA,
            },
        }
        outcome = await self.ask(
            state, questions, purpose="classify_comment", background=background
        )
        if not outcome.ok:
            return outcome, None
        try:
            answer = outcome.answers["kind"]
            label = answer["choice"]
            if label not in COMMENT_CRITERIA:
                raise ValueError(label)
            return outcome, (label, float(answer.get("confidence", 0.0)))
        except (KeyError, TypeError, ValueError):
            return JevOutcome(False, reason="malformed", latency_ms=outcome.latency_ms), None


async def _sleep(seconds: float) -> None:
    """Retry backoff (a seam: tests make it instant)."""
    await asyncio.sleep(seconds)


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
