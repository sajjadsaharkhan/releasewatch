"""Import the built dataset into a (development) Releasewatch database.

    docker compose exec api python -m scripts.dup_dataset import
    docker compose exec api python -m scripts.dup_dataset import --wipe     # re-import from scratch

What it creates (never touches anything else, except ``--wipe``, which deletes the
``dd-*`` projects it made earlier — their releases, issues, comments and search rows cascade):

* users ``dd-qa``, ``dd-developer``, ``dd-product_manager``, ``dd-support``, ``dd-cto``, ``dd-admin``
  (one password for all, ``--password``, default ``dataset-pass-123``; re-applied to existing
  ``dd-*`` users so the printed password is always the one that works);
* five projects, slugs ``dd-chat``, ``dd-limsa``, ``dd-dano``, ``dd-studentpanel``,
  ``dd-releasewatch``, each with a support template (so the Support form works) and three
  Releases beside its Stream: one **shipped**, one **in QA**, one **in planning**;
* every issue (type, source, status, severity → priority, labels, reproduction steps,
  cURL path, timestamps shifted so the newest issue is "an hour ago"), placed in a container
  by ``placement`` below, with its cycle replayed through the cycle service (picked up,
  submitted, verified), its comments, and a ``filed`` timeline event; ``cancelled``
  duplicates are linked to their original;
* then each issue is indexed for search (``index_item_now``) and, when Jev is on, the
  duplicate hints of every New bug are computed;
* finally a smoke check calls the pages the UI loads (Stream / release items and board,
  the issue list, one issue page per project) and fails loudly on any error.

``fixtures/dataset/import_map.json`` records fake id → database id; ``probe`` reads it.
Seeds are *additive*: nothing is wiped unless you pass ``--wipe``.
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.models  # noqa: F401 — registers every model's metadata
from app.config import settings
from app.core.auth import get_password_hash
from app.db.models.issue import Issue, IssueSource, IssueStatus, IssueType, Priority, issue_key
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.project import Project
from app.db.models.release import GoNogoStatus, Release, ReleaseKind, ReleaseStatus
from app.db.models.support_template import SupportTemplate, SupportTemplateField
from app.db.models.user import User, UserRole

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / "fixtures" / "dataset"
SLUG_PREFIX = "dd-"
LABEL = "dataset-dup"
PRIORITY = {
    "blocker": Priority.critical,
    "critical": Priority.critical,
    "major": Priority.high,
    "minor": Priority.low,
    "enhancement": Priority.medium,
}
#: Statuses that live in a container; New / Needs info / Rejected / Cancelled do not.
IN_CONTAINER = {"todo", "in_progress", "to_review", "in_review", "done", "blocked"}
ROLE_NAMES = {
    "qa": "QA",
    "developer": "Developer",
    "product_manager": "Product Manager",
    "support": "Support",
    "cto": "CTO",
    "admin": "Admin",
}
#: Per project: (shipped, in QA, planning) versions.
VERSIONS = {
    "Chat": ("v3.11.0", "v3.12.0", "v3.13.0"),
    "Limsa": ("v1.7.0", "v1.8.0", "v1.9.0"),
    "Dano": ("v5.2.0", "v5.3.0", "v5.4.0"),
    "StudentPanel": ("v2.0.0", "v2.1.0", "v2.2.0"),
    "Releasewatch": ("v0.9.0", "v0.10.0", "v0.11.0"),
}
SHIPPED_DAYS_AGO = 21
#: The lifecycle each container status is replayed through, from To do.
PATH = {
    "todo": [],
    "blocked": [],
    "in_progress": [IssueStatus.in_progress],
    "to_review": [IssueStatus.in_progress, IssueStatus.to_review],
    "in_review": [IssueStatus.in_progress, IssueStatus.in_review],
    "done": [IssueStatus.in_progress, IssueStatus.in_review, IssueStatus.done],
}


def _slug(name: str) -> str:
    return SLUG_PREFIX + name.lower()


def placement(raw: dict, completed_at: datetime | None, shipped_at: datetime) -> str | None:
    """Which container an issue lives in: ``shipped`` / ``qa`` / ``planning`` / ``stream``,
    or None (New, Needs info, Cancelled — the app keeps those out of containers).

    * Done before the ship date → the shipped release (a merge returns it to production);
      a later Done bug → the release in QA (a merge returns it to release QA); a Done task
      → the Stream.
    * Open urgent bugs (blocker / critical) → the release in QA; To do tasks → planning;
      everything else → the Stream.
    """
    if raw["status"] not in IN_CONTAINER:
        return None
    if raw["status"] == "done":
        if completed_at is not None and completed_at < shipped_at:
            return "shipped"
        return "qa" if raw["type"] == "bug" else "stream"
    if raw["type"] == "bug" and raw["severity"] in ("blocker", "critical"):
        return "qa"
    if raw["type"] == "task" and raw["status"] == "todo":
        return "planning"
    return "stream"


async def _wipe(db: AsyncSession) -> int:
    ids = (
        (await db.execute(select(Project.id).where(Project.slug.like(SLUG_PREFIX + "%"))))
        .scalars()
        .all()
    )
    if ids:
        await db.execute(delete(Project).where(Project.id.in_(ids)))
        await db.commit()
    return len(ids)


async def _users(db: AsyncSession, password: str) -> dict[str, User]:
    users: dict[str, User] = {}
    hashed = get_password_hash(password)
    for role, label in ROLE_NAMES.items():
        username = f"dd-{role}"
        user = await db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(
                name=f"Dataset {label}",
                username=username,
                role=UserRole(role),
                is_active=True,
            )
        user.hashed_password = hashed
        db.add(user)
        users[role] = user
    await db.flush()
    return users


async def _project(
    db: AsyncSession, name: str, users: dict[str, User], now: datetime
) -> tuple[Project, dict[str, int]]:
    project = Project(
        name=name,
        slug=_slug(name),
        description="Synthetic duplicate-detection dataset",
        created_by_id=users["admin"].id,
        triage_lead_id=users["qa"].id,
    )
    db.add(project)
    await db.flush()
    template = SupportTemplate(
        project_id=project.id,
        name="Problem report",
        is_active=True,
        position=0,
        created_by_id=users["admin"].id,
    )
    db.add(template)
    await db.flush()
    db.add_all(
        [
            SupportTemplateField(
                template_id=template.id,
                position=0,
                label="شرح مشکل",
                field_type="long_text",
                is_required=True,
                help_text="Describe what the customer saw.",
            ),
            SupportTemplateField(
                template_id=template.id,
                position=1,
                label="Platform",
                field_type="single_select",
                options=[
                    {"value": "web", "label": "Web"},
                    {"value": "ios", "label": "iOS"},
                    {"value": "android", "label": "Android"},
                ],
            ),
        ]
    )
    shipped_v, qa_v, planning_v = VERSIONS[name]
    shipped_at = now - timedelta(days=SHIPPED_DAYS_AGO)
    releases = {
        "shipped": Release(
            project_id=project.id,
            kind=ReleaseKind.release,
            version=shipped_v,
            status=ReleaseStatus.released,
            go_nogo_status=GoNogoStatus.approved,
            released_at=shipped_at,
            created_by_id=users["product_manager"].id,
            description="Synthetic dataset — shipped",
        ),
        "qa": Release(
            project_id=project.id,
            kind=ReleaseKind.release,
            version=qa_v,
            status=ReleaseStatus.qa,
            go_nogo_status=GoNogoStatus.pending,
            code_freeze_date=(now - timedelta(days=3)).date(),
            target_date=now + timedelta(days=4),
            created_by_id=users["product_manager"].id,
            description="Synthetic dataset — in release QA",
        ),
        "planning": Release(
            project_id=project.id,
            kind=ReleaseKind.release,
            version=planning_v,
            status=ReleaseStatus.planning,
            go_nogo_status=GoNogoStatus.pending,
            target_date=now + timedelta(days=30),
            created_by_id=users["product_manager"].id,
            description="Synthetic dataset — next",
        ),
    }
    db.add_all(releases.values())
    await db.flush()
    containers = {k: r.id for k, r in releases.items()}
    containers["stream"] = await db.scalar(
        select(Release.id).where(
            Release.project_id == project.id, Release.kind == ReleaseKind.stream
        )
    )
    return project, containers


def _steps(raw: list[dict]) -> list[dict]:
    """Reproduction steps in the shape ``IssueResponse`` validates: always a list (never
    NULL), each step with a 1-based ``step_order``."""
    return [{"step_order": n, **s} for n, s in enumerate(raw, 1)]


async def _preflight() -> None:
    """Say up front what the import will index with and whether background work will run,
    so a fake embedder or a stale worker is not discovered an hour later."""
    from app.db.session import task_session
    from app.search import embeddings, jev_settings

    async with task_session() as db:
        cfg = await embeddings.load_config(db)
        jev = await jev_settings.load(db)
    try:
        model = await embeddings.probe(cfg.endpoint, **cfg.request_args())
        warn = (
            "  ← a fake/test model: search numbers will mean nothing"
            if "fake" in model.lower()
            else ""
        )
        print(f"Embedding endpoint {cfg.endpoint} serves {model}{warn}")
    except embeddings.EmbeddingError as exc:
        print(f"Embedding endpoint {cfg.endpoint} is not answering ({exc}); indexing will fail.")
    print(f"Jev: {'on' if jev.active else 'off'}")
    try:
        from app.tasks.celery_app import celery_app

        queues = await asyncio.to_thread(
            lambda: celery_app.control.inspect(timeout=3).active_queues() or {}
        )
        names = {q["name"] for qs in queues.values() for q in qs}
        if not queues:
            print(
                "No Celery worker answered: on-save indexing / hints will not run after the import."
            )
        elif "search" not in names:
            print(
                f"The running worker consumes {sorted(names)} but not `search`: "
                "items you edit later will not be reindexed. Recreate it: "
                "docker compose -f docker-compose.yml -f docker-compose.dev.yml "
                "up -d --no-deps worker"
            )
    except Exception as exc:  # noqa: BLE001 — advisory only
        print(f"Could not ask Celery for its queues ({type(exc).__name__}).")


async def run(
    dataset: Path, password: str, wipe: bool, index: bool, shift: bool, base_url: str
) -> int:
    issues = json.loads((dataset / "corpus/issues.json").read_text(encoding="utf-8"))
    comments = json.loads((dataset / "corpus/comments.json").read_text(encoding="utf-8"))
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _preflight()

    async with factory() as db:
        if wipe:
            print(f"Wiped {await _wipe(db)} earlier dataset project(s).")
        exists = await db.scalar(
            select(Project.id).where(Project.slug.like(SLUG_PREFIX + "%")).limit(1)
        )
        if exists:
            print(
                "Dataset projects already exist. Re-run with --wipe to replace them "
                "(make dup-dataset-reset).",
                file=sys.stderr,
            )
            return 1

        now = datetime.now(UTC)
        users = await _users(db, password)
        projects: dict[str, Project] = {}
        containers: dict[str, dict[str, int]] = {}
        for name in sorted({i["project_name"] for i in issues}):
            projects[name], containers[name] = await _project(db, name, users, now)
        await db.flush()

        newest = max(datetime.fromisoformat(i["created_at"]) for i in issues)
        delta = (now - timedelta(hours=1) - newest) if shift else timedelta(0)
        shipped_at = now - timedelta(days=SHIPPED_DAYS_AGO)

        from app.services.cycle_service import cycle_service

        by_fake: dict[str, Issue] = {}
        placed: dict[str, str | None] = {}
        for raw in sorted(issues, key=lambda r: r["created_at"]):
            created = datetime.fromisoformat(raw["created_at"]) + delta
            status = IssueStatus(raw["status"])
            typ = IssueType(raw["type"])
            reporter = users["support" if raw["source"] == "support" else raw["reporter_role"]]
            triaged = raw["status"] != "new"
            done = status == IssueStatus.done
            completed = created + timedelta(days=2) if done else None
            where = placement(raw, completed, shipped_at)
            placed[raw["id"]] = where
            item = Issue(
                project_id=projects[raw["project_name"]].id,
                type=typ,
                source=IssueSource(raw["source"]),
                status=IssueStatus.todo if where else status,  # replayed below
                title=raw["title"],
                description=raw["description"] or None,
                priority=(PRIORITY[raw["severity"]] if triaged or typ == IssueType.task else None),
                labels=[LABEL, *raw["labels"]],
                reporter_id=reporter.id,
                assignee_id=users["developer"].id
                if raw["status"] in ("in_progress", "to_review", "in_review", "done")
                else None,
                reproduction_steps=_steps(raw["reproduction_steps"]),
                curl_command=f"curl 'https://api.example.invalid{raw['curl_path']}'"
                if raw["curl_path"]
                else None,
                release_id=containers[raw["project_name"]][where] if where else None,
                filed_at=created,
                triaged_at=created + timedelta(hours=2) if triaged else None,
                created_at=created,
                updated_at=created + timedelta(hours=1),
            )
            if status == IssueStatus.cancelled:
                item.cancel_reason = "duplicate"
                item.cancelled_at = created + timedelta(hours=2)
            db.add(item)
            await db.flush()
            by_fake[raw["id"]] = item
            db.add(
                IssueTimeline(
                    issue_id=item.id,
                    actor_id=reporter.id,
                    event_type=TimelineEventType.filed,
                    body=None,
                    meta={"priority": item.priority.value if item.priority else None},
                    is_internal=False,
                    created_at=created,
                )
            )
            if where:
                # Placed in To do, then walked to its status the way the app moves it, so
                # the cycle carries picked-up / submitted / verified stamps (08a).
                await cycle_service.on_placed(
                    db, item, users["qa"], now=created + timedelta(hours=2)
                )
                prev, at = IssueStatus.todo, created + timedelta(hours=3)
                for step in PATH[raw["status"]]:
                    at += timedelta(hours=8)
                    item.status = step
                    await cycle_service.on_status(db, item, prev, step, users["developer"], at)
                    prev = step
                if raw["status"] == "blocked":
                    item.blocked_from_status = IssueStatus.todo
                    item.status = IssueStatus.blocked
                if done:
                    item.started_at = created + timedelta(hours=11)
                    item.fixed_at = created + timedelta(days=1)
                    item.verified_at = item.completed_at = item.closed_at = completed
                elif item.status != IssueStatus.todo:
                    item.started_at = created + timedelta(hours=11)
                db.add(item)

        for raw in issues:  # second pass: link cancelled duplicates to their originals
            if raw["duplicate_of"] and raw["status"] == "cancelled":
                by_fake[raw["id"]].parent_issue_id = by_fake[raw["duplicate_of"]].id
                db.add(by_fake[raw["id"]])

        for c in comments:
            item = by_fake[c["issue_id"]]
            db.add(
                IssueTimeline(
                    issue_id=item.id,
                    actor_id=users[c["author_role"]].id,
                    event_type=TimelineEventType.comment,
                    body=c["body"],
                    is_internal=bool(c["is_internal"]),
                    created_at=datetime.fromisoformat(c["created_at"]) + delta,
                )
            )
        await db.commit()

        project_of = {r["id"]: r["project_name"] for r in issues}
        mapping = {
            fid: {
                "id": it.id,
                "key": issue_key(it.type, it.issue_number),
                "project": project_of[fid],
                "project_id": it.project_id,
                "slug": _slug(project_of[fid]),
                "container": placed[fid],
            }
            for fid, it in by_fake.items()
        }
        (dataset / "import_map.json").write_text(
            json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        counts: dict[str, int] = {}
        for where in placed.values():
            counts[where or "triage / none"] = counts.get(where or "triage / none", 0) + 1
        print(
            f"Imported {len(by_fake)} issues, {len(comments)} comments "
            f"into {len(projects)} projects "
            f"({', '.join(f'{k} {v}' for k, v in sorted(counts.items()))})."
        )

    if index:
        from app.search import jev_settings
        from app.tasks.search_index import compute_duplicate_hints_now, index_item_now

        print(f"Indexing {len(by_fake)} issues for search…")
        failed = 0
        for it in by_fake.values():
            try:
                await index_item_now(it.id)
            except Exception as exc:  # noqa: BLE001 — report and carry on; Reindex all can finish it
                failed += 1
                if failed == 1:
                    print(
                        f"  indexing failed ({type(exc).__name__}: {exc}). "
                        "Is the embeddings service up? "
                        "Run Settings → Search → Reindex all later."
                    )
        print(f"  indexed {len(by_fake) - failed}/{len(by_fake)}")
        async with factory() as db:
            jev_on = (await jev_settings.load(db)).active
        if jev_on:
            new_bugs = [
                (fid, it)
                for fid, it in by_fake.items()
                if it.status == IssueStatus.new and it.type == IssueType.bug
            ]
            print(f"Computing duplicate hints for {len(new_bugs)} New bugs…")
            hinted = 0
            for fid, it in new_bugs:
                try:
                    res = await compute_duplicate_hints_now(it.id)
                    hinted += bool((res or {}).get("hints"))
                except Exception as exc:  # noqa: BLE001
                    print(f"  hints failed for {fid}: {exc}")
            print(f"  {hinted} of them have at least one hint")
        else:
            print(
                "Jev is off, so no duplicate hints / similar-item panels yet "
                "(Settings → Search → Jev)."
            )
    await engine.dispose()

    from . import guide

    smoke = await _smoke(base_url, password, mapping)
    print(f"Hand-test script: {guide.write(dataset)}")
    return smoke


async def _smoke(base_url: str, password: str, mapping: dict) -> int:
    """Load what the UI loads for each project; any error fails the import."""
    import httpx

    ok = True
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=60) as http:
            r = await http.post(
                "/api/v1/auth/login", json={"username": "dd-qa", "password": password}
            )
            r.raise_for_status()
            http.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
            for slug in sorted({v["slug"] for v in mapping.values()}):
                pid = next(v["project_id"] for v in mapping.values() if v["slug"] == slug)
                one = next(v["id"] for v in mapping.values() if v["slug"] == slug)
                rels = (await http.get("/api/v1/releases", params={"project_id": pid})).json()
                rel_ids = (
                    [x["id"] for x in (rels.get("releases") or rels.get("items") or [])]
                    if isinstance(rels, dict)
                    else [x["id"] for x in rels]
                )
                stream = (await http.get(f"/api/v1/projects/{slug}/stream")).json()["id"]
                urls = [
                    f"/api/v1/releases/{rid}/{tab}"
                    for rid in {stream, *rel_ids}
                    for tab in ("items", "board")
                ]
                urls += [
                    f"/api/v1/issues?project_id={pid}",
                    f"/api/v1/issues?project_id={pid}&status=new",
                    f"/api/v1/issues/{one}",
                ]
                bad = []
                for url in urls:
                    resp = await http.get(url)
                    if resp.status_code != 200:
                        bad.append(f"{url} → {resp.status_code}")
                print(
                    f"  {slug}: {len(urls) - len(bad)}/{len(urls)} pages load"
                    + (f" — FAILED {bad}" if bad else "")
                )
                ok &= not bad
    except httpx.HTTPError as exc:
        print(f"Smoke check skipped: the API at {base_url} is not reachable ({exc}).")
        return 0
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="dup_dataset import")
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--password", default="dataset-pass-123")
    ap.add_argument("--wipe", action="store_true", help="delete the dd-* projects first")
    ap.add_argument(
        "--no-index", action="store_true", help="skip search indexing and hint computation"
    )
    ap.add_argument(
        "--no-shift", action="store_true", help="keep the dataset's own (Sept 2026) dates"
    )
    ap.add_argument("--base-url", default="http://localhost:8000", help="API for the smoke check")
    a = ap.parse_args(argv)
    return asyncio.run(
        run(a.dataset, a.password, a.wipe, not a.no_index, not a.no_shift, a.base_url)
    )
