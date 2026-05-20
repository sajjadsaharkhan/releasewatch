"""Standalone releases router (for endpoints that don't need the project slug).

This module is intentionally minimal — the main release CRUD lives in
``projects.py`` under ``/projects/{slug}/releases/*``.  This router is
reserved for cross-project release queries or future expansion.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter()


# Placeholder — extend with cross-project release search, export, etc.
@router.get("", summary="[Reserved] cross-project release list", include_in_schema=False)
async def list_all_releases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """Reserved for cross-project release aggregation — not yet implemented."""
    return []
