# ruff: noqa: E501 — long Markdown lines
"""Pick the duplicate-hint threshold (``T_SAME``) from the dataset.

    docker compose exec api python -m scripts.dup_dataset sweep            # asks Jev, saves, reports
    docker compose exec api python -m scripts.dup_dataset sweep --reuse    # re-report from the saved judgements, no Jev calls

Runs every draft through the same path as a triage hint — stage-1 candidates
(same project, bugs and tasks, not Cancelled), then Jev's same/related/unrelated
judgment — but keeps **every** verdict and confidence instead of only those above
today's threshold, so any ``T_SAME`` can be scored afterwards. The judgments are
saved to ``fixtures/dataset/sweep_judgments.json``: re-sweeping is free, and a
new Jev model or threshold policy only needs ``--reuse``.

Needs the dataset imported (``import_map.json``), the dev database it was
imported into, and Jev enabled in Settings (the key is read from there, never
printed). One Jev request per draft candidate: roughly 150 drafts × up to 10.
Nothing in the database is changed.
"""

import argparse
import asyncio
import collections
import json
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / "fixtures" / "dataset"
GRID = [round(0.50 + 0.01 * n, 2) for n in range(51)]  # 0.50 … 1.00
PRINT_EVERY = 2  # table rows are 0.02 apart; the chosen row is always shown
# A shown hint should be right about 12 times in 13. 0.90 would pick 0.52 here:
# below ~0.66 Jev's own "same" verdict decides and the curve is flat, so the
# target has to sit on the knee where the confidence floor starts to matter.
PRECISION_TARGET = 0.92
NEGATIVE_KINDS = ("hard_negative", "novel")
POSITIVE_KINDS = ("duplicate", "recurrence")


async def collect(dataset: Path, concurrency: int, limit: int | None) -> dict:
    from app.db.models.issue import IssueStatus, IssueType
    from app.db.session import task_session
    from app.search import jev_settings
    from app.search.constants import SIMILAR_CANDIDATES
    from app.search.jev import JevItem
    from app.search.normalize import normalize, strip_markdown
    from app.search.retrieval import Filters, same_problem_candidates
    from sqlalchemy import select

    from app.db.models.issue import Issue

    mapping = json.loads((dataset / "import_map.json").read_text(encoding="utf-8"))
    fake_of = {v["id"]: f for f, v in mapping.items()}
    project_id = {v["project"]: v["project_id"] for v in mapping.values()}
    drafts = json.loads((dataset / "drafts.json").read_text(encoding="utf-8"))["drafts"]
    if limit:
        drafts = drafts[:limit]
    sem = asyncio.Semaphore(concurrency)
    rows: list[dict] = []
    failures: collections.Counter = collections.Counter()

    async with task_session() as db:
        jev = await jev_settings.client(db)
        if jev is None:
            raise SystemExit("Jev is not enabled in Settings — nothing to sweep.")

    async def one(d: dict) -> None:
        async with sem:
            await judge(d)

    async def judge(d: dict) -> None:
        async with task_session() as db:
            filters = Filters(
                project_id=project_id[d["project_name"]],
                types=[IssueType.bug.value, IssueType.task.value],
                exclude_statuses=[IssueStatus.cancelled.value],
            )
            text = " ".join(p for p in (d["title"], d.get("description") or "") if p)
            hits = (await same_problem_candidates(db, None, text, filters=filters, k=SIMILAR_CANDIDATES))
            if not hits:
                rows.append({"id": d["id"], "kind": d["kind"], "same": d["same"], "cands": []})
                return
            issues = (await db.execute(select(Issue).where(Issue.id.in_([h.issue_id for h in hits])))).scalars().all()
            by_id = {i.id: i for i in issues}
            items = [
                JevItem(id=i.id, title=i.title, description=normalize(strip_markdown(i.description)),
                        type=getattr(i.type, "value", i.type))
                for i in (by_id.get(h.issue_id) for h in hits)
                if i is not None and getattr(i.status, "value", i.status) != IssueStatus.cancelled.value
            ]
        outcome, verdicts = await jev.judge_same(
            d["title"], normalize(strip_markdown(d.get("description") or "")), items, background=True,
        )
        if not outcome.ok:
            failures[outcome.reason] += 1
            return
        rows.append({
            "id": d["id"], "kind": d["kind"], "same": d["same"],
            "cands": [
                {"fake": fake_of.get(i.id, f"?{i.id}"), "verdict": verdicts[i.id][0], "confidence": verdicts[i.id][1]}
                for i in items if i.id in verdicts
            ],
        })
        if len(rows) % 20 == 0:
            print(f"[sweep] {len(rows)}/{len(drafts)}", flush=True)

    await asyncio.gather(*(one(d) for d in drafts))
    return {"rows": rows, "failures": dict(failures), "when": datetime.now(UTC).isoformat(), "drafts": len(drafts)}


def _prf(tp: int, fp: int, fn: int, beta: float = 1.0) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 0.0
    b2 = beta * beta
    f = (1 + b2) * p * r / (b2 * p + r) if p + r else 0.0
    return p, r, f


def score(run: dict, issues: dict[str, dict], t: float) -> dict:
    tp = fp = fn = 0
    found = shown_pos = 0
    pos_drafts = neg_drafts = false_hint_drafts = 0
    by_kind: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])  # kind -> [drafts, drafts with a hint]
    for r in run["rows"]:
        gold = {s for s in r["same"] if issues.get(s, {}).get("status") != "cancelled"}
        picked = sorted(
            (c for c in r["cands"] if c["verdict"] == "same" and c["confidence"] >= t),
            key=lambda c: -c["confidence"],
        )[:3]  # DUPLICATE_HINT_LIMIT
        shown = {c["fake"] for c in picked}
        tp += len(shown & gold)
        fp += len(shown - gold)
        fn += len(gold - shown)
        by_kind[r["kind"]][0] += 1
        by_kind[r["kind"]][1] += bool(shown)
        if r["kind"] in POSITIVE_KINDS and gold:
            pos_drafts += 1
            found += bool(shown & gold)
        if r["kind"] in NEGATIVE_KINDS:
            neg_drafts += 1
            false_hint_drafts += bool(shown)
    p, rec, f1 = _prf(tp, fp, fn)
    _, _, f05 = _prf(tp, fp, fn, beta=0.5)
    return {
        "t": t, "precision": p, "recall": rec, "f1": f1, "f05": f05, "tp": tp, "fp": fp, "fn": fn,
        "found": found / pos_drafts if pos_drafts else 0.0,
        "false_hint": false_hint_drafts / neg_drafts if neg_drafts else 0.0,
        "by_kind": {k: v for k, v in by_kind.items()},
    }


def pick(table: list[dict]) -> dict:
    """The lowest threshold whose pair precision reaches the target — the most
    recall a triager can have while a shown hint is still right 9 times in 10."""
    ok = [s for s in table if s["precision"] >= PRECISION_TARGET and s["tp"] > 0]
    return ok[0] if ok else max(table, key=lambda s: s["f05"])


def report(run: dict, issues: dict[str, dict]) -> tuple[str, float]:
    table = [score(run, issues, t) for t in GRID]
    best = pick(table)
    judged = sum(len(r["cands"]) for r in run["rows"])
    o = [
        f"# Duplicate-hint threshold sweep — {datetime.now(UTC).strftime('%Y-%m-%d')}",
        "",
        f"**Recommendation: `T_SAME = {best['t']:.2f}`** — the lowest threshold at which a shown hint is right "
        f"at least {PRECISION_TARGET:.0%} of the time (precision {best['precision']:.3f}, recall {best['recall']:.3f}; "
        f"{best['found']:.0%} of duplicate/recurrence drafts get a correct hint, {best['false_hint']:.0%} of "
        "hard-negative and novel drafts get a wrong one).",
        "",
        f"Source: the synthetic duplicate dataset ({run['drafts']} drafts, {judged} Jev judgments, judged {run['when'][:10]}); "
        "Jev failures: " + (", ".join(f"{k} ×{v}" for k, v in run["failures"].items()) or "none") + ". "
        "A hint is a `same` verdict at or above the threshold, at most 3 per draft, candidates as for a triage hint "
        "(same project, bugs and tasks, not Cancelled). Re-check against real text with `search_eval stage2 --part similar` "
        "before trusting the last decimal.",
        "",
        "| T_SAME | precision | recall | F1 | correct hint on dup/recurrence drafts | wrong hint on hard-neg/novel drafts | TP | FP | FN |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in table:
        if s['t'] != best['t'] and round(s['t'] * 100) % PRINT_EVERY:
            continue
        mark = " **←**" if s["t"] == best["t"] else ""
        o.append(
            f"| {s['t']:.2f}{mark} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} | {s['found']:.1%} | "
            f"{s['false_hint']:.1%} | {s['tp']} | {s['fp']} | {s['fn']} |"
        )
    o += ["", "## Drafts that get at least one hint, by kind (at the recommended threshold)", "", "| kind | drafts | with a hint |", "|---|---|---|"]
    for k, (n, hit) in sorted(best["by_kind"].items()):
        o.append(f"| {k} | {n} | {hit} ({hit / n:.0%}) |")
    return "\n".join(o) + "\n", best["t"]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="sweep")
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--reuse", action="store_true", help="re-report from the saved judgments; no Jev calls")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, help="only the first N drafts (a cheap smoke test)")
    ap.add_argument("--out", type=Path, help="report path (default: fixtures/dataset/sweep_report.md)")
    args = ap.parse_args(argv)

    saved = args.dataset / "sweep_judgments.json"
    if args.reuse:
        run = json.loads(saved.read_text(encoding="utf-8"))
    else:
        run = asyncio.run(collect(args.dataset, args.concurrency, args.limit))
        if not args.limit:
            saved.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    issues = {i["id"]: i for i in json.loads((args.dataset / "corpus/issues.json").read_text(encoding="utf-8"))}
    text, best = report(run, issues)
    out = args.out or (args.dataset / "sweep_report.md")
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"report → {out}")
    return 0
