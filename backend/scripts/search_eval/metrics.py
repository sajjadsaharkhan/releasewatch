"""Ranking metrics. Pure."""

import math
from statistics import quantiles


def recall_at(ranked: list[str], rel: dict[str, int], k: int) -> float:
    """Share of grade-2 answers found in the top ``k``."""
    wanted = {i for i, g in rel.items() if g >= 2}
    if not wanted:
        return 0.0
    return len(wanted & set(ranked[:k])) / len(wanted)


def hit_at(ranked: list[str], rel: dict[str, int], k: int) -> float:
    """1 when any grade-2 answer is in the top ``k``."""
    return 1.0 if any(rel.get(i, 0) >= 2 for i in ranked[:k]) else 0.0


def reciprocal_rank(ranked: list[str], rel: dict[str, int]) -> float:
    for n, i in enumerate(ranked, start=1):
        if rel.get(i, 0) >= 2:
            return 1.0 / n
    return 0.0


def ndcg_at(ranked: list[str], rel: dict[str, int], k: int = 10) -> float:
    def dcg(grades):
        return sum((2**g - 1) / math.log2(n + 2) for n, g in enumerate(grades))

    ideal = dcg(sorted(rel.values(), reverse=True)[:k])
    return dcg([rel.get(i, 0) for i in ranked[:k]]) / ideal if ideal else 0.0


def p50_p95(samples_ms: list[float]) -> tuple[float, float]:
    if not samples_ms:
        return 0.0, 0.0
    if len(samples_ms) < 2:
        return samples_ms[0], samples_ms[0]
    cuts = quantiles(samples_ms, n=100, method="inclusive")
    return cuts[49], cuts[94]
