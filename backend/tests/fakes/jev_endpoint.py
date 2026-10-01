"""A scripted fake Jev served over HTTP for the E2E stack (engine PRD A.12).

The E2E scenarios need exactly one behaviour: every same-problem question is
answered ``same`` with a high confidence, so a seeded item shows up in the
similar-reports panel and as a stored duplicate hint. Rerank (noul) questions
answer 0.9. Nothing else is modelled — no key check, no failures.

Run (docker-compose.e2e.yml):
    uvicorn tests.fakes.jev_endpoint:app --host 0.0.0.0 --port 80

The app reaches it through ``JEV_BASE_URL=http://jev:80``; the switch and key
are seeded (``scripts/seed_e2e.py``) so ``GET /features`` reports Jev on.
"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Fake Jev (E2E)")

MODEL = "jev-1.13.0"
#: What every same-problem judge answers — above ``T_SAME`` (0.7).
SAME_CONFIDENCE = 0.9


class Question(BaseModel):
    type: str = "noul"
    instructions: dict | str | None = None
    criteria: dict | None = None


class SystemOneRequest(BaseModel):
    state: object = None
    model: str | None = None
    questions: dict[str, Question]


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.post("/v1/systemone")
async def systemone(body: SystemOneRequest) -> dict:
    answers = {}
    for key, question in body.questions.items():
        if question.type == "choice":
            answers[key] = {
                "type": "choice",
                "choice": "same",
                "probabilities": {"same": SAME_CONFIDENCE},
                "confidence": SAME_CONFIDENCE,
            }
        else:
            answers[key] = {"type": "noul", "noul": SAME_CONFIDENCE}
    return {"model": MODEL, "answers": answers, "usage": {"input_tokens": 1}}
