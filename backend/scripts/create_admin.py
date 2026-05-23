"""Create root admin user.

Usage:
    python -m scripts.create_admin           # from backend/ directory
    docker compose exec api python -m scripts.create_admin
"""

import asyncio
import uuid

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.db.models.user import User, UserRole


# Hash password using bcrypt directly
def get_password_hash(password: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


async def create_admin_user() -> None:
    """Create the root admin user if it doesn't exist."""
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Check if admin already exists
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.email == "admin@example.com")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Admin user already exists: {existing.email}")
            print(f"  Username: {existing.username}")
            print(f"  Role: {existing.role.value}")
            return

        # Create root admin user
        admin = User(
            id=uuid.uuid4(),
            email="admin@example.com",
            name="Root Admin",
            username="admin",
            hashed_password=get_password_hash("password123"),
            role=UserRole.admin,
            title="System Administrator",
            bio="Root administrator with full access to all resources.",
            avatar_color="#6366f1",
            is_active=True,
        )

        session.add(admin)
        await session.commit()
        await session.refresh(admin)

        print(f"Created admin user:")
        print(f"  Email: {admin.email}")
        print(f"  Username: {admin.username}")
        print(f"  Password: password123")
        print(f"  Role: {admin.role}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_admin_user())
