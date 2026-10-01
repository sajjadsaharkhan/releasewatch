"""An evaluation index: the engine's documents, embedded once, searched in memory.

The dense channels mirror ``app.search.retrieval._dense_channel`` (best cosine
per item and kind, top ``CHANNEL_LIMIT``); the keyword channel runs pg_trgm's
own ``word_similarity`` over a TEMP table, so it is exactly the production
function. Fusion and the floor are the engine's ``fuse`` / ``apply_floor``.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import asyncpg
import numpy as np

from app.config import settings
from app.search import embeddings
from app.search.comment_rules import rule_label
from app.search.constants import CHANNEL_LIMIT, KEYWORD_TOP, RESULT_LIMIT, T_TRGM
from app.search.documents import Documents, build_documents
from app.search.normalize import fold, normalize, strip_markdown
from app.search.retrieval import apply_floor, fuse

from .dataset import Dataset

#: Builds the documents for one item: the engine's, or the Phase 1 baseline's.
Builder = Callable[[object, list], Documents]


def engine_documents(item, comments) -> Documents:
    labels = {c.id: rule_label(c.body) for c in comments}
    return build_documents(item, comments, labels)


def phase1_documents(item, comments) -> Documents:
    """Phase 1's ``core`` group: the title twice, then the description (no
    steps, no comments, no keyword index — it used an English tsvector)."""
    parts = [f"Title: {item.title}", f"Title: {item.title}"]
    if item.description:
        parts.append(f"Description: {strip_markdown(item.description)}")
    return Documents(title="", body_chunks=[" ".join(parts)], talk=[], keyword_text="")


@dataclass
class System:
    name: str
    endpoint: str
    builder: Builder
    #: Channels this system searches (the baseline has only ``body``).
    channels: tuple[str, ...] = ("body", "title", "talk", "keyword")
    #: The engine's ``T_FLOOR`` (FR-S04). Phase 1 had none.
    floor: bool = True
    model: str = ""
    owners: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)
    matrix: np.ndarray | None = None
    index_seconds: float = 0.0


def _unit(rows: list[list[float]]) -> np.ndarray:
    m = np.asarray(rows, dtype=np.float32)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


class EvalIndex:
    def __init__(self, dataset: Dataset, system: System):
        self.ds = dataset
        self.sys = system
        self.conn: asyncpg.Connection | None = None
        self.table = f"eval_kw_{system.name}"
        self.last_candidates: list[tuple[str, float, bool]] = []

    async def build(self) -> None:
        start = time.perf_counter()
        texts, owners, kinds, keyword_rows = [], [], [], []
        for item_id, item in self.ds.items.items():
            docs = self.sys.builder(item, self.ds.comments.get(item_id, []))
            for kind, chunk in (
                [("title", docs.title)]
                + [("body", c) for c in docs.body_chunks]
                + [("talk", t.text) for t in docs.talk]
            ):
                if chunk and kind in self.sys.channels:
                    texts.append(chunk)
                    owners.append(item_id)
                    kinds.append(kind)
            if docs.keyword_text:
                keyword_rows.append((item_id, docs.keyword_text))

        result = await embeddings.embed(self.sys.endpoint, texts, timeout=120.0, dim=None)
        self.sys.model = result.model
        self.sys.owners, self.sys.kinds = owners, kinds
        self.sys.matrix = _unit(result.vectors)
        self.sys.index_seconds = time.perf_counter() - start

        if "keyword" in self.sys.channels:
            self.conn = await asyncpg.connect(
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                database=settings.POSTGRES_DB,
            )
            await self.conn.execute(
                f"CREATE TEMP TABLE {self.table} (issue_id text, keyword_text text)"
            )
            await self.conn.copy_records_to_table(self.table, records=keyword_rows)

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()

    async def search(self, query: str) -> tuple[list[str], float, float]:
        """``(ranked ids, embed ms, retrieval ms)`` — Jev off, page mode."""
        q = normalize(query)
        t0 = time.perf_counter()
        qv = _unit((await embeddings.embed(self.sys.endpoint, [q], dim=None)).vectors)[0]
        t1 = time.perf_counter()

        sims = self.sys.matrix @ qv
        best: dict[str, dict[str, float]] = {}
        for owner, kind, sim in zip(self.sys.owners, self.sys.kinds, sims.tolist(), strict=True):
            per_kind = best.setdefault(kind, {})
            if sim > per_kind.get(owner, -2.0):
                per_kind[owner] = sim
        channels = {
            kind: sorted(per_item.items(), key=lambda kv: (-kv[1], kv[0]))[:CHANNEL_LIMIT]
            for kind, per_item in best.items()
        }
        if self.conn is not None:
            rows = await self.conn.fetch(
                f"SELECT issue_id, word_similarity($1, keyword_text) AS ws FROM {self.table} "
                f"WHERE word_similarity($1, keyword_text) >= $2 ORDER BY ws DESC, issue_id LIMIT $3",
                fold(q),
                T_TRGM,
                KEYWORD_TOP,
            )
            channels["keyword"] = [(r["issue_id"], float(r["ws"])) for r in rows]

        fused = fuse(channels)
        hits = apply_floor(fused, dense_available=True) if self.sys.floor else fused
        hits = hits[:RESULT_LIMIT]
        t2 = time.perf_counter()
        #: Every fused candidate before the floor, for the T_FLOOR sweep.
        self.last_candidates = [
            (h.issue_id, round(h.best_dense, 4), "keyword" in h.sims) for h in fused
        ]
        return [h.issue_id for h in hits], (t1 - t0) * 1000, (t2 - t1) * 1000
