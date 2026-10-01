"""The embedding endpoint client (slice 12, engine PRD A.1, A.10).

The only code that knows where embeddings come from. Any OpenAI-compatible
``POST {endpoint}/embeddings`` works; the default is the bundled
text-embeddings-inference service running ``BAAI/bge-m3``.

The endpoint lives in ``system_settings`` (category ``search``, key
``config``: ``{embedding_endpoint, embed_model}``); without a row, the
``SEARCH_EMBEDDING_ENDPOINT`` setting applies. ``embed_model`` is whatever
the service last *reported* — never typed by a person — so a model swapped
behind the same endpoint is noticed and reindexed (BR-S16).
"""

from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes

from app.config import settings
from app.db.models.search import EMBEDDING_DIM
from app.db.models.system_setting import SystemSetting

#: Texts per request (A.5).
BATCH_SIZE = 32
#: Seconds per request.
TIMEOUT = 10.0

#: Test seam (Appendix A.12): when set, every request goes through this
#: transport — the in-process fake embedding endpoint in ``tests/``.
transport_override: httpx.AsyncBaseTransport | None = None


class EmbeddingError(Exception):
    """The endpoint is unreachable, failed, or answered with the wrong shape."""


@dataclass(frozen=True)
class Embedded:
    model: str
    vectors: list[list[float]]


@dataclass(frozen=True)
class SearchConfig:
    endpoint: str
    embed_model: str | None
    #: True when the endpoint is the installation default (no saved override).
    is_default: bool


def default_endpoint() -> str:
    return settings.SEARCH_EMBEDDING_ENDPOINT.rstrip("/")


async def _setting_row(db: AsyncSession) -> SystemSetting | None:
    return (
        await db.execute(
            select(SystemSetting).where(
                SystemSetting.category == "search", SystemSetting.key == "config"
            )
        )
    ).scalar_one_or_none()


async def load_config(db: AsyncSession) -> SearchConfig:
    row = await _setting_row(db)
    value = (row.value if row else None) or {}
    saved = (value.get("embedding_endpoint") or "").strip().rstrip("/")
    return SearchConfig(
        endpoint=saved or default_endpoint(),
        embed_model=value.get("embed_model") or None,
        is_default=not saved,
    )


async def save_config(
    db: AsyncSession,
    *,
    endpoint: str | None = None,
    embed_model: str | None = None,
) -> SearchConfig:
    """Update the saved endpoint and/or the reported model. An endpoint equal to
    the default is stored as "no override"."""
    row = await _setting_row(db)
    value = dict((row.value if row else None) or {})
    if endpoint is not None:
        endpoint = endpoint.strip().rstrip("/")
        value["embedding_endpoint"] = "" if endpoint == default_endpoint() else endpoint
    if embed_model is not None:
        value["embed_model"] = embed_model
    if row is None:
        db.add(SystemSetting(category="search", key="config", value=value, is_active=True))
    else:
        row.value = value
        attributes.flag_modified(row, "value")
    await db.flush()
    return await load_config(db)


def _client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, transport=transport_override)


async def embed(
    endpoint: str,
    texts: list[str],
    *,
    model: str | None = None,
    timeout: float = TIMEOUT,
    dim: int | None = EMBEDDING_DIM,
) -> Embedded:
    """Embed ``texts`` in batches of ``BATCH_SIZE``. Raises ``EmbeddingError``
    on any failure, and when a batch reports a different model than the first.
    ``dim=None`` skips the size check — only the evaluation harness does that
    (its MiniLM baseline is 384-dim and never reaches the index)."""
    if not texts:
        return Embedded(model=model or "", vectors=[])
    vectors: list[list[float]] = []
    reported: str | None = None
    try:
        async with _client(timeout) as client:
            for start in range(0, len(texts), BATCH_SIZE):
                batch = texts[start : start + BATCH_SIZE]
                payload: dict = {"input": batch}
                if model:
                    payload["model"] = model
                resp = await client.post(f"{endpoint.rstrip('/')}/embeddings", json=payload)
                resp.raise_for_status()
                body = resp.json()
                batch_model = str(body.get("model") or model or "")
                if reported is not None and batch_model != reported:
                    raise EmbeddingError("The embedding service changed model mid-request.")
                reported = batch_model
                rows = sorted(body["data"], key=lambda d: d.get("index", 0))
                vectors.extend(r["embedding"] for r in rows)
    except EmbeddingError:
        raise
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise EmbeddingError(f"Embedding request failed: {exc}") from exc

    if len(vectors) != len(texts):
        raise EmbeddingError("The embedding service returned the wrong number of vectors.")
    if not reported:
        raise EmbeddingError("The embedding service did not report its model.")
    if dim is not None and any(len(v) != dim for v in vectors):
        raise EmbeddingError(
            f"The embedding service returned {len(vectors[0])}-dimension vectors; "
            f"the index stores {dim}."
        )
    return Embedded(model=reported, vectors=vectors)


async def probe(endpoint: str, *, timeout: float = 5.0) -> str:
    """The model an endpoint serves, by embedding one word. Raises ``EmbeddingError``."""
    return (await embed(endpoint, ["ping"], timeout=timeout)).model
