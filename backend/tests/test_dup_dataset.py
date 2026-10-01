"""The committed duplicate dataset stays valid and in sync with its authored clusters.

Pure file checks (backend/scripts/dup_dataset): `build` must reproduce the committed
files byte for byte, and `validate` must report no failure. Run `python -m
scripts.dup_dataset build` after editing a cluster.
"""

import json

from scripts.dup_dataset import build, validate


def test_committed_dataset_matches_the_clusters():
    data = build.build(build.load_clusters())
    committed = {
        "corpus/issues.json": data["issues"],
        "corpus/comments.json": data["comments"],
        "drafts.json": {"drafts": data["drafts"]},
        "queries.json": {"queries": data["queries"], "no_match": data["no_match"]},
        "gold.json": data["gold"],
    }
    for name, expected in committed.items():
        on_disk = json.loads((build.OUT / name).read_text(encoding="utf-8"))
        assert on_disk == expected, f"{name} is stale — run `python -m scripts.dup_dataset build`"


def test_dataset_passes_validation():
    errors, stats = validate.check()
    assert errors == []
    assert stats["issues"] >= 150 and stats["drafts"] >= 100
