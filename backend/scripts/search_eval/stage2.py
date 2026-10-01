"""``stage2``: Jev on (engine PRD §8 Q4, Q5; slices 13–14).

``--part search`` — Jev reranks each query's stage-1 candidates, read from the
engine scores ``stage1 --phase engine --state DIR`` saved (no re-embedding):
the engine's floor, then the top ``JEV_CANDIDATES``, the same payload the app
sends (``JevClient.rerank``). Reports ranking metrics on Jev's order and a
``T_RELEVANT`` sweep: recall above the threshold vs results shown above it on
no-match queries (**Q4**: ≤ 1 on average).

``--part comments`` — ``JevClient.classify_comment`` on every labelled comment,
a confusion matrix against the gold labels, accuracy per label (**Q5**,
reported, not gated), and the rule's agreement for comparison.

``--part similar`` (slice 14) — ``drafts.json`` through the app's
same-problem path: body+title stage-1 candidates, then ``JevClient.judge_same``
— the triage filter (not Cancelled; the snapshot is Phase 1 data, so the
support-source filter has nothing to filter). Precision / recall / F1 per draft
kind with a ``T_SAME`` sweep (**Q3**: precision on duplicate + hard-negative
drafts ≥ 0.80), and "show stage-1 top-3 without Jev" as the reference policy.

The Jev key comes from the ``JEV_API_KEY`` environment variable, never argv.
"""

import asyncio
import collections
import json
from datetime import UTC, datetime
from statistics import mean

from app.search import constants
from app.search.comment_rules import RULE_KEPT, rule_label, talk_weight
from app.search.constants import DUPLICATE_HINT_LIMIT, SIMILAR_CANDIDATES
from app.search.jev import JevClient, JevItem
from app.search.normalize import normalize, strip_markdown

from . import metrics
from .dataset import Dataset, Draft
from .index import EvalIndex, System, engine_documents

SWEEP = [round(0.20 + 0.05 * i, 2) for i in range(16)]  # 0.20 … 0.95
#: Parallel Jev calls in flight (stay well under the 40 rps limit).
CONCURRENCY = 6


def _items_for(ds: Dataset, ids: list[str]) -> list[JevItem]:
    out = []
    for i in ids:
        it = ds.items[i]
        out.append(
            JevItem(id=i, title=it.title, description=normalize(strip_markdown(it.description)))
        )
    return out


def _floored(candidates: list) -> list[str]:
    kept = [c[0] for c in candidates if c[1] >= constants.T_FLOOR or c[2]]
    return kept[: constants.JEV_CANDIDATES]


async def run_search(ds: Dataset, engine_state: dict, jev: JevClient, progress=print) -> dict:
    cands = engine_state["candidates"]
    sem = asyncio.Semaphore(CONCURRENCY)
    failures = collections.Counter()
    latencies: list[int] = []

    async def judge(qid: str, text: str) -> tuple[str, list[str], dict]:
        top = _floored(cands.get(qid, []))
        if not top:
            return qid, [], {}
        async with sem:
            outcome, scores = await jev.rerank(text, _items_for(ds, top))
        if not outcome.ok:
            failures[outcome.reason] += 1
            return qid, top, {}
        latencies.append(outcome.latency_ms)
        return qid, top, scores

    jobs = [judge(q.id, q.q) for q in ds.queries] + [judge(q.id, q.q) for q in ds.no_match]
    results = {}
    for n, coro in enumerate(asyncio.as_completed(jobs), start=1):
        qid, top, scores = await coro
        results[qid] = {"stage1": top, "scores": scores}
        if n % 50 == 0:
            progress(f"[stage2 search] {n}/{len(jobs)}")
    return {"results": results, "failures": dict(failures), "latency_ms": latencies}


def search_report(ds: Dataset, run: dict) -> str:
    res = run["results"]

    def jev_order(qid: str) -> list[str]:
        r = res.get(qid, {"stage1": [], "scores": {}})
        if not r["scores"]:
            return r["stage1"]
        return sorted(r["stage1"], key=lambda i: -r["scores"].get(i, 0.0))

    def m(order_fn) -> dict:
        rows = [(order_fn(q.id), q.rel) for q in ds.queries]
        return {
            "R@1": mean(metrics.recall_at(o, rel, 1) for o, rel in rows),
            "R@5": mean(metrics.recall_at(o, rel, 5) for o, rel in rows),
            "MRR": mean(metrics.reciprocal_rank(o, rel) for o, rel in rows),
            "nDCG@10": mean(metrics.ndcg_at(o, rel, 10) for o, rel in rows),
        }

    stage1 = m(lambda qid: res.get(qid, {}).get("stage1", []))
    jev = m(jev_order)

    sweep = []
    for t in SWEEP:

        def above(qid, t=t):
            r = res.get(qid, {"stage1": [], "scores": {}})
            return [i for i in jev_order(qid) if r["scores"].get(i, 0.0) >= t]

        r5 = mean(metrics.recall_at(above(q.id), q.rel, 5) for q in ds.queries)
        empty = sum(1 for q in ds.queries if not above(q.id)) / len(ds.queries)
        shown = [len(above(q.id)) for q in ds.no_match]
        fp_grade0 = mean(sum(1 for i in above(q.id) if q.rel.get(i, 0) == 0) for q in ds.queries)
        sweep.append((t, r5, empty, mean(shown) if shown else 0.0, fp_grade0))

    p50, p95 = metrics.p50_p95([float(x) for x in run["latency_ms"]])
    lines = [
        f"# Stage-2 evaluation (search) — {datetime.now(tz=UTC).date().isoformat()}",
        "",
        f"Dataset `{ds.path}`: {len(ds.queries)} queries, {len(ds.no_match)} no-match. "
        f"Candidates: the engine's stage-1 list after `T_FLOOR = {constants.T_FLOOR}`, top "
        f"{constants.JEV_CANDIDATES}. Jev failures: {run['failures'] or 'none'}. "
        f"Jev latency p50 {p50:.0f} ms, p95 {p95:.0f} ms.",
        "",
        "## Ranking (all candidates, Jev order vs stage-1 order)",
        "",
        "| Order | R@1 | R@5 | MRR | nDCG@10 |",
        "|---|---|---|---|---|",
        *(
            f"| {name} | {v['R@1']:.3f} | {v['R@5']:.3f} | {v['MRR']:.3f} | {v['nDCG@10']:.3f} |"
            for name, v in (("stage 1", stage1), ("Jev rerank", jev))
        ),
        "",
        "## T_RELEVANT sweep — what lands in `results` (above the threshold)",
        "",
        "Q4: results shown above the threshold on no-match queries ≤ 1 on average. "
        f"In effect now: `T_RELEVANT = {constants.T_RELEVANT}`.",
        "",
        "| T | Recall@5 above T | real queries with no result above T | no-match: mean shown (Q4) | "
        "irrelevant results above T per query |",
        "|---|---|---|---|---|",
        *(
            f"| {t:.2f} | {r5:.3f} | {empty:.1%} | {nm:.2f} | {fp:.2f} |"
            for t, r5, empty, nm, fp in sweep
        ),
        "",
    ]
    return "\n".join(lines)


async def run_comments(ds: Dataset, gold: list[dict], jev: JevClient, progress=print) -> dict:
    comments = {c.corpus_id: (issue_id, c) for issue_id, cs in ds.comments.items() for c in cs}
    sem = asyncio.Semaphore(CONCURRENCY)
    out = []

    async def one(g: dict) -> dict:
        issue_id, c = comments[g["id"]]
        item = ds.items[issue_id]
        async with sem:
            outcome, result = await jev.classify_comment(
                item.title,
                normalize(strip_markdown(item.description)),
                normalize(strip_markdown(c.body)),
                background=True,
            )
        return {
            "id": g["id"],
            "gold": g["label"],
            "rule": rule_label(c.body),
            "jev": result[0] if result else None,
            "confidence": result[1] if result else None,
            "reason": None if outcome.ok else outcome.reason,
        }

    for n, coro in enumerate(asyncio.as_completed([one(g) for g in gold]), start=1):
        out.append(await coro)
        if n % 50 == 0:
            progress(f"[stage2 comments] {n}/{len(gold)}")
    return {"rows": out}


def comments_report(run: dict) -> str:
    rows = [r for r in run["rows"] if r["jev"]]
    labels = ["this_problem", "other_problem", "process", "ack"]
    cm = collections.Counter((r["gold"], r["jev"]) for r in rows)
    acc = {g: (cm[(g, g)] / n if (n := sum(cm[(g, p)] for p in labels)) else 0.0) for g in labels}
    total = sum(cm[(g, g)] for g in labels) / len(rows) if rows else 0.0

    def used(label, conf=None):
        return talk_weight(label, conf) > 0

    gold_used = {r["id"]: r["gold"] in ("this_problem", "other_problem") for r in run["rows"]}
    jev_agree = (
        mean(used(r["jev"], r["confidence"]) == gold_used[r["id"]] for r in rows) if rows else 0.0
    )
    rule_agree = mean((r["rule"] == RULE_KEPT) == gold_used[r["id"]] for r in run["rows"])
    failed = len(run["rows"]) - len(rows)
    lines = [
        "# Stage-2 evaluation (comments)",
        "",
        f"{len(run['rows'])} labelled comments; Jev answered {len(rows)} ({failed} failed). "
        f"Accuracy over all four labels: **{total:.3f}** (Q5, reported, not gated).",
        "",
        "## Confusion matrix (rows: gold, columns: Jev)",
        "",
        "| gold \\ Jev | " + " | ".join(labels) + " | accuracy |",
        "|---|" + "---|" * (len(labels) + 1),
        *(
            f"| {g} | " + " | ".join(str(cm[(g, p)]) for p in labels) + f" | {acc[g]:.3f} |"
            for g in labels
        ),
        "",
        "## Used for search or not",
        "",
        'Gold "used" = this_problem or other_problem. Agreement on that yes/no decision:',
        "",
        f"- Jev (with the confidence < {0.6} rule): **{jev_agree:.3f}**",
        f"- The rule alone (`rule_kept`): **{rule_agree:.3f}**",
        "",
    ]
    return "\n".join(lines)


def save(path, data) -> None:
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)


# ── --part similar (slice 14, Q3) ────────────────────────────────────────────

DRAFT_KINDS = ("duplicate", "recurrence", "hard_negative", "novel")
#: Phase 1 snapshot statuses that mean cancelled for the candidate filter.
_CANCELLED = {"cancelled"}


def _candidate_ok(ds: Dataset, item_id: str) -> bool:
    status = str(ds.items[item_id].status or "").lower()
    return status not in _CANCELLED


async def run_similar(ds: Dataset, endpoint: str, jev: JevClient, progress=print) -> dict:
    """Each draft through the app's same-problem path (14): body+title stage-1
    candidates (the same documents and channels ``same_problem_candidates``
    uses), the triage filter, then Jev's same/related/unrelated judgment."""
    system = System(
        "engine", endpoint, engine_documents, channels=("body", "title"), floor=False,
    )
    index = EvalIndex(ds, system)
    await index.build()
    sem = asyncio.Semaphore(CONCURRENCY)
    failures = collections.Counter()

    async def one(d: Draft) -> dict:
        text = " ".join(p for p in (d.title, d.description) if p)
        ids, _, _ = await index.search(text)
        cands = [i for i in ids if _candidate_ok(ds, i)][:SIMILAR_CANDIDATES]
        if not cands:
            return {"id": d.id, "kind": d.kind, "stage1": [], "verdicts": {}}
        async with sem:
            outcome, verdicts = await jev.judge_same(
                d.title, normalize(strip_markdown(d.description)), _items_for(ds, cands),
                background=True,
            )
        if not outcome.ok:
            failures[outcome.reason] += 1
            verdicts = {}
        return {"id": d.id, "kind": d.kind, "stage1": cands, "verdicts": verdicts}

    rows = []
    jobs = [one(d) for d in ds.drafts]
    for n, coro in enumerate(asyncio.as_completed(jobs), start=1):
        rows.append(await coro)
        if n % 25 == 0:
            progress(f"[stage2 similar] {n}/{len(jobs)}")
    await index.close()
    return {"rows": rows, "failures": dict(failures)}


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def similar_report(ds: Dataset, run: dict) -> str:
    rows = run["rows"]
    gold = {d.id: set(d.same) for d in ds.drafts}
    kinds = [k for k in DRAFT_KINDS if any(r["kind"] == k for r in rows)]

    def shown(row, t: float) -> list[str]:
        """The triage rule: `same` at or above T, top DUPLICATE_HINT_LIMIT."""
        verdicts = row["verdicts"]
        picked = [
            i for i, v in verdicts.items()
            if v[0] == "same" and v[1] >= t
        ]
        picked.sort(key=lambda i: -verdicts[i][1])
        return picked[:DUPLICATE_HINT_LIMIT]

    def counts(picked: list[str], same: set[str]):
        """(TP, FP, FN) of the shown ids against the gold `same` set."""
        hit = len(same & set(picked))
        return hit, len(picked) - hit, len(same - set(picked))

    def aggregate(pick) -> dict[str, tuple[int, int, int]]:
        """(TP, FP, FN) per draft kind, micro-aggregated over ``pick(row)`` ids."""
        out = {k: [0, 0, 0] for k in kinds}
        for r in rows:
            tp, fp, fn = counts(pick(r), gold[r["id"]])
            cell = out[r["kind"]]
            cell[0], cell[1], cell[2] = cell[0] + tp, cell[1] + fp, cell[2] + fn
        return out

    def fmt3(x: float) -> str:
        return f"{x:.3f}"

    def table(agg: dict[str, tuple[int, int, int]]) -> list[str]:
        return [
            f"| {kind} | {tp + fp} | {fmt3(p)} | {fmt3(r)} | {fmt3(f1)} |"
            for kind, (tp, fp, fn) in ((k, v) for k, v in agg.items())
            for p, r, f1 in [_prf(tp, fp, fn)]
        ]

    q3_agg = aggregate(lambda r: shown(r, constants.T_SAME))
    q3_tp = sum(q3_agg[k][0] for k in ("duplicate", "hard_negative") if k in q3_agg)
    q3_fp = sum(q3_agg[k][1] for k in ("duplicate", "hard_negative") if k in q3_agg)
    q3_p = _prf(q3_tp, q3_fp, 0)[0]
    q3 = q3_p >= 0.80

    n_per_kind = {k: sum(1 for r in rows if r["kind"] == k) for k in kinds}
    sweep = [
        (t, {k: _prf(*v) for k, v in aggregate(lambda r, t=t: shown(r, t)).items()})
        for t in SWEEP
    ]

    lines = [
        f"# Stage-2 evaluation (similar) — {datetime.now(tz=UTC).date().isoformat()}",
        "",
        f"Dataset `{ds.path}`: {len(rows)} drafts "
        f"({', '.join(f'{k} {n}' for k, n in n_per_kind.items())}). "
        f"Candidates: body+title stage 1, top {SIMILAR_CANDIDATES}, not Cancelled; "
        f"Jev judge, top {DUPLICATE_HINT_LIMIT} `same` shown. "
        f"Jev failures: {run['failures'] or 'none'}.",
        "",
        "The snapshot is Phase 1 data (no support-sourced items), so this runs the "
        "triage filter; the support panel's open-support filter has nothing to filter.",
        "",
        "## Gates — Q3: same-problem precision on duplicate + hard-negative ≥ 0.80",
        "",
        f"At `T_SAME = {constants.T_SAME}`: **{q3_p:.3f}** — " + ("pass" if q3 else "**no**"),
        "",
        f"## In effect now (T_SAME = {constants.T_SAME})",
        "",
        "| kind | shown | precision | recall | F1 |",
        "|---|---|---|---|---|",
        *table(q3_agg),
        "",
        "## Reference: stage-1 top-3 without Jev",
        "",
        "| kind | shown | precision | recall | F1 |",
        "|---|---|---|---|---|",
        *table(aggregate(lambda r: r["stage1"][:DUPLICATE_HINT_LIMIT])),
        "",
        "## T_SAME sweep",
        "",
        "| T | " + " | ".join(f"{k} P/R/F1" for k in kinds) + " |",
        "|---|" + "---|" * len(kinds),
        *(
            f"| {t:.2f} | "
            + " | ".join(f"{p:.3f} / {r:.3f} / {f1:.3f}" for p, r, f1 in precisions.values())
            for t, precisions in sweep
        ),
        "",
        "## Recommendation",
        "",
        "_Fill in: keep or change `T_SAME` (and `T_RELATED`), and explain any gate "
        "that did not pass._",
        "",
    ]
    return "\n".join(lines)
