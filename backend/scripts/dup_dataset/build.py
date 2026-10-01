"""Flatten the authored clusters (fixtures/clusters/*.json) into the dataset files.

Outputs, next to ``fixtures/`` in ``fixtures/dataset/`` (the shape the stage-1 /
stage-2 harness in ``scripts/search_eval`` loads, plus the extras this dataset adds):

    corpus/issues.json      every fake issue, with its reproduction steps, cURL path, labels
    corpus/comments.json    every comment (the `talk` channel's input)
    drafts.json             new reports to type into the create / support form
    queries.json            search queries + no-match queries
    gold.json              the clusters: who duplicates whom, and why

Authoring format (one cluster):
    {"id": "c01", "project": "Chat", "area": "reactions", "note": "...",
     "members": [{"k": "a", "type": "bug", "st": "done", "sev": "major", "role": "qa",
                  "src": "internal", "t": "title", "d": "description",
                  "steps": [["step", "expected", "actual"]], "curl": "/api/v1/...",
                  "labels": ["chat"], "days": 40, "dupe_of": "a",
                  "cm": [["developer", "comment body"], ["qa", "internal note", 1]]}],
     "drafts": [{"k": "1", "kind": "duplicate", "p": "support", "t": "...", "d": "...",
                 "steps": [...], "same": ["a"], "rel": [], "cat": ["colloquial"],
                 "sig": ["description"], "diff": "easy"}],
     "queries": [{"q": "...", "cat": ["short"], "rel": {"a": 2, "b": 1}}],
     "rel_clusters": ["c02"]}

`same`/`rel` name members of this cluster by key; ``rel_clusters`` adds every
non-cancelled member of those clusters to the draft's ``related`` automatically.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUT = FIXTURES / "dataset"
ANCHOR = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

PROJECTS = ["Chat", "Limsa", "Dano", "StudentPanel", "Releasewatch"]


def load_clusters() -> list[dict]:
    """Every ``clusters/*.json``, then ``patches.json`` — extra drafts / queries
    appended to an existing cluster: ``[{"cluster": "c01", "drafts": [...], "queries": [...]}]``."""
    clusters: list[dict] = []
    for path in sorted((FIXTURES / "clusters").glob("*.json")):
        clusters.extend(json.loads(path.read_text(encoding="utf-8")))
    patch_file = FIXTURES / "patches.json"
    if patch_file.exists():
        by_id = {c["id"]: c for c in clusters}
        for patch in json.loads(patch_file.read_text(encoding="utf-8")):
            target = by_id[patch["cluster"]]
            target.setdefault("drafts", []).extend(patch.get("drafts", []))
            target.setdefault("queries", []).extend(patch.get("queries", []))
    return clusters


def _steps(raw) -> list[dict]:
    return [
        {"description": s[0], "expected_result": s[1], "actual_result": s[2]} for s in (raw or [])
    ]


def build(clusters: list[dict]) -> dict:
    issues, comments = [], []
    gid: dict[tuple[str, str], str] = {}  # (cluster id, member key) → global id
    for c in clusters:
        for m in c["members"]:
            gid[(c["id"], m["k"])] = f"f{len(gid) + 1:03d}"

    status_of: dict[str, str] = {}
    members_of: dict[str, list[str]] = {}
    for c in clusters:
        for m in c["members"]:
            members_of.setdefault(c["id"], []).append(gid[(c["id"], m["k"])])

    for c in clusters:
        for m in c["members"]:
            iid = gid[(c["id"], m["k"])]
            status_of[iid] = m["st"]
            created = ANCHOR - timedelta(days=m["days"], hours=(len(issues) * 7) % 23)
            issues.append(
                {
                    "id": iid,
                    "project_name": c["project"],
                    "project_id": PROJECTS.index(c["project"]) + 1,
                    "type": m.get("type", "bug"),
                    "source": m.get("src", "internal"),
                    "status": m["st"],
                    "severity": m.get("sev", "major"),
                    "labels": m.get("labels", []),
                    "reporter_role": m.get("role", "qa"),
                    "title": m["t"],
                    "description": m.get("d", ""),
                    "reproduction_steps": _steps(m.get("steps")),
                    "curl_path": m.get("curl"),
                    "created_at": created.isoformat(),
                    "cluster_id": c["id"],
                    "duplicate_of": gid[(c["id"], m["dupe_of"])] if m.get("dupe_of") else None,
                    "cancel_reason": "duplicate" if m["st"] == "cancelled" else None,
                    "in_stream": m["st"]
                    in ("done", "in_progress", "to_review", "in_review", "todo", "blocked"),
                }
            )
            for n, cm in enumerate(m.get("cm", [])):
                comments.append(
                    {
                        "id": f"fc{len(comments) + 1:03d}",
                        "issue_id": iid,
                        "author_role": cm[0],
                        "is_internal": bool(cm[2]) if len(cm) > 2 else False,
                        "body": cm[1],
                        "created_at": (created + timedelta(hours=3 + n * 5)).isoformat(),
                    }
                )

    drafts, queries, no_match = [], [], []
    for c in clusters:
        rel_cluster_ids = [i for rc in c.get("rel_clusters", []) for i in members_of.get(rc, [])]
        for d in c.get("drafts", []):
            same = [gid[(c["id"], k)] for k in d.get("same", [])]
            same = [i for i in same if status_of[i] != "cancelled"]
            related = [gid[(c["id"], k)] for k in d.get("rel", [])] + rel_cluster_ids
            related = [
                i for i in dict.fromkeys(related) if i not in same and status_of[i] != "cancelled"
            ]
            base = (
                gid[(c["id"], d["base"])]
                if d.get("base")
                else (same[0] if same else (related[0] if related else None))
            )
            drafts.append(
                {
                    "id": f"n{len(drafts) + 1:03d}",
                    "cluster_id": c["id"],
                    "kind": d["kind"],
                    "persona": d["p"],
                    "project_id": PROJECTS.index(c["project"]) + 1,
                    "project_name": c["project"],
                    "title": d["t"],
                    "description": d.get("d", ""),
                    "reproduction_steps": _steps(d.get("steps")),
                    "base_issue": base,
                    "same": same,
                    "related": related,
                    "cat": d.get("cat", []),
                    "signal_fields": d.get("sig", []),
                    "difficulty": d.get("diff", "medium"),
                    "note": d.get("note", ""),
                }
            )
        for q in c.get("queries", []):
            rel = {gid[(c["id"], k)]: g for k, g in q["rel"].items()}
            base = next((i for i, g in rel.items() if g == 2), None)
            queries.append(
                {
                    "id": f"q{len(queries) + 1:03d}",
                    "q": q["q"],
                    "cat": q["cat"],
                    "base_issue": base,
                    "rel": rel,
                    "cluster_id": c["id"],
                }
            )
    extra = (
        json.loads((FIXTURES / "no_match.json").read_text(encoding="utf-8"))
        if (FIXTURES / "no_match.json").exists()
        else []
    )
    for n, q in enumerate(extra, 1):
        no_match.append({"id": f"x{n:03d}", "q": q})

    gold = [
        {
            "cluster_id": c["id"],
            "project": c["project"],
            "area": c.get("area", ""),
            "note": c.get("note", ""),
            "members": {m["k"]: gid[(c["id"], m["k"])] for m in c["members"]},
            "duplicate_pairs": [
                {"issue": gid[(c["id"], m["k"])], "duplicate_of": gid[(c["id"], m["dupe_of"])]}
                for m in c["members"]
                if m.get("dupe_of")
            ],
            "related_clusters": c.get("rel_clusters", []),
        }
        for c in clusters
    ]
    return {
        "issues": issues,
        "comments": comments,
        "drafts": drafts,
        "queries": queries,
        "no_match": no_match,
        "gold": gold,
    }


def write(data: dict) -> None:
    (OUT / "corpus").mkdir(parents=True, exist_ok=True)

    def dump(path, obj):
        (OUT / path).write_text(
            json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )

    dump("corpus/issues.json", data["issues"])
    dump("corpus/comments.json", data["comments"])
    dump("drafts.json", {"drafts": data["drafts"]})
    dump("queries.json", {"queries": data["queries"], "no_match": data["no_match"]})
    dump("gold.json", data["gold"])


def main() -> int:
    data = build(load_clusters())
    write(data)
    print(
        f"{len(data['issues'])} issues, {len(data['comments'])} comments, "
        f"{len(data['drafts'])} drafts, {len(data['queries'])} queries "
        f"(+{len(data['no_match'])} no-match) → {OUT}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
