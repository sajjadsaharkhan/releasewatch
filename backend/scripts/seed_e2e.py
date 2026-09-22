"""Seed script for the E2E stack — one known user per role + one project.

Wipes the E2E database (idempotent — safe to run on every `make e2e`) and
creates exactly the fixtures the Playwright suite's ``global-setup.ts`` logs
in as. Later slices extend this only with what their scenarios need (e.g. a
support template in slice 05); `pm` and `support` roles arrive in slice 04.

Usage:
    docker compose exec api python -m scripts.seed_e2e
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.models  # noqa: F401 — registers every model's metadata
from app.config import settings
from app.core.auth import get_password_hash
from app.db.base import Base
from app.db.models.project import Project
from app.db.models.user import User, UserRole

E2E_PASSWORD = "e2e-password-123"

ROLE_USERS = [
    ("e2e-qa", "E2E QA", UserRole.qa),
    ("e2e-developer", "E2E Developer", UserRole.developer),
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

    print("Seeding one product project...")
    project = Project(
        name="E2E Product",
        slug="e2e-product",
        description="Fixture project for the Playwright suite",
        created_by_id=users["e2e-admin"].id,
        triage_lead_id=users["e2e-qa"].id,
    )
    session.add(project)
    await session.commit()
    print("  Created 1 project")
    print("\nE2E seed complete.")


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
