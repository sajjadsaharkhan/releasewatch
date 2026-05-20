"""Settings API — notification preferences and integrations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter()

# In production these would be stored per-user/workspace in a settings table.
# For now they are returned as a default matrix and accepted as-is.

_DEFAULT_NOTIFICATION_MATRIX = {
    "filed": {"reporter": True, "assignee": False, "triage": True, "cto": True},
    "assigned": {"reporter": False, "assignee": True, "triage": False, "cto": False},
    "comment": {"reporter": True, "assignee": True, "triage": False, "cto": False},
    "mention": {"reporter": True, "assignee": True, "triage": True, "cto": True},
    "regression": {"reporter": True, "assignee": True, "triage": True, "cto": True},
    "fix_ready": {"reporter": True, "assignee": False, "triage": False, "cto": False},
    "fix_verified": {"reporter": False, "assignee": True, "triage": False, "cto": False},
    "release_gate": {"reporter": False, "assignee": False, "triage": True, "cto": True},
}

_gitlab_config: dict = {}


@router.get("/notifications")
async def get_notifications(
    current_user: User = Depends(get_current_user),
):
    """Return the notification preference matrix (event types × roles)."""
    return _DEFAULT_NOTIFICATION_MATRIX


@router.put("/notifications")
async def save_notifications(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Persist notification preferences. Body must match the matrix shape."""
    _DEFAULT_NOTIFICATION_MATRIX.update(body)
    return _DEFAULT_NOTIFICATION_MATRIX


@router.get("/integrations/gitlab")
async def get_gitlab_config(
    current_user: User = Depends(get_current_user),
):
    """Return GitLab webhook connection status and config."""
    return {
        "connected": bool(_gitlab_config.get("webhook_url")),
        "webhook_url": _gitlab_config.get("webhook_url"),
        "target_branch": _gitlab_config.get("target_branch", "main"),
    }


@router.post("/integrations/gitlab")
async def save_gitlab_config(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Save GitLab webhook URL, secret, and target branch."""
    _gitlab_config.update(body)
    return {"connected": True, **_gitlab_config}
