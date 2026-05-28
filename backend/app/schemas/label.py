"""Label schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LabelBase(BaseModel):
    """Fields shared between create and update."""

    name: str = Field(max_length=64, description="Label name, e.g. 'auth', 'payments'")
    color: str = Field(
        max_length=7,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color code, e.g. '#ef4444'",
    )


class LabelCreate(LabelBase):
    """Payload for POST /labels."""


class LabelUpdate(BaseModel):
    """Partial payload for PATCH /labels/{id}."""

    name: Optional[str] = Field(None, max_length=64)
    color: Optional[str] = Field(None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")


class LabelResponse(LabelBase):
    """Full label representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class LabelWithCount(LabelResponse):
    """Label with the number of issues using it."""

    issue_count: int = Field(
        default=0,
        serialization_alias="issueCount",
        description="Number of issues with this label"
    )
