"""Validate the built dataset (fixtures/dataset/). Exit 1 on any failure; stdlib only.

Same rules as the evaluation dataset spec (§6) where they apply, plus this
dataset's own: clusters, duplicate chains, statuses the app knows.
"""

import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
DS = HERE / "fixtures" / "dataset"

STATUSES = {
    "new",
    "needs_info",
    "todo",
    "in_progress",
    "to_review",
    "in_review",
    "done",
    "blocked",
    "cancelled",
    "rejected",
}
KINDS = {"duplicate", "recurrence", "hard_negative", "novel"}
PERSONAS = {"support", "qa", "developer"}
ROLES = {"qa", "developer", "pm", "support", "cto", "admin"}
CATS = {
    "short",
    "colloquial",
    "codeswitch",
    "translit",
    "typo",
    "fa2en",
    "en2fa",
    "symptom",
    "identifier",
    "cross_lingual",
}
SIGNALS = {"title", "description", "repro", "curl", "comments"}
DIFFS = {"easy", "medium", "hard"}
DONE = {"done"}

PII = {
    "phone": re.compile(r"(?<!\d)(?:\+98|0098|0)9\d{9}(?!\d)"),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "national_id": re.compile(r"(?<!\d)\d{10}(?!\d)"),
    "card": re.compile(r"(?<!\d)(?:\d{4}[- ]?){3}\d{4}(?!\d)|\bIR\d{24}\b"),
}
_LETTERS = str.maketrans(
    {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "ة": "ه",
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        **{chr(0x06F0 + i): str(i) for i in range(10)},
        **{chr(0x0660 + i): str(i) for i in range(10)},
    }
)
ZWNJ = chr(0x200C)
_MARKS = re.compile(
    "["
    + chr(0x064B)
    + "-"
    + chr(0x065F)
    + chr(0x0670)
    + chr(0x0640)
    + chr(0x200D)
    + chr(0x200E)
    + chr(0x200F)
    + "]"
)


def tokens(text: str) -> list[str]:
    t = unicodedata.normalize("NFC", text or "").translate(_LETTERS).lower()
    t = _MARKS.sub("", t).replace(ZWNJ, " ")
    return re.findall(r"[\w/]+", t)


def shares_run(a: str, b: str, n: int = 4) -> bool:
    ta, tb = tokens(a), tokens(b)
    grams = {tuple(tb[i : i + n]) for i in range(len(tb) - n + 1)}
    return any(tuple(ta[i : i + n]) in grams for i in range(len(ta) - n + 1))


def lang(t: str) -> str:
    fa = len(re.findall(r"[؀-ۿ]", t))
    en = len(re.findall(r"[A-Za-z]", t))
    s = fa + en or 1
    return "fa" if fa / s > 0.8 else "en" if en / s > 0.8 else "mixed"


def issue_text(i: dict) -> str:
    steps = " ".join(
        f"{s['description']} {s['expected_result']} {s['actual_result']}"
        for s in i["reproduction_steps"]
    )
    return f"{i['title']} {i['description']} {steps}"


def text_of(x: dict) -> str:
    steps = " ".join(
        f"{s['description']} {s['expected_result']} {s['actual_result']}"
        for s in x.get("reproduction_steps", [])
    )
    return f"{x.get('title') or x.get('q') or ''} {x.get('description', '')} {steps}"


def check() -> tuple[list[str], dict]:
    errors: list[str] = []
    err = errors.append
    issues = json.loads((DS / "corpus/issues.json").read_text(encoding="utf-8"))
    comments = json.loads((DS / "corpus/comments.json").read_text(encoding="utf-8"))
    drafts = json.loads((DS / "drafts.json").read_text(encoding="utf-8"))["drafts"]
    qd = json.loads((DS / "queries.json").read_text(encoding="utf-8"))
    queries, no_match = qd["queries"], qd["no_match"]
    by_id = {i["id"]: i for i in issues}
    if len(by_id) != len(issues):
        err("duplicate issue ids")

    for i in issues:
        iid = i["id"]
        if i["status"] not in STATUSES:
            err(f"{iid}: bad status {i['status']}")
        if i["reporter_role"] not in ROLES:
            err(f"{iid}: bad role")
        if i["type"] not in ("bug", "task"):
            err(f"{iid}: bad type")
        if i["source"] not in ("internal", "support"):
            err(f"{iid}: bad source")
        if i["source"] == "support" and i["type"] != "bug":
            err(f"{iid}: support items are bugs")
        if not i["title"].strip():
            err(f"{iid}: empty title")
        if i["duplicate_of"] and i["duplicate_of"] not in by_id:
            err(f"{iid}: unknown duplicate_of")
        if i["duplicate_of"] and by_id[i["duplicate_of"]]["cluster_id"] != i["cluster_id"]:
            err(f"{iid}: duplicate_of crosses clusters")
        if i["status"] == "cancelled" and not i["duplicate_of"]:
            err(f"{iid}: cancelled without duplicate_of")
        if i["status"] == "cancelled" and i["type"] != "bug":
            err(f"{iid}: cancelled non-bug")
        for s in i["reproduction_steps"]:
            if not all(s.get(k) for k in ("description", "expected_result", "actual_result")):
                err(f"{iid}: incomplete repro step")
    for c in comments:
        if c["issue_id"] not in by_id:
            err(f"{c['id']}: unknown issue")
        if c["author_role"] not in ROLES:
            err(f"{c['id']}: bad author role")
        if not c["body"].strip():
            err(f"{c['id']}: empty comment")

    seen = set()
    for d in drafts:
        did = d["id"]
        if did in seen:
            err(f"{did}: duplicate id")
        seen.add(did)
        if d["kind"] not in KINDS:
            err(f"{did}: bad kind")
        if d["persona"] not in PERSONAS:
            err(f"{did}: bad persona")
        if set(d["cat"]) - CATS:
            err(f"{did}: bad cat {set(d['cat']) - CATS}")
        if set(d["signal_fields"]) - SIGNALS:
            err(f"{did}: bad signal")
        if d["difficulty"] not in DIFFS:
            err(f"{did}: bad difficulty")
        for i in d["same"] + d["related"] + ([d["base_issue"]] if d["base_issue"] else []):
            if i not in by_id:
                err(f"{did}: unknown issue {i}")
        if set(d["same"]) & set(d["related"]):
            err(f"{did}: same ∩ related")
        if d["kind"] in ("duplicate", "recurrence") and not d["same"]:
            err(f"{did}: empty same")
        if d["kind"] in ("hard_negative", "novel") and d["same"]:
            err(f"{did}: same must be empty")
        if d["kind"] == "recurrence" and not any(
            by_id[i]["status"] in DONE for i in d["same"] if i in by_id
        ):
            err(f"{did}: recurrence needs a Done issue in same")
        for i in d["same"]:
            if i in by_id and by_id[i]["status"] == "cancelled":
                err(f"{did}: cancelled issue in same")
            if i in by_id and by_id[i]["project_name"] != d["project_name"]:
                err(f"{did}: same crosses projects")
            if i in by_id and shares_run(text_of(d), issue_text(by_id[i])):
                err(f"{did}: shares 4+ tokens with its same issue {i}")
        if not d["title"].strip():
            err(f"{did}: empty title")

    for q in queries:
        qid = q["id"]
        if set(q["cat"]) - CATS or not q["cat"]:
            err(f"{qid}: bad cat")
        if not any(g == 2 for g in q["rel"].values()):
            err(f"{qid}: no grade-2")
        for i, g in q["rel"].items():
            if i not in by_id:
                err(f"{qid}: unknown issue {i}")
            elif g == 2 and shares_run(q["q"], issue_text(by_id[i])):
                err(f"{qid}: shares 4+ tokens with {i}")
    for q in no_match:
        if not q["q"].strip():
            err(f"{q['id']}: empty no-match")

    blob = json.dumps([issues, comments, drafts, queries], ensure_ascii=False)
    for name, pat in PII.items():
        for m in pat.finditer(blob):
            err(f"unmasked {name}: …{blob[max(0, m.start() - 20) : m.end() + 5]}…")

    c = collections.Counter
    stats = {
        "issues": len(issues),
        "comments": len(comments),
        "drafts": len(drafts),
        "queries": len(queries),
        "no_match": len(no_match),
        "clusters": len({i["cluster_id"] for i in issues}),
        "issues_per_project": c(i["project_name"] for i in issues),
        "issues_status": c(i["status"] for i in issues),
        "issues_type": c(i["type"] for i in issues),
        "issues_source": c(i["source"] for i in issues),
        "issues_language": c(lang(i["title"] + " " + i["description"]) for i in issues),
        "issues_with_repro": sum(1 for i in issues if i["reproduction_steps"]),
        "issues_with_curl": sum(1 for i in issues if i["curl_path"]),
        "issues_with_comments": len({x["issue_id"] for x in comments}),
        "issues_cancelled_dupes": sum(1 for i in issues if i["status"] == "cancelled"),
        "draft_kind": c(d["kind"] for d in drafts),
        "draft_persona": c(d["persona"] for d in drafts),
        "draft_difficulty": c(d["difficulty"] for d in drafts),
        "draft_language": c(lang(d["title"] + " " + d["description"]) for d in drafts),
        "draft_signal": c(s for d in drafts for s in d["signal_fields"]),
        "query_cat": c(t for q in queries for t in q["cat"]),
        "query_language": c(lang(q["q"]) for q in queries),
    }
    return errors, stats


def write_manifest(stats: dict) -> None:
    lines = [
        "# Duplicate dataset — MANIFEST",
        "",
        "Generated by `python -m scripts.dup_dataset validate --manifest`. Synthetic: every issue,",
        "comment, draft and query was written for this dataset (no production text).",
        "",
        "## Distributions",
        "",
    ]
    for key, value in stats.items():
        shown = dict(value.most_common()) if isinstance(value, collections.Counter) else value
        lines.append(f"- **{key}:** {shown}")
    (DS / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    errors, stats = check()
    for e in errors:
        print("FAIL", e)
    if "--stats" in sys.argv:
        for k, v in stats.items():
            print(f"{k}: {dict(v) if isinstance(v, collections.Counter) else v}")
    if "--manifest" in sys.argv and not errors:
        write_manifest(stats)
        print("MANIFEST.md written")
    print(f"{len(errors)} failure(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
