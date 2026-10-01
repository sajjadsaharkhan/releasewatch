"""``stage1``: Jev-off search quality and latency, engine vs the Phase 1 baseline.

Gates (engine PRD §8): **Q1** Recall@5 ≥ baseline + 10 points; **Q2** stage-1
p95 (query embedding + retrieval) < 300 ms. Q2 is only meaningful on
production hardware with the full corpus — the report states where it ran.
"""

import platform
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from statistics import mean

from app.search import constants

from . import metrics
from .dataset import Dataset, Query
from .index import EvalIndex, System

Q1_MARGIN = 0.10
Q2_P95_MS = 300.0


@dataclass
class Scores:
    system: System
    per_query: dict[str, dict] = field(default_factory=dict)
    no_match_counts: list[int] = field(default_factory=list)
    embed_ms: list[float] = field(default_factory=list)
    retrieval_ms: list[float] = field(default_factory=list)

    def aggregate(self, queries: list[Query]) -> dict[str, float]:
        rows = [self.per_query[q.id] for q in queries if q.id in self.per_query]
        if not rows:
            return {}
        return {k: mean(r[k] for r in rows) for k in rows[0]}

    @property
    def total_ms(self) -> list[float]:
        return [a + b for a, b in zip(self.embed_ms, self.retrieval_ms, strict=True)]


async def score(ds: Dataset, system: System, progress=print) -> Scores:
    index = EvalIndex(ds, system)
    progress(f"[{system.name}] embedding {len(ds.items)} items via {system.endpoint} …")
    await index.build()
    progress(
        f"[{system.name}] model {system.model}, {len(system.owners)} vectors, {system.index_seconds:.1f}s"
    )
    out = Scores(system)
    try:
        for q in ds.queries:
            ranked, e_ms, r_ms = await index.search(q.q)
            out.embed_ms.append(e_ms)
            out.retrieval_ms.append(r_ms)
            out.per_query[q.id] = {
                "R@1": metrics.recall_at(ranked, q.rel, 1),
                "R@5": metrics.recall_at(ranked, q.rel, 5),
                "R@10": metrics.recall_at(ranked, q.rel, 10),
                "Hit@5": metrics.hit_at(ranked, q.rel, 5),
                "MRR": metrics.reciprocal_rank(ranked, q.rel),
                "nDCG@10": metrics.ndcg_at(ranked, q.rel, 10),
            }
        for q in ds.no_match:
            ranked, _, _ = await index.search(q.q)
            out.no_match_counts.append(len(ranked))
    finally:
        await index.close()
    return out


def _fmt(x: float) -> str:
    return f"{x:.3f}"


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def report(ds: Dataset, engine: Scores, baseline: Scores, *, host_note: str) -> str:
    metric_names = ["R@1", "R@5", "R@10", "Hit@5", "MRR", "nDCG@10"]
    overall = {s.system.name: s.aggregate(ds.queries) for s in (engine, baseline)}

    by_cat: dict[str, list[Query]] = defaultdict(list)
    for q in ds.queries:
        for c in q.cats or ["untagged"]:
            by_cat[c].append(q)

    e5 = overall[engine.system.name].get("R@5", 0.0)
    b5 = overall[baseline.system.name].get("R@5", 0.0)
    q1 = e5 >= b5 + Q1_MARGIN
    _, e_p95 = metrics.p50_p95(engine.total_ms)
    q2 = e_p95 < Q2_P95_MS

    parts = [
        f"# Stage-1 evaluation — {datetime.now(tz=UTC).date().isoformat()}",
        "",
        f"Dataset: `{ds.path}` — {len(ds.items)} items, "
        f"{sum(len(v) for v in ds.comments.values())} comments, {len(ds.queries)} queries, "
        f"{len(ds.no_match)} no-match queries.",
        f"Engine: `{engine.system.model}` at `{engine.system.endpoint}`. "
        f"Baseline (Phase 1): `{baseline.system.model}` at `{baseline.system.endpoint}`, "
        "Phase 1 documents (title twice + description), dense channel only, no floor.",
        f"Host: {host_note}",
        "",
        "## Gates",
        "",
        _table(
            ["Gate", "Measure", "Result", "Pass"],
            [
                [
                    "Q1",
                    "Recall@5 ≥ baseline + 10 pts",
                    f"{_fmt(e5)} vs {_fmt(b5)} (+{(e5 - b5) * 100:.1f} pts)",
                    "yes" if q1 else "**no**",
                ],
                ["Q2", "stage-1 p95 < 300 ms", f"{e_p95:.0f} ms", "yes" if q2 else "**no**"],
            ],
        ),
        "",
        "## Overall",
        "",
        _table(
            ["System", *metric_names],
            [
                [name, *(_fmt(agg.get(m, 0.0)) for m in metric_names)]
                for name, agg in overall.items()
            ],
        ),
        "",
        "## Recall@5 by category",
        "",
        _table(
            ["Category", "n", engine.system.name, baseline.system.name],
            [
                [
                    cat,
                    str(len(qs)),
                    _fmt(engine.aggregate(qs).get("R@5", 0.0)),
                    _fmt(baseline.aggregate(qs).get("R@5", 0.0)),
                ]
                for cat, qs in sorted(by_cat.items())
            ],
        ),
        "",
        "## No-match queries (Jev off)",
        "",
        "Results shown after the `T_FLOOR` floor on queries no item answers — lower is better.",
        "",
        _table(
            ["System", "mean shown", "queries with 0"],
            [
                [
                    s.system.name,
                    _fmt(mean(s.no_match_counts) if s.no_match_counts else 0.0),
                    f"{sum(1 for n in s.no_match_counts if n == 0)}/{len(s.no_match_counts)}",
                ]
                for s in (engine, baseline)
            ],
        ),
        "",
        "## Latency (ms)",
        "",
        "Retrieval here is the in-memory mirror of the SQL channels plus pg_trgm; the "
        "production path runs the same channels in Postgres.",
        "",
        _table(
            ["System", "embed p50", "embed p95", "retrieval p50", "retrieval p95", "total p95"],
            [
                [
                    s.system.name,
                    *(
                        f"{v:.0f}"
                        for v in (
                            *metrics.p50_p95(s.embed_ms),
                            *metrics.p50_p95(s.retrieval_ms),
                            metrics.p50_p95(s.total_ms)[1],
                        )
                    ),
                ]
                for s in (engine, baseline)
            ],
        ),
        "",
        "## Constants in effect (`app/search/constants.py`)",
        "",
        _table(
            ["Constant", "Value"],
            [
                ["FUSION_WEIGHTS", str(constants.FUSION_WEIGHTS)],
                ["RRF_K", str(constants.RRF_K)],
                ["T_FLOOR", str(constants.T_FLOOR)],
                ["T_TRGM", str(constants.T_TRGM)],
                ["KEYWORD_TOP", str(constants.KEYWORD_TOP)],
                ["CHANNEL_LIMIT", str(constants.CHANNEL_LIMIT)],
            ],
        ),
        "",
        "## Recommendation",
        "",
        "_Fill in: keep or change the constants above, and explain any gate that did not pass._",
        "",
    ]
    return "\n".join(parts)


def default_host_note() -> str:
    return f"{platform.node()} ({platform.machine()}, {platform.system()})"
