"""Agent ownership — the last-writer rule (slice 18, prd-mcp.md BR-M07, BR-M14, A.5).

A pure module, like ``app/workflow.py`` and ``app/policy.py``: plain values in,
a verdict and a reason out, no database or HTTP access. It is the only place
the last-writer rule is written.

An agent may edit or delete a piece of content only while the piece's **last
writer** is the same user through MCP, with any of the user's tokens (active or
not). Once a person changes the piece in the UI, its last writer is that person
with no token, and the agent can no longer touch it.

The caller finds the latest relevant record of the piece (A.5) and passes its
actor and token:

| Piece | Latest relevant record |
|---|---|
| Title | latest ``title_changed``, else ``filed`` |
| Description | latest ``description_changed``, else ``filed`` |
| Reproduction steps | latest ``steps_changed``, else ``filed`` |
| Environment | latest ``environment_changed``, else ``filed`` |
| cURL | latest ``curl_changed``, else ``filed`` |
| Note | the edit stamp in ``meta`` if present, else the note's actor and token |
| Attachment | uploader and token |

``app/services/agent_ownership_loader.py`` gathers those records for one item.
"""

from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum


class Piece(StrEnum):
    note = "note"
    field = "field"
    attachment = "attachment"
    title = "title"
    description = "description"


#: Fields of a bug the agent may fill (slice 17) and then edit.
FIELDS: tuple[str, ...] = ("reproduction_steps", "curl", "environment")

NOT_OWNER = "not_owner"
ITEM_CLOSED = "item_closed"
ITEM_TRIAGED = "item_triaged"

_CLOSED = frozenset({"done", "cancelled"})


@dataclass(frozen=True)
class ItemState:
    """What the rule needs to know about the item."""

    type: str
    status: str
    #: A task with no container in a backlog status (BR-04).
    in_backlog: bool
    #: The item has ``via_mcp_token_id`` set — an agent filed it.
    filed_by_agent: bool


@dataclass(frozen=True)
class Record:
    """The latest relevant record of a piece: who wrote it, through which token."""

    actor_id: int | None
    token_id: int | None


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    code: str | None = None
    reason: str | None = None


ALLOWED = Verdict(True)


def decide(
    item: ItemState,
    piece: Piece,
    record: Record | None,
    user_id: int,
    user_token_ids: Collection[int],
) -> Verdict:
    """May ``user_id``'s agent edit or delete this piece now?"""
    piece = Piece(piece)
    owned = (
        record is not None
        and record.actor_id == user_id
        and record.token_id is not None
        and record.token_id in user_token_ids
    )
    if piece in (Piece.title, Piece.description) and not item.filed_by_agent:
        owned = False
    if not owned:
        return Verdict(
            False, NOT_OWNER,
            f"Your agent is not the last writer of this {piece.value}: a person, or "
            "another user's agent, changed it last. Add a note instead.",
        )

    if piece is Piece.field and item.status in _CLOSED:
        return Verdict(
            False, ITEM_CLOSED,
            f"The bug is {item.status.capitalize()}; its fields are final. Add a note instead.",
        )
    if piece in (Piece.title, Piece.description):
        open_for_edit = (
            item.status == "new" if item.type == "bug" else item.in_backlog
        )
        if not open_for_edit:
            where = "is no longer New" if item.type == "bug" else "is no longer in the backlog"
            return Verdict(
                False, ITEM_TRIAGED,
                f"The item {where}, so its {piece.value} is final. Add a note instead.",
            )
    return ALLOWED

