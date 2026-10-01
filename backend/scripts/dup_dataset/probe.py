"""Try the imported dataset against a running API and report how the engine does.

    docker compose exec api python -m scripts.dup_dataset probe
    docker compose exec api python -m scripts.dup_dataset probe --k 5

Needs ``import`` to have run (it reads ``fixtures/dataset/import_map.json``). Signs in as
``dd-qa`` and calls the real HTTP endpoints, so it exercises what the UI calls:

* every search query → ``GET /api/v1/search`` (project scope) → Recall@k / Hit@k / MRR by style;
* every no-match query → how many results survive the floor (lower is better);
* every draft → stage-1 candidates for ``title + description`` (+ repro steps), the same
  text the create form sends, and, if Jev is on, ``POST /api/v1/search/similar``:
  duplicates/recurrences should surface a ``same`` issue, hard negatives and novel drafts none.

The report is written to ``fixtures/dataset/probe_report.md``. Misses list the keys to open in
the UI by hand. Nothing is changed in the database.
"""

import argparse
import asyncio
import collections
import json
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / "fixtures" / "dataset"


def _text(d: dict) -> tuple[str, str]:
    steps = "\n".join(
        f"{n}. {s['description']} — expected: {s['expected_result']}; actual: {s['actual_result']}"
        for n, s in enumerate(d.get("reproduction_steps") or [], 1)
    )
    desc = "\n\n".join(x for x in (d.get("description") or "", steps) if x)
    return d["title"], desc


async def run(base: str, dataset: Path, password: str, k: int, concurrency: int) -> int:
    mapping_file = dataset / "import_map.json"
    if not mapping_file.exists():
        print("No import_map.json — run `import` first.", file=sys.stderr)
        return 1
    mapping = json.loads(mapping_file.read_text(encoding="utf-8"))
    fake_of = {v["id"]: f for f, v in mapping.items()}
    issues = {
        i["id"]: i for i in json.loads((dataset / "corpus/issues.json").read_text(encoding="utf-8"))
    }
    queries = json.loads((dataset / "queries.json").read_text(encoding="utf-8"))
    drafts = json.loads((dataset / "drafts.json").read_text(encoding="utf-8"))["drafts"]
    project_id = {
        name: next(v["project_id"] for v in mapping.values() if v["project"] == name)
        for name in {v["project"] for v in mapping.values()}
    }

    async with httpx.AsyncClient(base_url=base, timeout=60) as http:
        r = await http.post("/api/v1/auth/login", json={"username": "dd-qa", "password": password})
        if r.status_code != 200:
            print(f"Login failed ({r.status_code}): {r.text[:200]}", file=sys.stderr)
            return 1
        http.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        feats = (await http.get("/api/v1/features")).json()
        jev_on = bool(feats.get("jev_enabled"))
        sem = asyncio.Semaphore(concurrency)

        async def search(q: str, pid: int) -> list[str]:
            async with sem:
                resp = await http.get(
                    "/api/v1/search", params={"q": q, "scope": "project", "project_id": pid}
                )
            resp.raise_for_status()
            body = resp.json()
            return [fake_of.get(x["issue_id"], f"?{x['issue_id']}") for x in body["results"]]

        async def similar(d: dict) -> dict[str, tuple[str, float]] | None:
            title, desc = _text(d)
            async with sem:
                resp = await http.post(
                    "/api/v1/search/similar",
                    json={
                        "context": "tech",
                        "project_id": project_id[d["project_name"]],
                        "title": title,
                        "description": desc,
                    },
                )
            if resp.status_code == 204:
                return None
            resp.raise_for_status()
            return {
                fake_of.get(x["issue"]["id"], "?"): (x["verdict"], x["confidence"])
                for x in resp.json()["items"]
            }

        # ── search queries ────────────────────────────────────────────────
        q_rows = []
        res = await asyncio.gather(
            *(
                search(q["q"], project_id[issues[q["base_issue"]]["project_name"]])
                for q in queries["queries"]
            )
        )
        for q, got in zip(queries["queries"], res, strict=True):
            gold = {i for i, g in q["rel"].items() if g == 2}
            top = got[:k]
            rank = next((n for n, i in enumerate(got, 1) if i in gold), None)
            q_rows.append(
                {
                    "q": q,
                    "recall": len(gold & set(top)) / len(gold),
                    "hit": bool(gold & set(top)),
                    "rr": 1 / rank if rank else 0.0,
                    "got": top,
                    "gold": sorted(gold),
                }
            )
        proj_default = next(iter(project_id.values()))
        nm = await asyncio.gather(
            *(search(q["q"], pid) for q in queries["no_match"] for pid in [proj_default])
        )

        # ── drafts ────────────────────────────────────────────────────────
        s1 = await asyncio.gather(
            *(search(" ".join(_text(d)), project_id[d["project_name"]]) for d in drafts)
        )
        sim = (
            await asyncio.gather(*(similar(d) for d in drafts)) if jev_on else [None] * len(drafts)
        )

    def avg(xs):
        xs = list(xs)
        return sum(xs) / len(xs) if xs else 0.0

    out = [
        f"# Dataset probe — {len(queries['queries'])} queries, {len(drafts)} drafts, k={k}",
        f"API `{base}` · Jev {'on' if jev_on else 'off (no same-problem judgement; stage-1 only)'}",
        "",
        "## Search queries (project scope)",
        "",
        f"Recall@{k} **{avg(r['recall'] for r in q_rows):.3f}** · "
        f"Hit@{k} **{avg(r['hit'] for r in q_rows):.3f}** · "
        f"MRR **{avg(r['rr'] for r in q_rows):.3f}**",
        "",
        "| style | n | Recall@k | Hit@k |",
        "|---|---|---|---|",
    ]
    by_cat = collections.defaultdict(list)
    for r in q_rows:
        for c in r["q"]["cat"]:
            by_cat[c].append(r)
    for c, rows in sorted(by_cat.items()):
        out.append(
            f"| {c} | {len(rows)} | {avg(r['recall'] for r in rows):.3f} "
            f"| {avg(r['hit'] for r in rows):.3f} |"
        )
    out += [
        "",
        f"No-match queries: mean results shown **{avg(len(x) for x in nm):.1f}** "
        f"(0 is ideal; {sum(1 for x in nm if not x)}/{len(nm)} showed nothing).",
        "",
        "## Drafts (what the create form would suggest)",
        "",
        "| kind | n | stage-1 hit@k (same in top k) | stage-1 shown "
        "| Jev: same found | Jev: false `same` |",
        "|---|---|---|---|---|---|",
    ]
    by_kind = collections.defaultdict(list)
    for d, got, sj in zip(drafts, s1, sim, strict=True):
        by_kind[d["kind"]].append((d, got, sj))
    for kind in ("duplicate", "recurrence", "hard_negative", "novel"):
        rows = by_kind.get(kind, [])
        if not rows:
            continue
        positive = kind in ("duplicate", "recurrence")
        hit = (
            avg(bool(set(d["same"]) & set(got[:k])) for d, got, _ in rows)
            if positive
            else float("nan")
        )
        shown = avg(len(got[:k]) for _, got, _ in rows)
        if jev_on:
            found = (
                avg(
                    any(v[0] == "same" and i in d["same"] for i, v in (sj or {}).items())
                    for d, _, sj in rows
                )
                if positive
                else float("nan")
            )
            false = avg(
                any(v[0] == "same" and i not in d["same"] for i, v in (sj or {}).items())
                for d, _, sj in rows
            )
            jev_cols = f"{found:.3f} | {false:.3f}"
        else:
            jev_cols = "— | —"
        out.append(f"| {kind} | {len(rows)} | {hit:.3f} | {shown:.1f} | {jev_cols} |")

    out += [
        "",
        "## Misses — open these in the UI",
        "",
        "Search queries whose gold issue is not in the top k:",
        "",
    ]
    for r in [x for x in q_rows if not x["hit"]][:40]:
        gold = ", ".join(f"{mapping[g]['key']}" for g in r["gold"])
        out.append(f"- `{r['q']['q']}` ({','.join(r['q']['cat'])}) → want {gold}")
    out += ["", "Duplicate / recurrence drafts with no `same` issue in the stage-1 top k:", ""]
    for d, got, _ in by_kind.get("duplicate", []) + by_kind.get("recurrence", []):
        if not set(d["same"]) & set(got[:k]):
            want = ", ".join(mapping[i]["key"] for i in d["same"])
            out.append(
                f"- {d['id']} [{d['kind']}/{d['difficulty']}/"
                f"{','.join(d['signal_fields']) or '-'}] «{d['title']}» → want {want}"
            )
    report = "\n".join(out) + "\n"
    (dataset / "probe_report.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="dup_dataset probe")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--password", default="dataset-pass-123")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--concurrency", type=int, default=8)
    a = ap.parse_args(argv)
    return asyncio.run(run(a.base_url, a.dataset, a.password, a.k, a.concurrency))
