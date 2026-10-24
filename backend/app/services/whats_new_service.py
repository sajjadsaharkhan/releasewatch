"""What's new (TASK-575) — which notes a person sees, and remembering what they've seen.

Notes are written per team (``app/whats_new/AUTHORING.md``): Support sees the
``support`` highlights, every other role the ``tech`` ones. A note counts as
seen once the person dismissed it, opened it in the changelog, or if it was
published no later than the day their account was created — someone who joins
gets today's app, not a tour of what changed before they arrived.
"""

from fastapi import status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.db.models.user import User, UserRole
from app.db.models.user_acknowledgement import AcknowledgementKind, UserAcknowledgement
from app.schemas.whats_new import HighlightOut, NoteOut, TourStepOut, WhatsNewResponse
from app.whats_new.notes import Kind, Note, Team


def team_of(user: User) -> Team:
    return Team.support if user.role == UserRole.support else Team.tech


async def _seen_ids(db: AsyncSession, user: User) -> set[str]:
    rows = await db.execute(
        select(UserAcknowledgement.key).where(
            UserAcknowledgement.user_id == user.id,
            UserAcknowledgement.kind == AcknowledgementKind.note,
        )
    )
    return set(rows.scalars())


def _view(note: Note, team: Team, seen: bool) -> NoteOut | None:
    highlights = [h for h in note.highlights if team in h.teams]
    if not highlights:
        return None
    headline = note.headline[team]
    return NoteOut(
        id=note.id,
        date=note.date,
        title=headline.title,
        summary=headline.summary,
        highlights=[
            HighlightOut(
                kind=h.kind.value,
                title=h.title,
                icon=h.icon,
                body=h.body,
                tour=[TourStepOut(**s.model_dump()) for s in h.tour],
            )
            for h in highlights
        ],
        seen=seen,
    )


async def whats_new_for(db: AsyncSession, user: User, notes: tuple[Note, ...]) -> WhatsNewResponse:
    team = team_of(user)
    acknowledged = await _seen_ids(db, user)
    joined = user.created_at.date()
    views = [
        view
        for note in notes
        if (view := _view(note, team, note.id in acknowledged or note.date <= joined))
    ]
    newest = views[0] if views else None
    show = (
        newest.id
        if newest and not newest.seen and any(h.kind != Kind.fixed.value for h in newest.highlights)
        else None
    )
    return WhatsNewResponse(notes=views, show=show)


async def mark_seen(db: AsyncSession, user: User, note_ids: list[str], notes: tuple[Note, ...]) -> None:
    """Record the notes as seen. Seeing a note twice keeps the first time."""
    known = {n.id for n in notes}
    if unknown := sorted(set(note_ids) - known):
        raise DomainError(
            status.HTTP_404_NOT_FOUND, f"No What's new note {', '.join(unknown)}.", "note_not_found"
        )
    await db.execute(
        insert(UserAcknowledgement)
        .values([
            {"user_id": user.id, "kind": AcknowledgementKind.note.value, "key": note_id}
            for note_id in sorted(set(note_ids))
        ])
        .on_conflict_do_nothing()
    )
    await db.commit()
