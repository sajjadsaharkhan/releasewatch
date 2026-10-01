"""``python -m scripts.search_eval stage1 --dataset DIR [--endpoint URL] --baseline-endpoint URL``

Run inside the api container (it needs the app settings and Postgres with
pg_trgm). Both endpoints are OpenAI-compatible ``/embeddings`` services; the
baseline one must serve ``sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2``
(e.g. a second TEI container), the engine one defaults to the configured
search endpoint (bge-m3). Writes the Markdown report to ``--out``.
"""

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from app.db.session import task_session
from app.search import embeddings

from . import stage1
from .dataset import load
from .index import System, engine_documents, phase1_documents


async def _engine_endpoint(given: str | None) -> str:
    if given:
        return given
    async with task_session() as db:
        return (await embeddings.load_config(db)).endpoint


async def _stage1(args) -> None:
    ds = load(args.dataset)
    engine = System("engine", await _engine_endpoint(args.endpoint), engine_documents)
    baseline = System(
        "phase1",
        args.baseline_endpoint,
        phase1_documents,
        channels=("body",),
        floor=False,
    )
    engine_scores = await stage1.score(ds, engine)
    baseline_scores = await stage1.score(ds, baseline)
    text = stage1.report(
        ds, engine_scores, baseline_scores, host_note=args.host or stage1.default_host_note()
    )
    out = Path(args.out or f"search-eval-stage1-{datetime.now(tz=UTC).date().isoformat()}.md")
    out.write_text(text)
    print(f"Report written to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m scripts.search_eval")
    sub = parser.add_subparsers(dest="command", required=True)
    s1 = sub.add_parser(
        "stage1", help="Jev-off quality (Q1) and latency (Q2) vs the Phase 1 baseline"
    )
    s1.add_argument("--dataset", required=True, help="Directory with corpus/, queries.json")
    s1.add_argument("--endpoint", help="Engine embedding endpoint (default: the configured one)")
    s1.add_argument(
        "--baseline-endpoint", required=True, help="Endpoint serving the Phase 1 MiniLM model"
    )
    s1.add_argument("--out", help="Report path (default: ./search-eval-stage1-<date>.md)")
    s1.add_argument("--host", help="Where this ran, for the report (default: this machine)")
    args = parser.parse_args()
    if args.command == "stage1":
        asyncio.run(_stage1(args))


if __name__ == "__main__":
    main()
