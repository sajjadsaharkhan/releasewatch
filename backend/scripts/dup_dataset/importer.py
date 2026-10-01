"""Import the built dataset into a (development) Releasewatch database.

    docker compose exec api python -m scripts.dup_dataset import
    docker compose exec api python -m scripts.dup_dataset import --wipe     # re-import from scratch

What it creates (never touches anything else, except ``--wipe``, which deletes the
``dd-*`` projects it made earlier — their issues, comments and search rows cascade):

* users ``dd-qa``, ``dd-developer``, ``dd-pm``, ``dd-support``, ``dd-cto``, ``dd-admin``
  (one password for all, ``--password``, default ``dataset-pass-123``);
* five projects, slugs ``dd-chat``, ``dd-limsa``, ``dd-dano``, ``dd-studentpanel``,
  ``dd-releasewatch``, each with a support template so the Support form works;
* every issue (type, source, status, severity → priority, labels, reproduction steps,
  cURL path, timestamps shifted so the newest issue is "an hour ago"), its comments,
  and a ``filed`` timeline event; ``cancelled`` duplicates are linked to their original;
* then each issue is indexed for search (``index_item_now``) and, when Jev is on, the
  duplicate hints of every New bug are computed.

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
from app.db.models.issue import Issue, IssueSource, IssueStatus, IssueType, Priority
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.project import Project
from app.db.models.release import Release, ReleaseKind
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
#: Statuses that live in a container (the project's Stream); New / backlog items do not.
IN_STREAM = {"todo", "in_progress", "to_review", "in_review", "done", "blocked"}
ROLE_NAMES = {
    "qa": "QA",
    "developer": "Developer",
    "pm": "PM",
    "support": "Support",
    "cto": "CTO",
    "admin": "Admin",
}


def _slug(name: str) -> str:
    return SLUG_PREFIX + name.lower()


async def _wipe(db: AsyncSession) -> None:
    ids = (
        (await db.execute(select(Project.id).where(Project.slug.like(SLUG_PREFIX + "%"))))
        .scalars()
        .all()
    )
    if ids:
        print(f"Wiping {len(ids)} earlier dataset project(s)…")
        await db.execute(delete(Project).where(Project.id.in_(ids)))
        await db.commit()


async def _users(db: AsyncSession, password: str) -> dict[str, User]:
    users: dict[str, User] = {}
    for role, label in ROLE_NAMES.items():
        username = f"dd-{role}"
        user = await db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(
                name=f"Dataset {label}",
                username=username,
                hashed_password=get_password_hash(password),
                role=UserRole(role),
                is_active=True,
            )
            db.add(user)
        users[role] = user
    await db.flush()
    return users


async def _project(db: AsyncSession, name: str, users: dict[str, User]) -> Project:
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
    return project


async def run(dataset: Path, password: str, wipe: bool, index: bool, shift: bool) -> int:
    issues = json.loads((dataset / "corpus/issues.json").read_text(encoding="utf-8"))
    comments = json.loads((dataset / "corpus/comments.json").read_text(encoding="utf-8"))
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        if wipe:
            await _wipe(db)
        exists = await db.scalar(
            select(Project.id).where(Project.slug.like(SLUG_PREFIX + "%")).limit(1)
        )
        if exists:
            print(
                "Dataset projects already exist. Re-run with --wipe to replace them.",
                file=sys.stderr,
            )
            return 1

        users = await _users(db, password)
        projects: dict[str, Project] = {}
        for name in sorted({i["project_name"] for i in issues}):
            projects[name] = await _project(db, name, users)
        await db.flush()
        stream = {
            name: await db.scalar(
                select(Release.id).where(
                    Release.project_id == p.id, Release.kind == ReleaseKind.stream
                )
            )
            for name, p in projects.items()
        }

        newest = max(datetime.fromisoformat(i["created_at"]) for i in issues)
        delta = (datetime.now(UTC) - timedelta(hours=1) - newest) if shift else timedelta(0)

        from app.services.cycle_service import cycle_service

        by_fake: dict[str, Issue] = {}
        for raw in sorted(issues, key=lambda r: r["created_at"]):
            created = datetime.fromisoformat(raw["created_at"]) + delta
            status = IssueStatus(raw["status"])
            typ = IssueType(raw["type"])
            reporter = users["support" if raw["source"] == "support" else raw["reporter_role"]]
            triaged = raw["status"] != "new"
            item = Issue(
                project_id=projects[raw["project_name"]].id,
                type=typ,
                source=IssueSource(raw["source"]),
                status=status,
                title=raw["title"],
                description=raw["description"] or None,
                priority=(PRIORITY[raw["severity"]] if triaged or typ == IssueType.task else None),
                labels=[LABEL, *raw["labels"]],
                reporter_id=reporter.id,
                assignee_id=users["developer"].id
                if raw["status"] in ("in_progress", "to_review", "in_review", "done")
                else None,
                reproduction_steps=raw["reproduction_steps"] or None,
                curl_command=f"curl 'https://api.example.invalid{raw['curl_path']}'"
                if raw["curl_path"]
                else None,
                release_id=stream[raw["project_name"]] if raw["status"] in IN_STREAM else None,
                filed_at=created,
                created_at=created,
                updated_at=created + timedelta(hours=1),
            )
            if status == IssueStatus.cancelled:
                item.cancel_reason = "duplicate"
                item.cancelled_at = created + timedelta(hours=2)
            if status == IssueStatus.done:
                item.completed_at = created + timedelta(days=2)
                item.fixed_at = created + timedelta(days=1)
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
            if item.release_id is not None:
                await cycle_service.on_placed(
                    db, item, reporter, now=created + timedelta(minutes=30)
                )

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

        mapping = {
            fid: {
                "id": it.id,
                "key": f"{'BUG' if it.type == IssueType.bug else 'TASK'}-{it.issue_number}",
                "project": raw_p,
                "project_id": it.project_id,
                "slug": _slug(raw_p),
            }
            for fid, it in by_fake.items()
            for raw_p in [next(r["project_name"] for r in issues if r["id"] == fid)]
        }
        (dataset / "import_map.json").write_text(
            json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(
            f"Imported {len(by_fake)} issues, {len(comments)} comments "
            f"into {len(projects)} projects."
        )
        print(
            "Users: dd-qa / dd-developer / dd-pm / dd-support / dd-cto / dd-admin "
            f"— password {password!r}"
        )

    if index:
        from app.search import jev_settings
        from app.tasks.search_index import compute_duplicate_hints_now, index_item_now

        print("Indexing for search…")
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
            print("Computing duplicate hints for New bugs…")
            n = 0
            for fid, it in by_fake.items():
                if it.status == IssueStatus.new and it.type == IssueType.bug:
                    try:
                        await compute_duplicate_hints_now(it.id)
                        n += 1
                    except Exception as exc:  # noqa: BLE001
                        print(f"  hints failed for {fid}: {exc}")
            print(f"  computed for {n} New bugs")
        else:
            print(
                "Jev is off, so no duplicate hints / similar-item panels yet "
                "(Settings → Search → Jev)."
            )
    await engine.dispose()

    from . import guide

    print(f"Hand-test script: {guide.write(dataset)}")
    return 0


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
    a = ap.parse_args(argv)
    return asyncio.run(run(a.dataset, a.password, a.wipe, not a.no_index, not a.no_shift))
