"""Seed script for the E2E stack — one known user per role + one project.

Wipes the E2E database (idempotent — safe to run on every `make e2e`) and
creates exactly the fixtures the Playwright suite's ``global-setup.ts`` logs
in as. Later slices extend this only with what their scenarios need. Slice 05
adds a support template to the product project and a second project with none,
so the Support report scenario can prove only reportable projects are offered.
Slice 12 adds one bug and indexes it, so the palette scenario has something
to find (the E2E stack's embedding endpoint is the fake).

Usage:
    docker compose exec api python -m scripts.seed_e2e
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.models  # noqa: F401 — registers every model's metadata
from app.config import settings
from app.core.auth import get_password_hash
from app.db.base import Base
from app.db.models.issue import Issue, IssueStatus, IssueType
from app.db.models.project import Project
from app.db.models.support_template import SupportTemplate, SupportTemplateField
from app.db.models.user import User, UserRole
from app.tasks.search_index import index_item_now

E2E_PASSWORD = "e2e-password-123"
#: The searchable bug — e2e/tests/smoke.spec.ts searches for it.
SEARCH_FIXTURE_TITLE = "Reactions disappear in group chat after refresh"

ROLE_USERS = [
    ("e2e-qa", "E2E QA", UserRole.qa),
    ("e2e-developer", "E2E Developer", UserRole.developer),
    ("e2e-pm", "E2E PM", UserRole.pm),
    ("e2e-support", "E2E Support", UserRole.support),
    ("e2e-cto", "E2E CTO", UserRole.cto),
    ("e2e-admin", "E2E Admin", UserRole.admin),
]


async def _wipe(session: AsyncSession) -> None:
    table_names = [t.name for t in Base.metadata.sorted_tables if t.name != "alembic_version"]
    quoted = ", ".join(f'"{name}"' for name in table_names)
    await session.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
    await session.commit()


async def seed(session: AsyncSession) -> None:
    print("Wiping E2E database...")
    await _wipe(session)

    print("Seeding one user per role...")
    users: dict[str, User] = {}
    for username, name, role in ROLE_USERS:
        user = User(
            name=name,
            username=username,
            hashed_password=get_password_hash(E2E_PASSWORD),
            role=role,
            is_active=True,
        )
        session.add(user)
        users[username] = user
    await session.flush()
    print(f"  Created {len(users)} users")

    print("Seeding one project...")
    project = Project(
        name="E2E Product",
        slug="e2e-product",
        description="Fixture project for the Playwright suite",
        created_by_id=users["e2e-admin"].id,
        triage_lead_id=users["e2e-qa"].id,
    )
    session.add(project)
    no_template_project = Project(
        name="E2E Internal Tools",
        slug="e2e-internal-tools",
        description="Has no support template — Support must not be offered it",
        # Older than E2E Product, so the app's default project (newest first) stays E2E Product.
        created_at=datetime.now(UTC) - timedelta(days=1),
        created_by_id=users["e2e-admin"].id,
        triage_lead_id=users["e2e-qa"].id,
    )
    session.add(no_template_project)
    await session.flush()
    print("  Created 2 projects")

    print("Seeding one support template...")
    template = SupportTemplate(
        project_id=project.id,
        name="Online class problem",
        is_active=True,
        position=0,
        created_by_id=users["e2e-admin"].id,
    )
    session.add(template)
    await session.flush()
    session.add_all([
        SupportTemplateField(
            template_id=template.id, position=0, label="Class time", field_type="datetime",
            is_required=True, help_text="When the class started.",
        ),
        SupportTemplateField(
            template_id=template.id, position=1, label="Platform", field_type="single_select",
            options=[{"value": "web", "label": "Web app"}, {"value": "ios", "label": "iOS app"}],
        ),
        SupportTemplateField(
            template_id=template.id, position=2, label="Class name", field_type="short_text",
        ),
    ])
    print("Seeding one searchable bug...")
    bug = Issue(
        project_id=project.id,
        type=IssueType.bug,
        status=IssueStatus.new,
        title=SEARCH_FIXTURE_TITLE,
        description="After a page refresh, emoji reactions on group chat messages are gone.",
        reporter_id=users["e2e-qa"].id,
    )
    session.add(bug)
    await session.commit()

    print("Indexing it for search...")
    await index_item_now(bug.id)
    print("\nE2E seed complete.")


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
