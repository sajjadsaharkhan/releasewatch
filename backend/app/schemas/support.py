"""Support intake schemas (slice 05) — templates, report submission, the Support reports list."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.issue import IssueStatus
from app.db.models.support_template import FieldType
from app.schemas.attachment import PendingAttachment
from app.schemas.issue import UserSummary


class SelectOption(BaseModel):
    value: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)


class TemplateFieldIn(BaseModel):
    """One field in ``PUT /projects/{id}/templates/{tid}/fields``. List order is the form order.

    Pass ``id`` to keep an existing field (so a form a Support user already has
    open keeps working); omit it to add a new one. Fields left out are removed.
    """

    id: int | None = None
    label: str = Field(min_length=1, max_length=120)
    field_type: FieldType
    is_required: bool = False
    help_text: str | None = Field(None, max_length=500)
    options: list[SelectOption] | None = None

    @model_validator(mode="after")
    def _options_for_select_only(self) -> "TemplateFieldIn":
        if self.field_type == FieldType.single_select:
            if not self.options:
                raise ValueError("A single-select field needs at least one option.")
            values = [o.value for o in self.options]
            if len(values) != len(set(values)):
                raise ValueError("Option values must be unique.")
        else:
            self.options = None
        return self


class TemplateFieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    label: str
    field_type: FieldType
    is_required: bool
    help_text: str | None = None
    options: list[SelectOption] | None = None


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    fields: list[TemplateFieldIn] = Field(default_factory=list)
    #: The Settings UI creates templates switched off, so Support never sees a
    #: half-built form; the admin turns it live when it's ready.
    is_active: bool = True


class TemplateUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    is_active: bool
    position: int
    created_at: datetime
    updated_at: datetime
    fields: list[TemplateFieldResponse] = Field(default_factory=list)


class SupportProject(BaseModel):
    """A project Support can report on (has at least one active template)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    color: str


class SupportReportCreate(BaseModel):
    template_id: int
    title: str = Field(min_length=1, max_length=512)
    #: ``{field_id: value}``. JSON keys arrive as strings.
    values: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None
    pending_attachments: list[PendingAttachment] = Field(default_factory=list)


class SupportReportRow(BaseModel):
    """One row of the Support reports list (FR-11)."""

    id: int
    issue_number: int
    key: str
    title: str
    status: IssueStatus
    project_id: int
    project_name: str
    project_color: str | None = None
    recurrence_count: int
    reporter_name: str | None = None
    #: Who filed it — Support works as a team, so the list shows whose report it is.
    reporter_user: UserSummary | None = None
    #: Who is working on it — shown with a user hover card in the list.
    assignee_user: UserSummary | None = None
    created_at: datetime
    updated_at: datetime


class SupportReportList(BaseModel):
    items: list[SupportReportRow]
    total: int
    page: int
    size: int
