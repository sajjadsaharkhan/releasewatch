"""Seed script — populate the database with sample data for development.

Usage:
    python -m scripts.seed           # from backend/ directory
    docker compose exec api python -m scripts.seed
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.core.auth import get_password_hash
from app.db.models.user import User, UserRole
from app.db.models.project import Project
from app.db.models.release import Release, ReleaseStatus, GoNoGoStatus
from app.db.models.issue import Issue, IssueSeverity, IssueStatus
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType

NOW = datetime.now(tz=timezone.utc)


async def seed(session: AsyncSession) -> None:
    print("Seeding team members...")
    users = [
        User(id=uuid.uuid4(), name="Sajjad Saharkhan",  username="sajjad",  email="sajjad@releasewatch.dev",  role=UserRole.triage_lead, avatar_color="#8b5cf6", is_active=True),
        User(id=uuid.uuid4(), name="Priya Nair",         username="priya",   email="priya@releasewatch.dev",   role=UserRole.qa,          avatar_color="#06b6d4", is_active=True),
        User(id=uuid.uuid4(), name="Tom Eriksson",       username="tom",     email="tom@releasewatch.dev",     role=UserRole.developer,   avatar_color="#10b981", is_active=True),
        User(id=uuid.uuid4(), name="Ana Beatriz",        username="ana",     email="ana@releasewatch.dev",     role=UserRole.developer,   avatar_color="#f59e0b", is_active=True),
        User(id=uuid.uuid4(), name="Lena Hoffmann",      username="lena",    email="lena@releasewatch.dev",    role=UserRole.qa,          avatar_color="#ef4444", is_active=True),
        User(id=uuid.uuid4(), name="Marcus Chen",        username="marcus",  email="marcus@releasewatch.dev",  role=UserRole.cto,         avatar_color="#6366f1", is_active=True),
    ]
    for u in users:
        u.hashed_password = get_password_hash("password123")
    session.add_all(users)
    await session.flush()
    print(f"  Created {len(users)} users")

    print("Seeding projects...")
    triage_lead = users[0]
    projects = [
        Project(id=uuid.uuid4(), name="Mobile App",  slug="mobile-app",  description="iOS and Android apps", created_by=triage_lead.id),
        Project(id=uuid.uuid4(), name="API Gateway", slug="api-gateway", description="Core API service",      created_by=triage_lead.id),
    ]
    session.add_all(projects)
    await session.flush()
    print(f"  Created {len(projects)} projects")

    print("Seeding releases...")
    releases = [
        Release(id=uuid.uuid4(), project_id=projects[0].id, version="v2.4.1", status=ReleaseStatus.active,   go_nogo_status=GoNoGoStatus.pending,  created_by=triage_lead.id),
        Release(id=uuid.uuid4(), project_id=projects[0].id, version="v2.3.0", status=ReleaseStatus.archived, go_nogo_status=GoNoGoStatus.approved, created_by=triage_lead.id),
        Release(id=uuid.uuid4(), project_id=projects[1].id, version="v1.8.0", status=ReleaseStatus.qa,       go_nogo_status=GoNoGoStatus.pending,  created_by=triage_lead.id),
    ]
    session.add_all(releases)
    await session.flush()
    print(f"  Created {len(releases)} releases")

    print("Seeding issues...")
    qa1, dev1, dev2 = users[1], users[2], users[3]
    active_rel = releases[0]
    issues_data = [
        dict(severity=IssueSeverity.blocker,  status=IssueStatus.in_progress, title="Crash on checkout with Apple Pay",       reporter_id=qa1.id,  assignee_id=dev1.id, is_release_blocker=True),
        dict(severity=IssueSeverity.critical, status=IssueStatus.triaged,     title="Push notifications not delivered on iOS 17", reporter_id=qa1.id,  assignee_id=dev2.id),
        dict(severity=IssueSeverity.major,    status=IssueStatus.new,          title="Profile image upload fails >5MB",           reporter_id=qa1.id,  assignee_id=None),
        dict(severity=IssueSeverity.major,    status=IssueStatus.fixed,        title="Pagination breaks on search results",       reporter_id=users[4].id, assignee_id=dev1.id),
        dict(severity=IssueSeverity.minor,    status=IssueStatus.verified,     title="Date picker shows wrong timezone",          reporter_id=users[4].id, assignee_id=dev2.id),
        dict(severity=IssueSeverity.blocker,  status=IssueStatus.regression,   title="Auth token refresh causes 401 loop",        reporter_id=qa1.id,  assignee_id=dev1.id, is_regression=True),
        dict(severity=IssueSeverity.enhancement, status=IssueStatus.new,       title="Add swipe-to-dismiss on notification cards", reporter_id=qa1.id, assignee_id=None),
        dict(severity=IssueSeverity.critical, status=IssueStatus.in_progress,  title="Rate limiting not applied on /auth/login",  reporter_id=users[4].id, assignee_id=dev2.id, is_release_blocker=True),
        dict(severity=IssueSeverity.major,    status=IssueStatus.triaged,      title="Dark mode flicker on app launch",            reporter_id=qa1.id,  assignee_id=dev1.id),
        dict(severity=IssueSeverity.minor,    status=IssueStatus.closed,       title="Typo in onboarding screen copy",             reporter_id=users[4].id, assignee_id=dev2.id),
    ]
    issues = []
    for i, data in enumerate(issues_data, start=1):
        issue = Issue(
            id=uuid.uuid4(),
            issue_number=i,
            project_id=active_rel.project_id,
            release_id=active_rel.id,
            filed_at=NOW - timedelta(hours=24 * i // 3),
            **data,
        )
        issues.append(issue)
    session.add_all(issues)
    await session.flush()
    print(f"  Created {len(issues)} issues")

    print("Seeding timeline events...")
    events = []
    for issue in issues:
        events.append(IssueTimeline(
            id=uuid.uuid4(),
            issue_id=issue.id,
            actor_id=issue.reporter_id,
            event_type=TimelineEventType.filed,
            body=f"Issue filed.",
            created_at=issue.filed_at,
        ))
        if issue.assignee_id:
            events.append(IssueTimeline(
                id=uuid.uuid4(),
                issue_id=issue.id,
                actor_id=triage_lead.id,
                event_type=TimelineEventType.assigned,
                meta={"to_user_id": str(issue.assignee_id)},
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
