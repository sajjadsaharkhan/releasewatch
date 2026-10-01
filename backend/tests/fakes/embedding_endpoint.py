"""The fake embedding endpoint (engine PRD Appendix A.12).

An OpenAI-compatible ``POST /v1/embeddings`` that needs no model: each text
becomes character trigrams of its folded words, hashed into 1024 dimensions
and L2-normalized. Two texts are similar exactly when they share trigrams, so
a test makes an item findable *by construction* — quality claims come only
from the evaluation report, never from this.

The reported model is ``fake/<host>``, so pointing the endpoint at another
host looks like a model change (AC-S18).

In tests it runs in-process (``app.search.embeddings.transport_override``);
the E2E stack runs it as a container:
``uvicorn tests.fakes.embedding_endpoint:app --port 80``.
"""

import hashlib
import math

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.search.normalize import fold

DIM = 1024


def vector(text: str) -> list[float]:
    v = [0.0] * DIM
    for word in fold(text).split():
        padded = f" {word} "
        for i in range(len(padded) - 2):
            h = int.from_bytes(hashlib.md5(padded[i : i + 3].encode()).digest()[:4], "big")
            v[h % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0:
        v[0] = 1.0
        return v
    return [x / norm for x in v]


class FakeEmbeddings:
    def __init__(self) -> None:
        self.app = FastAPI()
        #: Every text embedded, per request, in order.
        self.requests: list[list[str]] = []
        #: When set, every request answers 503.
        self.fail = False
        #: Overrides the vector size, to test the dimension check.
        self.dim: int | None = None
        self.app.add_api_route("/v1/embeddings", self._embeddings, methods=["POST"])
        self.app.add_api_route("/health", self._health, methods=["GET"])

    @property
    def texts(self) -> list[str]:
        return [t for batch in self.requests for t in batch]

    def reset(self) -> None:
        self.requests.clear()
        self.fail = False
        self.dim = None

    async def _health(self) -> dict:
        return {"ok": True}

    async def _embeddings(self, request: Request):
        if self.fail:
            return JSONResponse({"error": "unavailable"}, status_code=503)
        body = await request.json()
        texts = body["input"] if isinstance(body["input"], list) else [body["input"]]
        self.requests.append(list(texts))
        host = (request.headers.get("host") or "fake").split(":")[0]
        data = []
        for i, t in enumerate(texts):
            vec = vector(t)
            if self.dim is not None:
                vec = vec[: self.dim]
            data.append({"object": "embedding", "index": i, "embedding": vec})
        return {"object": "list", "data": data, "model": f"fake/{host}", "usage": {}}


fake = FakeEmbeddings()
app = fake.app
