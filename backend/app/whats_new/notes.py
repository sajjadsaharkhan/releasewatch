"""Loading and validating What's new notes (TASK-575).

A note is ``notes/<YYYY-MM-DD>.md``: YAML front matter between two ``---``
lines and nothing after it, in the format ``AUTHORING.md`` defines. Notes are
versioned with the code, so a bad one fails ``make test`` rather than a
request: every rule the guide states that a parser can check is checked here.
"""

import enum
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NOTES_DIR = Path(__file__).resolve().parent / "notes"

_ANCHOR = r"^[a-z0-9]+(-[a-z0-9]+)*$"
_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n?\Z", re.DOTALL)


class Team(str, enum.Enum):
    """Who a highlight is for. ``tech`` is every role but Support."""

    tech = "tech"
    support = "support"


class Kind(str, enum.Enum):
    new = "new"
    improved = "improved"
    fixed = "fixed"


def _words(text: str) -> int:
    return len(text.split())


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TourStep(_Strict):
    anchor: str = Field(pattern=_ANCHOR)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    advance: Literal["next", "click"] = "next"
    route: str | None = Field(default=None, pattern=r"^/")

    @field_validator("title")
    @classmethod
    def _short_title(cls, v: str) -> str:
        if _words(v) > 5:
            raise ValueError("a tour step title is at most 5 words")
        return v

    @field_validator("body")
    @classmethod
    def _short_body(cls, v: str) -> str:
        if _words(v) > 15:
            raise ValueError("a tour step body is at most 15 words")
        return v


class Highlight(_Strict):
    kind: Kind
    teams: list[Team] = Field(min_length=1)
    title: str = Field(min_length=1)
    icon: str | None = Field(default=None, pattern=_ANCHOR)
    body: str | None = None
    tour: list[TourStep] = Field(default_factory=list)

    @field_validator("teams")
    @classmethod
    def _distinct(cls, v: list[Team]) -> list[Team]:
        if len(set(v)) != len(v):
            raise ValueError("teams are listed once each")
        return v

    @model_validator(mode="after")
    def _shape_by_kind(self) -> "Highlight":
        if self.kind is Kind.fixed:
            if self.icon or self.body or self.tour:
                raise ValueError("a fixed highlight has a title only")
        elif not (self.icon and self.body and self.tour):
            raise ValueError(f"a {self.kind.value} highlight needs an icon, a body and a tour")
        return self


class Headline(_Strict):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class Note(_Strict):
    id: str
    date: date
    headline: dict[Team, Headline]
    highlights: list[Highlight] = Field(min_length=1)

    @model_validator(mode="after")
    def _headline_per_team(self) -> "Note":
        if self.id != self.date.isoformat():
            raise ValueError(f"the file name must be the note's date ({self.date.isoformat()}.md)")
        teams = {team for h in self.highlights for team in h.teams}
        if missing := teams - self.headline.keys():
            raise ValueError(f"no headline for {', '.join(sorted(t.value for t in missing))}")
        if extra := self.headline.keys() - teams:
            raise ValueError(f"a headline for {', '.join(sorted(t.value for t in extra))}, who has no highlight")
        return self

    def anchors(self) -> set[str]:
        return {step.anchor for h in self.highlights for step in h.tour}


def parse_note(path: Path) -> Note:
    match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"{path.name}: front matter between two '---' lines, nothing after it")
    data = yaml.safe_load(match.group(1)) or {}
    return Note.model_validate({**data, "id": path.stem})


@lru_cache
def load_notes(notes_dir: Path = NOTES_DIR) -> tuple[Note, ...]:
    """Every note in ``notes_dir``, newest first. Cached: notes ship with the code."""
    notes = [parse_note(p) for p in notes_dir.glob("*.md")]
    return tuple(sorted(notes, key=lambda n: n.date, reverse=True))


def get_notes() -> tuple[Note, ...]:
    """FastAPI dependency; tests override it with their own notes."""
    return load_notes()
