# ruff: noqa: E501 — long Markdown lines
"""Write ``fixtures/dataset/scenarios.md``: a hand-test script for the imported dataset.

Run by ``import`` (and on its own: ``python -m scripts.dup_dataset guide``). It picks a few
drafts / queries of each kind and prints what to type, which user to sign in as, and which
issue keys the engine should (or should not) surface, using the keys of *your* database
from ``import_map.json``.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / "fixtures" / "dataset"
PASSWORD_NOTE = "password `dataset-pass-123` unless you passed `--password`"


def _keys(mapping: dict, ids: list[str]) -> str:
    return ", ".join(f"**{mapping[i]['key']}** ({mapping[i]['status']})" for i in ids) or "nothing"


def _pick(drafts: list[dict], n: int, **match) -> list[dict]:
    """The first ``n`` drafts matching, spread across projects (round-robin)."""
    rows = [
        d
        for d in drafts
        if all(
            (d.get(k) == v) if not isinstance(v, (list, set)) else bool(set(d.get(k, [])) & set(v))
            for k, v in match.items()
        )
    ]
    by_project: dict[str, list[dict]] = {}
    for d in rows:
        by_project.setdefault(d["project_name"], []).append(d)
    out: list[dict] = []
    while len(out) < n and any(by_project.values()):
        for name in list(by_project):
            if by_project[name] and len(out) < n:
                out.append(by_project[name].pop(0))
    return out


def _draft_block(d: dict, mapping: dict, expect: str) -> list[str]:
    out = [
        f"- **{d['id']}** · {d['kind']} · {d['persona']} · {d['difficulty']} · project **{d['project_name']}**",
        f"  - Title: `{d['title']}`",
    ]
    if d["description"]:
        out.append(f"  - Description: `{d['description']}`")
    for n, s in enumerate(d.get("reproduction_steps") or [], 1):
        out.append(
            f"  - Step {n}: {s['description']} → expected *{s['expected_result']}*, "
            f"actual *{s['actual_result']}*"
        )
    out.append(f"  - {expect}")
    if d.get("note"):
        out.append(f"  - Note: {d['note']}")
    return out


def write(dataset: Path = DEFAULT_DATASET) -> Path:
    mapping_path = dataset / "import_map.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    issues = {
        i["id"]: i for i in json.loads((dataset / "corpus/issues.json").read_text(encoding="utf-8"))
    }
    for fid, v in mapping.items():
        v["status"] = issues[fid]["status"]
    drafts = json.loads((dataset / "drafts.json").read_text(encoding="utf-8"))["drafts"]
    qdata = json.loads((dataset / "queries.json").read_text(encoding="utf-8"))

    out = [
        "# Hand-test script for the duplicate dataset",
        "",
        f"Sign in as `dd-qa`, `dd-developer`, `dd-pm`, `dd-cto`, `dd-admin` or `dd-support` ({PASSWORD_NOTE}). "
        "Projects are `Chat`, `Limsa`, `Dano`, `StudentPanel`, `Releasewatch` (slugs `dd-…`).",
        "",
        "## 1 · Tech create form — *Possibly the same* (needs Jev on)",
        "",
        "Open **New issue** in the project, type the title and description, wait ~1 s. "
        "**Same problem** rows are expected for the keys listed; nothing should be marked *Same problem* "
        "for hard negatives or novel drafts. Cancelled issues are never suggested.",
        "",
    ]
    for d in _pick(drafts, 3, kind="duplicate", difficulty="easy") + _pick(
        drafts, 3, kind="duplicate", difficulty="hard"
    ):
        out += _draft_block(d, mapping, f"Expect Same problem: {_keys(mapping, d['same'])}")
    out += [
        "",
        "### Recurrence (the original is Done)",
        "",
        "A Done original means Merge returns it to *To do* with a new production / release-QA cycle.",
        "",
    ]
    for d in _pick(drafts, 3, kind="recurrence"):
        out += _draft_block(d, mapping, f"Expect Same problem: {_keys(mapping, d['same'])}")
    out += ["", "### Hard negatives — same area, different fault", ""]
    for d in _pick(drafts, 4, kind="hard_negative"):
        out += _draft_block(
            d, mapping, f"Expect NO *Same problem*; maybe Related: {_keys(mapping, d['related'])}"
        )
    out += ["", "### Novel — nothing should match", ""]
    for d in _pick(drafts, 3, kind="novel"):
        out += _draft_block(d, mapping, "Expect no *Same problem*")
    out += ["", "### Only the comments carry the signal (known limit, engine PRD S4)", ""]
    for d in _pick(drafts, 2, signal_fields=["comments"]):
        out += _draft_block(
            d,
            mapping,
            f"Duplicate detection reads title/description/steps only, so a miss on "
            f"{_keys(mapping, d['same'])} is expected",
        )
    out += [
        "",
        "## 2 · Support form — *Similar reports* (sign in as `dd-support`, needs Jev on)",
        "",
        "`#/support/new`, pick the project, fill the title and the «شرح مشکل» field. Only **open support "
        "reports of that project** are offered.",
        "",
    ]
    for d in _pick(drafts, 4, kind="duplicate", persona="support"):
        support_same = [
            i
            for i in d["same"]
            if issues[i]["source"] == "support" and issues[i]["status"] != "done"
        ]
        out += _draft_block(
            d, mapping, f"Expect (open support reports only): {_keys(mapping, support_same)}"
        )
    out += [
        "",
        "## 3 · Triage hints (sign in as `dd-qa`, Jev on, **Triage** page)",
        "",
        "Each New bug below duplicates the listed original; its row should be marked *Possible duplicate* "
        "and *Merge into this* should name the original.",
        "",
    ]
    gold = json.loads((dataset / "gold.json").read_text(encoding="utf-8"))
    shown = 0
    for c in gold:
        for pair in c["duplicate_pairs"]:
            a, b = pair["issue"], pair["duplicate_of"]
            if issues[a]["status"] == "new" and issues[a]["type"] == "bug" and shown < 8:
                out.append(
                    f"- **{mapping[a]['key']}** «{issues[a]['title']}» → **{mapping[b]['key']}** "
                    f"({issues[b]['status']}) · cluster {c['cluster_id']}"
                )
                shown += 1
    out += [
        "",
        "## 4 · Search (command palette / Search page)",
        "",
        "Type the query inside the right project (`⌘K` or `/search`). The listed issues are the *grade-2* answers.",
        "",
    ]
    seen: set[str] = set()
    for q in qdata["queries"]:
        style = q["cat"][0]
        if style in seen:
            continue
        seen.add(style)
        gold2 = [i for i, g in q["rel"].items() if g == 2]
        out.append(f"- `{q['q']}` ({', '.join(q['cat'])}) → {_keys(mapping, gold2)}")
    out += ["", "No-match queries — the page should say *No matches* (or show almost nothing):", ""]
    out += [f"- `{q['q']}`" for q in qdata["no_match"][:6]]
    path = dataset / "scenarios.md"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path
