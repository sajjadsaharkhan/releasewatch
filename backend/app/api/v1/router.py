"""Central API v1 router — assembles all sub-routers.

Each domain module exposes a module-level ``router`` (``APIRouter``).  This
module imports and mounts them all under a single ``api_router`` which is then
included by ``create_app()`` with the ``/api/v1`` prefix.
"""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    projects,
    releases,
    issues,
    timeline,
    attachments,
    inbox,
    reports,
    team,
    settings as settings_router,
    telegram,
    user,
    ws,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
# Releases are nested under projects — the projects router handles /projects/{slug}/releases/*
# but a dedicated releases router handles actions that don't need the slug context
api_router.include_router(releases.router, prefix="/releases", tags=["releases"])
api_router.include_router(issues.router, prefix="/issues", tags=["issues"])
api_router.include_router(timeline.router, prefix="/issues", tags=["timeline"])
api_router.include_router(attachments.router, prefix="/issues", tags=["attachments"])
api_router.include_router(inbox.router, prefix="/inbox", tags=["inbox"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(team.router, prefix="/team", tags=["team"])
api_router.include_router(user.router, tags=["user"])
api_router.include_router(settings_router.router, prefix="/settings", tags=["settings"])
api_router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
api_router.include_router(ws.router, prefix="/ws", tags=["websocket"])
