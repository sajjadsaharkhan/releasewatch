"""The Agent ownership loader (slice 18, prd-mcp.md A.5).

Gathers what ``app/agent_ownership.py`` needs for one item — the latest
relevant timeline record of each item-level piece, in one query, and the
user's token ids — and answers per piece. ``rw_update_own``, ``rw_delete_own``
and ``rw_get_item``'s ``you_can_edit`` all come through here, so the tools and
the flags cannot disagree.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_ownership import ItemState, Piece, Record, Verdict, decide
from app.db.models.issue import BACKLOG_STATUSES, Issue
from app.db.models.issue_attachment import IssueAttachment
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.mcp_token import McpToken
from app.db.models.user import User

T = TimelineEventType
#: The event that records a change of each item-level piece; ``filed`` is the fallback.
PIECE_EVENTS: dict[str, TimelineEventType] = {
    "title": T.title_changed,
    "description": T.description_changed,
    "reproduction_steps": T.steps_changed,
    "environment": T.environment_changed,
    "curl": T.curl_changed,
}
_BACKLOG = {getattr(s, "value", s) for s in BACKLOG_STATUSES}


def _value(v):
    return getattr(v, "value", v)


def note_record(note: IssueTimeline) -> Record:
    """A note's last writer: the edit stamp if it was edited, else its author."""
    meta = note.meta or {}
    if meta.get("edited_by") is not None:
        return Record(int(meta["edited_by"]), meta.get("edited_via_mcp_token_id"))
    return Record(note.actor_id, note.via_mcp_token_id)


@dataclass(frozen=True)
class ItemOwnership:
    """The last-writer verdicts for one item and one user."""

    item: ItemState
    user_id: int
    token_ids: frozenset[int]
    #: Latest record per event type value, ``filed`` included.
    latest: dict[str, Record]

    def _decide(self, piece: Piece, record: Record | None) -> Verdict:
        return decide(self.item, piece, record, self.user_id, self.token_ids)

    def _latest(self, name: str) -> Record | None:
        return self.latest.get(PIECE_EVENTS[name].value) or self.latest.get(T.filed.value)

    def title(self) -> Verdict:
        return self._decide(Piece.title, self._latest("title"))

    def description(self) -> Verdict:
        return self._decide(Piece.description, self._latest("description"))

    def field(self, name: str) -> Verdict:
        return self._decide(Piece.field, self._latest(name))

    def note(self, note: IssueTimeline) -> Verdict:
        return self._decide(Piece.note, note_record(note))

    def attachment(self, attachment: IssueAttachment) -> Verdict:
        return self._decide(
            Piece.attachment, Record(attachment.uploaded_by_id, attachment.via_mcp_token_id),
        )


async def load(db: AsyncSession, issue: Issue, user: User) -> ItemOwnership:
    kinds = [T.filed.value, *(e.value for e in PIECE_EVENTS.values())]
    rows = (await db.execute(
        select(IssueTimeline.event_type, IssueTimeline.actor_id, IssueTimeline.via_mcp_token_id)
        .where(IssueTimeline.issue_id == issue.id, IssueTimeline.event_type.in_(kinds))
        .distinct(IssueTimeline.event_type)
        .order_by(
            IssueTimeline.event_type, IssueTimeline.created_at.desc(), IssueTimeline.id.desc(),
        )
    )).all()
    # Any of the user's tokens counts, active or not (BR-M07, AC-M32).
    token_ids = frozenset((await db.execute(
        select(McpToken.id).where(McpToken.user_id == user.id)
    )).scalars())
    return ItemOwnership(
        item=ItemState(
            type=_value(issue.type),
            status=_value(issue.status),
            in_backlog=issue.release_id is None and _value(issue.status) in _BACKLOG,
            filed_by_agent=issue.via_mcp_token_id is not None,
        ),
        user_id=user.id,
        token_ids=token_ids,
        latest={_value(kind): Record(actor, token) for kind, actor, token in rows},
    )
