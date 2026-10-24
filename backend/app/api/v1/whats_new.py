"""What's new endpoints (TASK-575) — every signed-in role.

GET  /whats-new        — the reader's team's notes, and which one to open now
POST /whats-new/seen   — record notes as seen (idempotent)
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.whats_new import SeenRequest, WhatsNewResponse
from app.services import whats_new_service
from app.whats_new.notes import Note, get_notes

router = APIRouter()


@router.get("", response_model=WhatsNewResponse, summary="What's new for the current user")
async def whats_new(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notes: tuple[Note, ...] = Depends(get_notes),
) -> WhatsNewResponse:
    return await whats_new_service.whats_new_for(db, current_user, notes)


@router.post("/seen", status_code=status.HTTP_204_NO_CONTENT, summary="Mark What's new notes as seen")
async def mark_seen(
    payload: SeenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notes: tuple[Note, ...] = Depends(get_notes),
) -> Response:
    await whats_new_service.mark_seen(db, current_user, payload.note_ids, notes)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
