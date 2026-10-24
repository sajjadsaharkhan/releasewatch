"""What's new (TASK-575) — notes as one person's team sees them."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class TourStepOut(BaseModel):
    anchor: str
    title: str
    body: str
    advance: Literal["next", "click"]
    route: str | None


class HighlightOut(BaseModel):
    kind: Literal["new", "improved", "fixed"]
    title: str
    icon: str | None
    body: str | None
    tour: list[TourStepOut]


class NoteOut(BaseModel):
    id: str
    date: date
    title: str
    summary: str
    #: Only the highlights for the reader's team.
    highlights: list[HighlightOut]
    seen: bool


class WhatsNewResponse(BaseModel):
    #: The reader's team's notes, newest first; a note with nothing for them is left out.
    notes: list[NoteOut]
    #: The note whose modal opens now: the newest one, while unseen and with
    #: something new or improved for the reader. ``None`` otherwise.
    show: str | None


class SeenRequest(BaseModel):
    note_ids: list[str] = Field(min_length=1, max_length=100)
