"""Seed script — populate the database with sample data for development.

Usage:
    python -m scripts.seed           # from backend/ directory
    docker compose exec api python -m scripts.seed
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.core.auth import get_password_hash
from app.db.models.user import User, UserRole
from app.db.models.project import Project
from app.db.models.release import Release, ReleaseStatus, GoNogoStatus
from app.db.models.issue import Issue, IssueStatus, IssueType, Priority
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType

NOW = datetime.now(tz=timezone.utc)


async def seed(session: AsyncSession) -> None:
    print("Seeding team members...")

    admin_user = User(
        name="Root Admin",
        username="admin",
        hashed_password=get_password_hash("password123"),
        role=UserRole.admin,
        title="System Administrator",
        bio="Root administrator with full access to all resources.",
        avatar_color="#6366f1",
        is_active=True,
    )

    users = [
        admin_user,
        User(name="Sajjad Saharkhan",  username="sajjad",  role=UserRole.developer, avatar_color="#8b5cf6", title="Engineering Lead", bio="Building Releasewatch to make QA painless.", is_active=True),
        User(name="Priya Nair",         username="priya",   role=UserRole.qa,          avatar_color="#06b6d4", title="QA Engineer", is_active=True),
        User(name="Tom Eriksson",       username="tom",     role=UserRole.developer,   avatar_color="#10b981", title="Frontend Developer", is_active=True),
        User(name="Ana Beatriz",        username="ana",     role=UserRole.developer,   avatar_color="#f59e0b", title="Backend Developer", is_active=True),
        User(name="Lena Hoffmann",      username="lena",    role=UserRole.qa,          avatar_color="#ef4444", title="QA Engineer", is_active=True),
        User(name="Marcus Chen",        username="marcus",  role=UserRole.cto,         avatar_color="#6366f1", title="CTO", is_active=True),
        User(name="Nora Lindqvist",     username="nora",    role=UserRole.pm,          avatar_color="#ec4899", title="Project Manager", is_active=True),
        User(name="Omar Haddad",        username="omar",    role=UserRole.support,     avatar_color="#14b8a6", title="Customer Support", is_active=True),
    ]

    for u in users:
        if u is not admin_user:
            u.hashed_password = get_password_hash("password123")

    session.add_all(users)
    await session.flush()
    print(f"  Created {len(users)} users (including admin)")

    print("Seeding projects...")
    creator = users[0]
    # Sajjad (users[1]) is designated as triage lead for both projects
    triage_lead = users[1]
    projects = [
        Project(name="Mobile App",  slug="mobile-app",  description="iOS and Android apps", created_by_id=creator.id, triage_lead_id=triage_lead.id),
        Project(name="API Gateway", slug="api-gateway", description="Core API service",      created_by_id=creator.id, triage_lead_id=triage_lead.id),
    ]
    session.add_all(projects)
    await session.flush()
    print(f"  Created {len(projects)} projects")

    # Every project already has its Default (ORM hook); add a few examples.
    from app.db.models.backlog_category import BacklogCategory
    for project in projects:
        session.add_all([
            BacklogCategory(project_id=project.id, name="Feature requests", icon="sparkles", color="emerald", position=1),
            BacklogCategory(project_id=project.id, name="Improvements", icon="trending-up", color="cyan", position=2),
            BacklogCategory(project_id=project.id, name="Ideas", icon="lightbulb", color="violet", position=3),
        ])
    await session.flush()
    print("  Created backlog categories")

    print("Seeding releases...")
    # Every project already has its Stream (ORM hook, BR-51); add Releases in
    # different lifecycle states.
    from app.db.models.release import ReleaseKind
    releases = [
        Release(project_id=projects[0].id, version="v2.4.1", status=ReleaseStatus.qa,          go_nogo_status=GoNogoStatus.pending,  created_by_id=creator.id,
                code_freeze_date=(NOW - timedelta(days=2)).date(), target_date=NOW + timedelta(days=5)),
        Release(project_id=projects[0].id, version="v2.5.0", status=ReleaseStatus.planning,    go_nogo_status=GoNogoStatus.pending,  created_by_id=creator.id,
                target_date=NOW + timedelta(days=30)),
        Release(project_id=projects[0].id, version="v2.3.0", status=ReleaseStatus.released,    go_nogo_status=GoNogoStatus.approved, created_by_id=creator.id,
                released_at=NOW - timedelta(days=14)),
        Release(project_id=projects[1].id, version="v1.8.0", status=ReleaseStatus.development, go_nogo_status=GoNogoStatus.pending,  created_by_id=creator.id,
                target_date=NOW + timedelta(days=12)),
    ]
    session.add_all(releases)
    await session.flush()
    streams = {
        r.project_id: r for r in (await session.execute(
            select(Release).where(Release.kind == ReleaseKind.stream.value)
        )).scalars().all()
    }
    print(f"  Created {len(releases)} releases (+ one Stream per project)")

    print("Seeding issues...")
    qa1, dev1, dev2 = users[2], users[1], users[3]
    mobile, api = projects
    qa_rel, planned_rel, shipped_rel, api_rel = releases
    mobile_stream, api_stream = streams[mobile.id], streams[api.id]
    # (project, container or None for the backlog, fields)
    issues_data = [
        # Mobile App — v2.4.1 in QA
        (mobile, qa_rel, dict(priority=Priority.critical, status=IssueStatus.in_progress, title="Crash on checkout with Apple Pay",           reporter_id=qa1.id,      assignee_id=dev1.id, is_release_blocker=True)),
        (mobile, qa_rel, dict(priority=Priority.critical, status=IssueStatus.todo,        title="Push notifications not delivered on iOS 17", reporter_id=qa1.id,      assignee_id=dev2.id)),
        (mobile, qa_rel, dict(priority=Priority.high,     status=IssueStatus.in_review,   title="Pagination breaks on search results",        reporter_id=users[4].id, assignee_id=dev1.id)),
        (mobile, qa_rel, dict(priority=Priority.medium,   status=IssueStatus.done,        title="Date picker shows wrong timezone",           reporter_id=users[4].id, assignee_id=dev2.id)),
        (mobile, qa_rel, dict(priority=Priority.critical, status=IssueStatus.in_progress, title="Auth token refresh causes 401 loop",         reporter_id=qa1.id,      assignee_id=dev1.id)),
        (mobile, qa_rel, dict(priority=None,              status=IssueStatus.new,         title="Profile image upload fails >5MB",            reporter_id=qa1.id,      assignee_id=None)),
        # Mobile App — v2.5.0 planned, v2.3.0 shipped
        (mobile, planned_rel, dict(type=IssueType.task, priority=Priority.medium, status=IssueStatus.todo, title="Redesign the onboarding flow", reporter_id=users[7].id, assignee_id=dev2.id)),
        (mobile, shipped_rel, dict(priority=Priority.medium, status=IssueStatus.done,     title="Typo in onboarding screen copy",             reporter_id=users[4].id, assignee_id=dev2.id)),
        # Mobile App — Stream
        (mobile, mobile_stream, dict(priority=Priority.high,   status=IssueStatus.in_progress, title="Dark mode flicker on app launch",      reporter_id=qa1.id,      assignee_id=dev1.id)),
        (mobile, mobile_stream, dict(type=IssueType.task, priority=Priority.low, status=IssueStatus.done, title="Rotate the App Store screenshots", reporter_id=users[7].id, assignee_id=dev2.id)),
        # Mobile App — backlog
        (mobile, None, dict(type=IssueType.task, priority=Priority.medium, status=IssueStatus.todo, title="Add swipe-to-dismiss on notification cards", reporter_id=users[7].id, assignee_id=None)),
        (mobile, None, dict(type=IssueType.task, priority=Priority.low,    status=IssueStatus.todo, title="Offline mode for the reading list",          reporter_id=users[7].id, assignee_id=None)),
        # API Gateway — v1.8.0 in development, Stream, backlog
        (api, api_rel,    dict(priority=Priority.critical, status=IssueStatus.in_progress, title="Rate limiting not applied on /auth/login", reporter_id=users[4].id, assignee_id=dev2.id, is_release_blocker=True)),
        (api, api_stream, dict(priority=Priority.high,     status=IssueStatus.todo,        title="Webhook retries flood the queue",           reporter_id=qa1.id,      assignee_id=users[4].id)),
        (api, None,       dict(type=IssueType.task, priority=Priority.medium, status=IssueStatus.todo, title="Move request logs to structured JSON", reporter_id=users[7].id, assignee_id=None)),
    ]
    issues = []
    for i, (project, container, data) in enumerate(issues_data, start=1):
        issue = Issue(
            issue_number=i,
            project_id=project.id,
            release_id=container.id if container is not None else None,
            filed_at=NOW - timedelta(hours=24 * i // 3),
            **data,
        )
        issues.append(issue)
    session.add_all(issues)
    await session.flush()
    # issue_number was set explicitly above — move the sequence past it so the
    # next item filed through the app doesn't reuse a seeded number.
    await session.execute(text(
        "SELECT setval('issue_number_seq', (SELECT max(issue_number) FROM issues))"
    ))
    # Backlog members need a rank to be ordered (slice 08).
    for rank, issue in enumerate((i for i in issues if i.release_id is None), start=1):
        issue.backlog_rank = rank * 1024.0
    print(f"  Created {len(issues)} issues")

    print("Seeding timeline events...")
    events = []
    for issue in issues:
        events.append(IssueTimeline(
            issue_id=issue.id,
            actor_id=issue.reporter_id,
            event_type=TimelineEventType.filed,
            body="Issue filed.",
            created_at=issue.filed_at,
        ))
        if issue.assignee_id:
            events.append(IssueTimeline(
                issue_id=issue.id,
                actor_id=triage_lead.id,  # triage lead user designated for the project
                event_type=TimelineEventType.assigned,
                meta={"assignee_id": str(issue.assignee_id)},
                created_at=issue.filed_at + timedelta(hours=1),
            ))
    session.add_all(events)
    await session.commit()
    print(f"  Created {len(events)} timeline events")
    print("\nSeed complete.")


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
