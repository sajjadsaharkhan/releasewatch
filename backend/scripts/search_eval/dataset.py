"""Load an evaluation dataset directory (search-eval-dataset-spec.md §7)."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace


@dataclass
class Query:
    id: str
    q: str
    cats: list[str]
    #: issue id → grade (2 = the one being looked for, 1 = related).
    rel: dict[str, int] = field(default_factory=dict)


@dataclass
class Draft:
    """A new-issue draft (dataset spec §4.2): someone writing a report."""

    id: str
    kind: str  # duplicate | recurrence | hard_negative | novel
    persona: str
    project_id: int | None
    title: str
    description: str
    #: Gold: the issues that are truly the same problem / merely related.
    same: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    cats: list[str] = field(default_factory=list)


@dataclass
class Dataset:
    path: Path
    #: Engine-shaped items (``build_documents`` input), by corpus id.
    items: dict[str, SimpleNamespace]
    #: Comments per corpus issue id, engine-shaped.
    comments: dict[str, list[SimpleNamespace]]
    queries: list[Query]
    no_match: list[Query]
    drafts: list[Draft] = field(default_factory=list)


def _item(raw: dict) -> SimpleNamespace:
    path = raw.get("curl_path")
    return SimpleNamespace(
        id=str(raw["id"]),
        title=raw.get("title") or "",
        description=raw.get("description"),
        reproduction_steps=raw.get("reproduction_steps") or [],
        # The corpus keeps only the cURL URL path (§2); give documents.py a
        # command it can parse so the engine's own path extraction runs.
        curl_command=f"curl https://corpus.invalid{path}" if path else None,
        labels=raw.get("labels") or [],
        project_id=raw.get("project_id"),
        status=raw.get("status"),
    )


def load(path: str | Path) -> Dataset:
    root = Path(path)
    issues = json.loads((root / "corpus" / "issues.json").read_text())
    items = {str(r["id"]): _item(r) for r in issues}

    comments: dict[str, list[SimpleNamespace]] = {}
    comments_file = root / "corpus" / "comments.json"
    if comments_file.exists():
        for n, c in enumerate(json.loads(comments_file.read_text())):
            comments.setdefault(str(c["issue_id"]), []).append(
                SimpleNamespace(
                    id=n + 1,  # documents.py keys labels by an int id
                    corpus_id=str(c["id"]),
                    body=c.get("body") or "",
                    is_internal=bool(c.get("is_internal")),
                )
            )

    raw = json.loads((root / "queries.json").read_text())
    queries = [
        Query(
            id=q["id"],
            q=q["q"],
            cats=list(q.get("cat") or []),
            rel={str(k): int(v) for k, v in q["rel"].items()},
        )
        for q in raw.get("queries", [])
    ]
    no_match = [Query(id=q["id"], q=q["q"], cats=["no_match"]) for q in raw.get("no_match", [])]

    drafts: list[Draft] = []
    drafts_file = root / "drafts.json"
    if drafts_file.exists():
        for d in json.loads(drafts_file.read_text()).get("drafts", []):
            drafts.append(
                Draft(
                    id=d["id"],
                    kind=d["kind"],
                    persona=d.get("persona") or "",
                    project_id=d.get("project_id"),
                    title=d.get("title") or "",
                    description=d.get("description") or "",
                    same=[str(i) for i in d.get("same") or []],
                    related=[str(i) for i in d.get("related") or []],
                    cats=list(d.get("cat") or []),
                )
            )
    return Dataset(
        path=root, items=items, comments=comments, queries=queries,
        no_match=no_match, drafts=drafts,
    )
