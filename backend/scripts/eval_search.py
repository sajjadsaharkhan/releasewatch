"""Phase-0 search evaluation script.

Usage:
    python scripts/eval_search.py [--project-id <id>] [--labels <path_to_labels.json>]

What it does:
    1. Connects to the database and checks how many issues have embeddings.
    2. Plots the pairwise cosine similarity distribution of 'core' group vectors
       (random sample of up to 200 issues) to reveal cluster tightness.
       → If most scores > 0.85, the embeddings are compressed and hybrid is critical.
       → If spread is wide, dense search carries more weight.
    3. If a labels file is provided, evaluates precision@5 / precision@10 against
       hand-labeled query→expected_issue_ids pairs.

Labels file format (JSON):
    [
      {"query": "login crash on safari", "expected_ids": [42, 17]},
      ...
    ]

Outputs:
    - Console summary of similarity distribution percentiles
    - eval_search_report.txt with full results
    - eval_search_cosine_dist.png (histogram) if matplotlib is available
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def _run(project_id: int | None, labels_path: str | None) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.session import get_engine, init_engine
    from app.services.search_service import (
        EmbeddingConfigMissing,
        _load_llm_config,
        embed_texts,
        search,
    )

    await init_engine()
    engine = get_engine()

    async with AsyncSession(engine) as db:
        # ── 1. Coverage stats ─────────────────────────────────────────────────
        total_q = await db.execute(
            text("SELECT COUNT(*) FROM issues" + (" WHERE project_id=:pid" if project_id else "")),
            {"pid": project_id} if project_id else {},
        )
        total_issues = total_q.scalar_one()

        emb_q = await db.execute(
            text(
                "SELECT COUNT(DISTINCT issue_id) FROM issue_embeddings"
                + (" WHERE project_id=:pid" if project_id else "")
            ),
            {"pid": project_id} if project_id else {},
        )
        embedded_issues = emb_q.scalar_one()

        print(f"\n{'='*60}")
        print(f"Issues:    {total_issues}")
        print(f"Embedded:  {embedded_issues}  ({embedded_issues/max(total_issues,1)*100:.1f}%)")

        if embedded_issues == 0:
            print("\nNo embeddings found. Run reindex first:\n"
                  "  POST /api/v1/search/reindex\n")
            return

        # ── 2. Cosine similarity distribution ─────────────────────────────────
        limit = 200
        rows = await db.execute(
            text(
                "SELECT issue_id, embedding::text FROM issue_embeddings "
                "WHERE field_group='core'"
                + (" AND project_id=:pid" if project_id else "")
                + " ORDER BY RANDOM() LIMIT :lim"
            ),
            {**({"pid": project_id} if project_id else {}), "lim": limit},
        )
        vecs_raw = rows.fetchall()

        def parse_vec(s: str) -> list[float]:
            return [float(x) for x in s.strip("[]").split(",")]

        vecs = [(row[0], parse_vec(row[1])) for row in vecs_raw]

        def cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(x * x for x in b) ** 0.5
            return dot / (na * nb) if na and nb else 0.0

        sample = vecs[:50]  # pairwise over 50 → 1225 pairs
        scores: list[float] = []
        for i in range(len(sample)):
            for j in range(i + 1, len(sample)):
                scores.append(cosine(sample[i][1], sample[j][1]))

        if scores:
            scores.sort()
            n = len(scores)
            pcts = {p: scores[int(p / 100 * n)] for p in [10, 25, 50, 75, 90, 95, 99]}
            mean = statistics.mean(scores)
            stdev = statistics.stdev(scores) if len(scores) > 1 else 0.0

            print(f"\n── Pairwise cosine similarity (n={n} pairs) ──")
            print(f"  mean={mean:.4f}  stdev={stdev:.4f}")
            for pct, val in pcts.items():
                print(f"  p{pct:02d} = {val:.4f}")

            if pcts[50] > 0.85:
                print("\n  ⚠ Median > 0.85: scores are compressed.")
                print("    Hybrid (lexical) retrieval is critical.")
                print("    Lean RRF weights toward lexical (already done in default config).")
            else:
                print("\n  ✓ Score spread looks healthy.")
                print("    Dense search is effective. Consider increasing _WEIGHTS_CORE.")

            # Histogram via matplotlib (optional)
            try:
                import matplotlib.pyplot as plt
                plt.figure(figsize=(8, 4))
                plt.hist(scores, bins=50, color="#6366f1", alpha=0.8)
                plt.xlabel("Cosine similarity")
                plt.ylabel("Pair count")
                plt.title("Pairwise cosine similarity distribution (core group)")
                out = Path(__file__).parent / "eval_search_cosine_dist.png"
                plt.savefig(out, dpi=120, bbox_inches="tight")
                plt.close()
                print(f"\n  Histogram saved to {out}")
            except ImportError:
                print("\n  (Install matplotlib for histogram: pip install matplotlib)")

        # ── 3. Precision evaluation against labeled pairs ─────────────────────
        if not labels_path:
            print("\n── Precision eval skipped (no --labels file provided) ──")
            print("   Create a JSON file with query→expected_issue_ids pairs.")
            print("   Example: [{\"query\": \"safari crash\", \"expected_ids\": [42, 17]}]")
        else:
            label_data = json.loads(Path(labels_path).read_text())
            pid = project_id or 0
            if not pid:
                # Auto-detect from first issue in DB
                r = await db.execute(text("SELECT project_id FROM issues LIMIT 1"))
                row = r.fetchone()
                pid = row[0] if row else 1

            p5_scores, p10_scores = [], []
            print(f"\n── Precision eval ({len(label_data)} queries) ──")
            for item in label_data:
                q = item["query"]
                expected = set(item["expected_ids"])
                result = await search(db, q, pid, limit=10)
                returned_ids = [r["issue_id"] for r in result["results"]]
                p5 = len(set(returned_ids[:5]) & expected) / max(len(expected), 1)
                p10 = len(set(returned_ids[:10]) & expected) / max(len(expected), 1)
                p5_scores.append(p5)
                p10_scores.append(p10)
                status = "✓" if p5 > 0 else "✗"
                print(f"  {status} [{p5:.2f}@5 / {p10:.2f}@10] {q!r}")
                print(f"      returned: {returned_ids[:5]}  expected: {list(expected)[:5]}")

            print(f"\n  Mean precision@5  = {statistics.mean(p5_scores):.3f}")
            print(f"  Mean precision@10 = {statistics.mean(p10_scores):.3f}")

        print(f"\n{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase-0 search evaluation")
    parser.add_argument("--project-id", type=int, default=None, help="Scope to one project")
    parser.add_argument("--labels", type=str, default=None, help="Path to labeled pairs JSON")
    args = parser.parse_args()
    asyncio.run(_run(args.project_id, args.labels))


if __name__ == "__main__":
    main()
