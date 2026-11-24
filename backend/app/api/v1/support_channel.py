"""Support channel settings (slice 21, FR-70) — CTO and Admin (``manage_support_channel``).

GET  /projects/{id}/support-channel        — chat, topic, enabled, test state, post counters
PUT  /projects/{id}/support-channel        — save; enabling needs a passing test (409)
POST /projects/{id}/support-channel/test   — send a test message → ``{ok, error?}``
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_db
from app.policy import Action
from app.schemas.support_channel import (
    SupportChannelResponse,
    SupportChannelTestResult,
    SupportChannelUpdate,
)
from app.services.authz import require_action
from app.services.support_channel_service import support_channel_service

router = APIRouter()

_manager = require_action(Action.manage_support_channel)


@router.get(
    "/{project_id}/support-channel", response_model=SupportChannelResponse,
    summary="The project's Support channel",
)
async def get_support_channel(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_manager),
) -> SupportChannelResponse:
    project = await support_channel_service.get_project(db, project_id)
    return SupportChannelResponse(**await support_channel_service.state(db, project))


@router.put(
    "/{project_id}/support-channel", response_model=SupportChannelResponse,
    summary="Save the project's Support channel",
)
async def put_support_channel(
    project_id: int,
    payload: SupportChannelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_manager),
) -> SupportChannelResponse:
    project = await support_channel_service.get_project(db, project_id)
    await support_channel_service.save(
        db, project, payload.chat_id, payload.thread_id, payload.enabled,
    )
    await db.commit()
    return SupportChannelResponse(**await support_channel_service.state(db, project))


@router.post(
    "/{project_id}/support-channel/test", response_model=SupportChannelTestResult,
    summary="Send a test message to the Support channel",
)
async def test_support_channel(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_manager),
) -> SupportChannelTestResult:
    project = await support_channel_service.get_project(db, project_id)
    result = await support_channel_service.send_test(db, project)
    await db.commit()
    return SupportChannelTestResult(**result)
