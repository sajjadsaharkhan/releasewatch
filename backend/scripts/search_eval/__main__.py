"""``python -m scripts.search_eval stage1 --dataset DIR [--endpoint URL] --baseline-endpoint URL``

Run inside the api container (it needs the app settings and Postgres with
pg_trgm). Both endpoints are OpenAI-compatible ``/embeddings`` services; the
baseline one must serve ``sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2``
(e.g. a second TEI container), the engine one defaults to the configured
search endpoint (bge-m3). Writes the Markdown report to ``--out``.

On a host that can't hold both models at once, score them one at a time:
``--phase engine --state DIR``, swap the services, ``--phase baseline --state DIR``,
then ``--phase report --state DIR``.
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
        engine = await run(System("engine", await _engine_endpoint(args.endpoint), engine_documents))
    if args.phase in ("all", "baseline"):
        if not args.baseline_endpoint:
            raise SystemExit("--baseline-endpoint is required to score the baseline")
        baseline = await run(System(
            "phase1", args.baseline_endpoint, phase1_documents, channels=("body",), floor=False,
        ))
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m scripts.search_eval")
    sub = parser.add_subparsers(dest="command", required=True)
    s1 = sub.add_parser(
        "stage1", help="Jev-off quality (Q1) and latency (Q2) vs the Phase 1 baseline"
    )
    s1.add_argument("--dataset", required=True, help="Directory with corpus/, queries.json")
    s1.add_argument("--endpoint", help="Engine embedding endpoint (default: the configured one)")
    s1.add_argument(
        "--baseline-endpoint", help="Endpoint serving the Phase 1 MiniLM model"
    )
    s1.add_argument(
        "--phase", choices=["all", "engine", "baseline", "report"], default="all",
        help="Score one system at a time (a host that can't hold both models), then 'report'",
    )
    s1.add_argument("--state", help="Directory for per-phase scores (with --phase)")
    s1.add_argument("--out", help="Report path (default: ./search-eval-stage1-<date>.md)")
    s1.add_argument("--host", help="Where this ran, for the report (default: this machine)")
    args = parser.parse_args()
    if args.command == "stage1":
        asyncio.run(_stage1(args))


if __name__ == "__main__":
    main()
