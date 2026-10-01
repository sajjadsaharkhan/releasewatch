"""``python -m scripts.search_eval stage1 --dataset DIR [--endpoint URL] --baseline-endpoint URL``

Run inside the api container (it needs the app settings and Postgres with
pg_trgm). Both endpoints are OpenAI-compatible ``/embeddings`` services; the
baseline one must serve ``sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2``
(e.g. a second TEI container), the engine one defaults to the configured
search endpoint (bge-m3). Writes the Markdown report to ``--out``.

On a host that can't hold both models at once, score them one at a time:
``--phase engine --state DIR``, swap the services, ``--phase baseline --state DIR``,
then ``--phase report --state DIR``.

``stage2 --part search|comments`` (slice 13) needs ``JEV_API_KEY`` in the
environment; ``--part search`` reuses the engine candidates saved by stage1.
"""

import argparse
import asyncio
import json
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
    state = Path(args.state) if args.state else None
    if args.phase != "all" and state is None:
        raise SystemExit("--phase engine|baseline|report needs --state DIR")
    if state:
        state.mkdir(parents=True, exist_ok=True)

    async def run(system: System) -> None:
        scores = await stage1.score(ds, system)
        if state:
            (state / f"{system.name}.json").write_text(json.dumps(scores.to_json()))
        return scores

    engine = baseline = None
    if args.phase in ("all", "engine"):
        engine = await run(
            System("engine", await _engine_endpoint(args.endpoint), engine_documents)
        )
    if args.phase in ("all", "baseline"):
        if not args.baseline_endpoint:
            raise SystemExit("--baseline-endpoint is required to score the baseline")
        baseline = await run(
            System(
                "phase1",
                args.baseline_endpoint,
                phase1_documents,
                channels=("body",),
                floor=False,
            )
        )
    if args.phase in ("engine", "baseline"):
        print(f"Scores saved in {state}")
        return
    if args.phase == "report":
        engine = stage1.Scores.from_json(json.loads((state / "engine.json").read_text()))
        baseline = stage1.Scores.from_json(json.loads((state / "phase1.json").read_text()))
    text = stage1.report(ds, engine, baseline, host_note=args.host or stage1.default_host_note())
    out = Path(args.out or f"search-eval-stage1-{datetime.now(tz=UTC).date().isoformat()}.md")
    out.write_text(text)
    print(f"Report written to {out}")


async def _stage2(args) -> None:
    import os

    from app.search.jev import DEFAULT_MODEL, JevClient

    from . import stage2

    api_key = os.environ.get("JEV_API_KEY")
    if not api_key:
        raise SystemExit(
            "Set JEV_API_KEY in the environment (never pass the key on the command line)."
        )
    jev = JevClient(api_key, args.model or DEFAULT_MODEL)
    ds = load(args.dataset)
    out = Path(
        args.out or f"search-eval-stage2-{args.part}-{datetime.now(tz=UTC).date().isoformat()}.md"
    )
    if args.part == "search":
        if not args.state:
            raise SystemExit("--part search needs --state DIR from `stage1 --phase engine`")
        engine = json.loads((Path(args.state) / "engine.json").read_text())
        run = await stage2.run_search(ds, engine, jev)
        stage2.save(Path(args.state) / "stage2-search.json", run)
        out.write_text(stage2.search_report(ds, run))
    else:
        gold = json.loads((Path(args.dataset) / "comments_labelled.json").read_text())
        run = await stage2.run_comments(ds, gold, jev)
        if args.state:
            stage2.save(Path(args.state) / "stage2-comments.json", run)
        out.write_text(stage2.comments_report(run))
    print(f"Report written to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m scripts.search_eval")
    sub = parser.add_subparsers(dest="command", required=True)
    s1 = sub.add_parser(
        "stage1", help="Jev-off quality (Q1) and latency (Q2) vs the Phase 1 baseline"
    )
    s1.add_argument("--dataset", required=True, help="Directory with corpus/, queries.json")
    s1.add_argument("--endpoint", help="Engine embedding endpoint (default: the configured one)")
    s1.add_argument("--baseline-endpoint", help="Endpoint serving the Phase 1 MiniLM model")
    s1.add_argument(
        "--phase",
        choices=["all", "engine", "baseline", "report"],
        default="all",
        help="Score one system at a time (a host that can't hold both models), then 'report'",
    )
    s1.add_argument("--state", help="Directory for per-phase scores (with --phase)")
    s1.add_argument("--out", help="Report path (default: ./search-eval-stage1-<date>.md)")
    s1.add_argument("--host", help="Where this ran, for the report (default: this machine)")
    s2 = sub.add_parser(
        "stage2", help="Jev on: rerank + T_RELEVANT sweep (Q4), comment labels (Q5)"
    )
    s2.add_argument("--part", choices=["search", "comments"], required=True)
    s2.add_argument("--dataset", required=True)
    s2.add_argument("--state", help="The stage1 --state DIR (search reads engine.json from it)")
    s2.add_argument("--model", help="Jev model (default: the pinned jev-1.13.0)")
    s2.add_argument("--out", help="Report path")
    args = parser.parse_args()
    if args.command == "stage1":
        asyncio.run(_stage1(args))
    elif args.command == "stage2":
        asyncio.run(_stage2(args))


if __name__ == "__main__":
    main()
