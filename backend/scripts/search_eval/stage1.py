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
    #: Per query / no-match query: fused candidates before the floor, as
    #: (issue_id, best dense cosine, found by keyword) — for the T_FLOOR sweep.
    candidates: dict[str, list] = field(default_factory=dict)

    def aggregate(self, queries: list[Query]) -> dict[str, float]:
        rows = [self.per_query[q.id] for q in queries if q.id in self.per_query]
        if not rows:
            return {}
        return {k: mean(r[k] for r in rows) for k in rows[0]}

    @property
    def total_ms(self) -> list[float]:
        return [a + b for a, b in zip(self.embed_ms, self.retrieval_ms, strict=True)]

    def to_json(self) -> dict:
        """Everything ``report`` needs, so systems can be scored one at a time."""
        s = self.system
        return {
            "system": {"name": s.name, "endpoint": s.endpoint, "model": s.model,
                       "channels": list(s.channels), "floor": s.floor,
                       "vectors": len(s.owners), "index_seconds": s.index_seconds},
            "per_query": self.per_query, "no_match_counts": self.no_match_counts,
            "embed_ms": self.embed_ms, "retrieval_ms": self.retrieval_ms,
            "candidates": self.candidates,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Scores":
        sd = data["system"]
        system = System(sd["name"], sd["endpoint"], builder=None, channels=tuple(sd["channels"]),
                        floor=sd["floor"], model=sd["model"], index_seconds=sd["index_seconds"])
        return cls(system, data["per_query"], data["no_match_counts"],
                   data["embed_ms"], data["retrieval_ms"], data.get("candidates", {}))


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
            out.candidates[q.id] = index.last_candidates
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
            out.candidates[q.id] = index.last_candidates
            out.no_match_counts.append(len(ranked))
    finally:
        await index.close()
    return out


FLOOR_SWEEP = [round(0.30 + 0.025 * i, 3) for i in range(17)]  # 0.30 … 0.70


def floor_sweep(ds: Dataset, scores: Scores) -> list[dict]:
    """Re-apply the engine's floor rule (best dense cosine ≥ T, or found by the
    keyword channel) to the saved pre-floor candidates, for each T."""
    from app.search.constants import RESULT_LIMIT

    rows = []
    for t in FLOOR_SWEEP:
        def kept(qid):
            cands = scores.candidates.get(qid, [])
            return [c[0] for c in cands if c[1] >= t or c[2]][:RESULT_LIMIT]

        r5 = [metrics.recall_at(kept(q.id), q.rel, 5) for q in ds.queries]
        h5 = [metrics.hit_at(kept(q.id), q.rel, 5) for q in ds.queries]
        empty_real = sum(1 for q in ds.queries if not kept(q.id))
        shown = [len(kept(q.id)) for q in ds.no_match]
        rows.append({
            "T": t, "R@5": mean(r5), "Hit@5": mean(h5),
            "real_empty": empty_real / len(ds.queries),
            "nm_mean": mean(shown) if shown else 0.0,
            "nm_zero": sum(1 for n in shown if n == 0),
        })
    return rows


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
        "## T_FLOOR sweep (engine, Jev off)",
        "",
        "The floor rule re-applied to the saved candidates: a result stays if its best dense "
        f"cosine ≥ T or the keyword channel found it. In effect now: `T_FLOOR = {constants.T_FLOOR}`.",
        "",
        *(
            [_table(
                ["T", "Recall@5", "Hit@5", "real queries with 0 results", "no-match: mean shown",
                 "no-match: 0 shown"],
                [
                    [f"{r['T']:.3f}", _fmt(r["R@5"]), _fmt(r["Hit@5"]), f"{r['real_empty']:.1%}",
                     f"{r['nm_mean']:.2f}", f"{r['nm_zero']}/{len(ds.no_match)}"]
                    for r in floor_sweep(ds, engine)
                ],
            )] if engine.candidates else ["_No candidates saved; re-run the engine phase._"]
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
