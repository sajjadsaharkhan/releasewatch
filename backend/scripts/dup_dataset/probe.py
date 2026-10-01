# ruff: noqa: E501 — long Markdown lines
"""Try the imported dataset against a running API and report how the engine does.

    docker compose exec api python -m scripts.dup_dataset probe
    docker compose exec api python -m scripts.dup_dataset probe --k 5 --out /tmp/report.md

Needs ``import`` to have run (it reads ``fixtures/dataset/import_map.json``). Signs in as
``dd-qa`` (tech), ``dd-support`` and ``dd-admin`` and calls the real HTTP endpoints, so it
exercises what the UI calls:

* every search query → ``GET /api/v1/search`` twice: ``mode=page`` (the Search page; Jev
  reranks when it is on) and ``mode=palette`` (stage 1 only, never Jev);
* every no-match query, in every dataset project → how many results the Search page shows;
* every draft → ``POST /api/v1/search/similar`` (``context=tech``) with **title + description**,
  exactly what the create form sends today; drafts that have reproduction steps are sent a
  second time with the steps folded into the description (what engine principle S4 intends);
* every Support-persona draft → ``context=support`` as ``dd-support`` (the Support form);
* every New bug → ``GET /issues/{id}/duplicate-hints`` (the triage *Possible duplicate* block).

Jev is a paid call: with Jev on, one probe makes roughly 600 of them. Nothing is changed in
the database. The report goes to ``fixtures/dataset/probe_report.md`` (or ``--out``).
"""

import argparse
import asyncio
import collections
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / "fixtures" / "dataset"
POSITIVE = ("duplicate", "recurrence")
KINDS = ("duplicate", "recurrence", "hard_negative", "novel")


def _steps(d: dict) -> str:
    return "\n".join(
        f"{n}. {s['description']} — {s['expected_result']} — {s['actual_result']}"
        for n, s in enumerate(d.get("reproduction_steps") or [], 1)
    )


async def _nothing() -> None:
    return None


def _avg(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _f(x: float) -> str:
    return "—" if x != x else f"{x:.3f}"  # NaN → dash


def same_sets(gold: list[dict], issues: dict[str, dict]) -> dict[str, set[str]]:
    """Corpus issue → the other issues that are the same problem (its duplicate
    cluster, linked through ``duplicate_pairs``), minus cancelled ones."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            x = parent[x]
        return x

    for c in gold:
        for p in c["duplicate_pairs"]:
            parent[find(p["issue"])] = find(p["duplicate_of"])
    groups: dict[str, set[str]] = collections.defaultdict(set)
    for x in list(parent):
        groups[find(x)].add(x)
    out: dict[str, set[str]] = {}
    for members in groups.values():
        for x in members:
            out[x] = {y for y in members if y != x and issues[y]["status"] != "cancelled"}
    return out


def relation(draft: dict, fid: str, issues: dict, gold_by_cluster: dict) -> str:
    """How a wrongly-`same` candidate relates to the draft, for the report."""
    if fid in draft.get("related", []):
        return "gold related"
    cand = issues.get(fid, {})
    if cand.get("cluster_id") == draft["cluster_id"]:
        return "same cluster, not in gold same"
    rel = gold_by_cluster.get(draft["cluster_id"], {}).get("related_clusters", [])
    if cand.get("cluster_id") in rel:
        return "sibling cluster (hard negative)"
    return "unrelated"


async def run(base: str, dataset: Path, password: str, k: int, concurrency: int, out: Path | None) -> int:
    mapping_file = dataset / "import_map.json"
    if not mapping_file.exists():
        print("No import_map.json — run `import` first.", file=sys.stderr)
        return 1
    mapping = json.loads(mapping_file.read_text(encoding="utf-8"))
    fake_of = {v["id"]: f for f, v in mapping.items()}
    issues = {i["id"]: i for i in json.loads((dataset / "corpus/issues.json").read_text(encoding="utf-8"))}
    queries = json.loads((dataset / "queries.json").read_text(encoding="utf-8"))
    drafts = json.loads((dataset / "drafts.json").read_text(encoding="utf-8"))["drafts"]
    gold = json.loads((dataset / "gold.json").read_text(encoding="utf-8"))
    gold_by_cluster = {c["cluster_id"]: c for c in gold}
    same_of = same_sets(gold, issues)
    project_id = {v["project"]: v["project_id"] for v in mapping.values()}
    key = lambda fid: mapping[fid]["key"] if fid in mapping else fid  # noqa: E731

    async def login(http: httpx.AsyncClient, user: str) -> dict:
        r = await http.post("/api/v1/auth/login", json={"username": user, "password": password})
        if r.status_code != 200:
            raise SystemExit(f"Login as {user} failed ({r.status_code}): {r.text[:200]}")
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    async with httpx.AsyncClient(base_url=base, timeout=120) as http:
        tech, support, admin = [await login(http, u) for u in ("dd-qa", "dd-support", "dd-admin")]
        jev_on = bool((await http.get("/api/v1/features", headers=tech)).json().get("jev_enabled"))
        status = (await http.get("/api/v1/settings/search", headers=admin)).json()
        sem = asyncio.Semaphore(concurrency)

        async def call(method: str, url: str, headers: dict, **kw) -> httpx.Response:
            async with sem:
                resp = await http.request(method, url, headers=headers, **kw)
            if resp.status_code >= 400:
                resp.raise_for_status()
            return resp

        async def search(q: str, pid: int, mode: str) -> list[str]:
            body = (await call("GET", "/api/v1/search", tech, params={"q": q, "scope": "project", "project_id": pid, "mode": mode})).json()
            return [fake_of.get(x["issue_id"], f"?{x['issue_id']}") for x in body["results"]]

        async def similar(d: dict, headers: dict, context: str, with_steps: bool) -> dict | None:
            desc = "\n\n".join(x for x in (d.get("description") or "", _steps(d) if with_steps else "") if x)
            resp = await call("POST", "/api/v1/search/similar", headers, json={
                "context": context, "project_id": project_id[d["project_name"]],
                "title": d["title"], "description": desc or None,
            })
            if resp.status_code == 204:
                return None  # Jev off or failing: the panel shows nothing
            return {fake_of.get(x["issue"]["id"], "?"): (x["verdict"], x["confidence"]) for x in resp.json()["items"]}

        async def hints(fid: str) -> list[tuple[str, float]]:
            body = (await call("GET", f"/api/v1/issues/{mapping[fid]['id']}/duplicate-hints", tech)).json()
            return [(fake_of.get(h["candidate_id"], "?"), h["confidence"]) for h in body["hints"]]

        qs = queries["queries"]
        q_page, q_pal = await asyncio.gather(
            asyncio.gather(*(search(q["q"], project_id[issues[q["base_issue"]]["project_name"]], "page") for q in qs)),
            asyncio.gather(*(search(q["q"], project_id[issues[q["base_issue"]]["project_name"]], "palette") for q in qs)),
        )
        nm_pairs = [(q, name) for q in queries["no_match"] for name in sorted(project_id)]
        nm = await asyncio.gather(*(search(q["q"], project_id[name], "page") for q, name in nm_pairs))
        s1 = await asyncio.gather(*(search(f"{d['title']} {d['description']}", project_id[d["project_name"]], "palette") for d in drafts))
        sim = await asyncio.gather(*(similar(d, tech, "tech", False) if jev_on else _nothing() for d in drafts))
        stepped = [d for d in drafts if d.get("reproduction_steps")]
        sim_steps = await asyncio.gather(*(similar(d, tech, "tech", True) if jev_on else _nothing() for d in stepped))
        sup_drafts = [d for d in drafts if d["persona"] == "support"]
        sim_sup = await asyncio.gather(*(similar(d, support, "support", False) if jev_on else _nothing() for d in sup_drafts))
        new_bugs = [f for f, i in issues.items() if i["status"] == "new" and i["type"] == "bug" and f in mapping]
        hint_rows = await asyncio.gather(*(hints(f) for f in new_bugs))

    # ── scoring ────────────────────────────────────────────────────────────
    def q_score(got: list[str], q: dict) -> dict:
        g = {i for i, v in q["rel"].items() if v == 2}
        rank = next((n for n, i in enumerate(got, 1) if i in g), None)
        return {"recall": len(g & set(got[:k])) / len(g), "hit": bool(g & set(got[:k])), "rr": 1 / rank if rank else 0.0}

    page = [q_score(g, q) for g, q in zip(q_page, qs, strict=True)]
    pal = [q_score(g, q) for g, q in zip(q_pal, qs, strict=True)]

    def judged(d: dict, sj: dict | None) -> dict:
        sj = sj or {}
        same = {i for i, (v, _) in sj.items() if v == "same"}
        return {
            "found": bool(same & set(d["same"])),
            "false": sorted(same - set(d["same"])),
            "shown": len(sj),
            "related": sum(1 for v, _ in sj.values() if v == "related"),
        }

    rows = [
        {"d": d, "s1": got, "j": judged(d, sj), "sj": sj}
        for d, got, sj in zip(drafts, s1, sim, strict=True)
    ]
    by_kind = collections.defaultdict(list)
    for r in rows:
        by_kind[r["d"]["kind"]].append(r)

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    jev = status.get("jev") or {}
    try:
        from app.search import constants as C  # inside the api container

        consts = f"T_FLOOR {C.T_FLOOR} · T_SAME {C.T_SAME} · T_RELATED {C.T_RELATED} · SIMILAR_LIMIT {C.SIMILAR_LIMIT} · DUPLICATE_HINT_LIMIT {C.DUPLICATE_HINT_LIMIT}"
    except Exception:  # noqa: BLE001 — run outside the container
        consts = "(engine constants not importable here)"
    o = [
        f"# Dataset probe — {len(qs)} queries, {len(drafts)} drafts, k={k}",
        "",
        f"- Run: {now} against `{base}`",
        f"- Embedding model: `{status.get('embed_model')}` (endpoint `{status.get('embedding_endpoint')}`)",
        f"- Jev: {'on, model `' + str(jev.get('model')) + '`' if jev_on else 'off — no same-problem judgement; stage-1 only'}",
        f"- Engine constants: {consts}",
        f"- Index: {status.get('index', {}).get('indexed')}/{status.get('index', {}).get('total')} items on the current model",
        "",
        "## Search queries (project scope)",
        "",
        "`page` is what the Search page shows (Jev reranks when on); `palette` is stage 1 alone.",
        "",
        "| style | n | page R@k | page Hit@k | page MRR | palette R@k | palette Hit@k |",
        "|---|---|---|---|---|---|---|",
        f"| **all** | {len(qs)} | **{_f(_avg(r['recall'] for r in page))}** | **{_f(_avg(r['hit'] for r in page))}** | **{_f(_avg(r['rr'] for r in page))}** "
        f"| {_f(_avg(r['recall'] for r in pal))} | {_f(_avg(r['hit'] for r in pal))} |",
    ]
    cats = sorted({c for q in qs for c in q["cat"]})
    for c in cats:
        idx = [n for n, q in enumerate(qs) if c in q["cat"]]
        o.append(
            f"| {c} | {len(idx)} | {_f(_avg(page[n]['recall'] for n in idx))} | {_f(_avg(page[n]['hit'] for n in idx))} "
            f"| {_f(_avg(page[n]['rr'] for n in idx))} | {_f(_avg(pal[n]['recall'] for n in idx))} | {_f(_avg(pal[n]['hit'] for n in idx))} |"
        )
    shown_nm = [(q, name, got) for (q, name), got in zip(nm_pairs, nm, strict=True) if got]
    o += [
        "",
        "## No-match queries",
        "",
        f"{len(queries['no_match'])} queries × {len(project_id)} projects = {len(nm_pairs)} Search-page calls. "
        f"Mean results shown **{_avg(len(x) for x in nm):.2f}**; **{len(nm_pairs) - len(shown_nm)}/{len(nm_pairs)}** showed nothing.",
        "",
    ]
    for q, name, got in shown_nm:
        o.append(f"- `{q['q']}` in {name} → {', '.join(key(i) + ' «' + issues.get(i, {}).get('title', '?')[:60] + '»' for i in got[:3])}")

    o += [
        "",
        "## Drafts — tech create form *Possibly the same* (title + description, as the form sends)",
        "",
        "Stage-1 hit = a gold `same` issue in the stage-1 top k. *Same found* = Jev called a gold `same` "
        "issue *Same problem*. *False same* = Jev called any other issue *Same problem*.",
        "",
        "| kind | n | stage-1 hit@k | panel rows | Jev same found | Jev false same | related rows |",
        "|---|---|---|---|---|---|---|",
    ]
    for kind in KINDS:
        rs = by_kind.get(kind, [])
        if not rs:
            continue
        pos = kind in POSITIVE
        o.append(
            f"| {kind} | {len(rs)} | {_f(_avg(bool(set(r['d']['same']) & set(r['s1'][:k])) for r in rs)) if pos else '—'} "
            f"| {_avg(r['j']['shown'] for r in rs):.1f} | {_f(_avg(r['j']['found'] for r in rs)) if pos and jev_on else '—'} "
            f"| {_f(_avg(bool(r['j']['false']) for r in rs)) if jev_on else '—'} | {_avg(r['j']['related'] for r in rs):.1f} |"
        )
    pos_rows = [r for r in rows if r["d"]["kind"] in POSITIVE]
    if jev_on:
        for label, keyf in (
            ("difficulty", lambda d: [d["difficulty"]]),
            ("persona", lambda d: [d["persona"]]),
            ("signal field", lambda d: d["signal_fields"] or ["(none)"]),
        ):
            groups = collections.defaultdict(list)
            for r in pos_rows:
                for g in keyf(r["d"]):
                    groups[g].append(r)
            o += ["", f"Duplicate + recurrence drafts by {label}:", "", f"| {label} | n | Jev same found | false same |", "|---|---|---|---|"]
            for g, rs in sorted(groups.items()):
                o.append(f"| {g} | {len(rs)} | {_f(_avg(r['j']['found'] for r in rs))} | {_f(_avg(bool(r['j']['false']) for r in rs))} |")

    if jev_on and stepped:
        st = [judged(d, sj) for d, sj in zip(stepped, sim_steps, strict=True)]
        base = [next(r["j"] for r in rows if r["d"]["id"] == d["id"]) for d in stepped]
        sp = [n for n, d in enumerate(stepped) if d["kind"] in POSITIVE]
        o += [
            "",
            "### With reproduction steps (what S4 intends; the form cannot send them today)",
            "",
            f"{len(stepped)} drafts carry steps. Positives: same found {_f(_avg(base[n]['found'] for n in sp))} without steps → "
            f"**{_f(_avg(st[n]['found'] for n in sp))}** with steps. False same (all): "
            f"{_f(_avg(bool(b['false']) for b in base))} → {_f(_avg(bool(s['false']) for s in st))}.",
        ]

    if jev_on and sup_drafts:
        sup_rows = []
        for d, sj in zip(sup_drafts, sim_sup, strict=True):
            want = {i for i in d["same"] if issues[i]["source"] == "support" and issues[i]["status"] not in ("done", "cancelled")}
            same = {i for i, (v, _) in (sj or {}).items() if v == "same"}
            sup_rows.append((d, want, same, sj or {}))
        with_target = [x for x in sup_rows if x[1]]
        o += [
            "",
            "## Support form — *Similar reports* (`context=support`, as `dd-support`)",
            "",
            "Only open support reports of the project are candidates, so the expected set is gold `same` ∩ open support reports.",
            "",
            f"- Support drafts: {len(sup_rows)}; with an open support report to find: {len(with_target)}",
            f"- Found it: **{_f(_avg(bool(w & s) for _, w, s, _ in with_target))}**",
            f"- Showed a wrong report as similar: **{_f(_avg(bool(s - w) for _, w, s, _ in sup_rows))}**",
            f"- Showed anything when nothing should match: {_f(_avg(bool(s) for _, w, s, _ in sup_rows if not w))}",
        ]
        bad = [x for x in sup_rows if x[2] - x[1]]
        for d, w, s, _ in bad:
            o.append(f"  - {d['id']} [{d['kind']}] «{d['title'][:70]}» showed {', '.join(key(i) for i in sorted(s - w))}; want {', '.join(key(i) for i in sorted(w)) or 'nothing'}")

    # triage hints
    h_eval = []
    for fid, hs in zip(new_bugs, hint_rows, strict=True):
        want = same_of.get(fid, set())
        got = {c for c, _ in hs}
        h_eval.append((fid, want, got))
    dup_new = [x for x in h_eval if x[1]]
    all_hints = [(f, c) for f, _, got in h_eval for c in got]
    o += [
        "",
        "## Triage — *Possible duplicate* hints on New bugs",
        "",
        f"- New bugs: {len(h_eval)}; that have a same-problem twin in the corpus: {len(dup_new)}",
        f"- Hint recall (twin among the hints): **{_f(_avg(bool(w & g) for _, w, g in dup_new))}**",
        f"- Hint precision (hints that point at a twin): **{_f(_avg(c in same_of.get(f, set()) for f, c in all_hints))}** of {len(all_hints)} hints",
        f"- New bugs with no twin that still got a hint: {sum(1 for _, w, g in h_eval if not w and g)}",
    ]

    # misses
    o += ["", "## Misses — open these in the UI", "", f"Search queries whose gold issue is not in the Search page's top {k}:", ""]
    for q, r, got in zip(qs, page, q_page, strict=True):
        if not r["hit"]:
            want = ", ".join(key(i) for i, v in q["rel"].items() if v == 2)
            o.append(f"- `{q['q']}` ({','.join(q['cat'])}) → want {want}; got {', '.join(key(i) for i in got[:3]) or 'nothing'}")
    if jev_on:
        o += ["", "Duplicate / recurrence drafts where Jev found no gold `same` issue:", ""]
        for r in pos_rows:
            if not r["j"]["found"]:
                d = r["d"]
                s1hit = "in" if set(d["same"]) & set(r["s1"][:k]) else "NOT in"
                verdicts = ", ".join(f"{key(i)} {v} {c:.2f}" for i, (v, c) in r["sj"].items()) or "nothing shown"
                o.append(
                    f"- {d['id']} [{d['kind']}/{d['difficulty']}/{','.join(d['signal_fields']) or '-'}] «{d['title'][:80]}» "
                    f"→ want {', '.join(key(i) for i in d['same'])} (stage-1 top {k}: {s1hit}); panel: {verdicts}"
                )
        o += ["", "Drafts where Jev called a non-gold issue *Same problem*:", ""]
        for r in rows:
            for fid in r["j"]["false"]:
                d = r["d"]
                o.append(
                    f"- {d['id']} [{d['kind']}] «{d['title'][:70]}» → {key(fid)} «{issues.get(fid, {}).get('title', '?')[:70]}» "
                    f"({r['sj'][fid][1]:.2f}; {relation(d, fid, issues, gold_by_cluster)})"
                )
    o += ["", "New bugs with a twin but no hint pointing at it:", ""]
    for f, w, g in dup_new:
        if not w & g:
            o.append(f"- {key(f)} «{issues[f]['title'][:70]}» → want {', '.join(key(i) for i in sorted(w))}; hints {', '.join(key(i) for i in sorted(g)) or 'none'}")
    wrong = [(f, c) for f, c in all_hints if c not in same_of.get(f, set())]
    if wrong:
        o += ["", "Hints that point at something other than a twin:", ""]
        for f, c in wrong:
            o.append(f"- {key(f)} «{issues[f]['title'][:60]}» → {key(c)} «{issues.get(c, {}).get('title', '?')[:60]}»")

    report = "\n".join(o) + "\n"
    path = out or dataset / "probe_report.md"
    path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Report written to {path}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="dup_dataset probe")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--password", default="dataset-pass-123")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--out", type=Path, default=None, help="report path (default fixtures/dataset/probe_report.md)")
    a = ap.parse_args(argv)
    return asyncio.run(run(a.base_url, a.dataset, a.password, a.k, a.concurrency, a.out))
