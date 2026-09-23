"""Support templates (slice 05, FR-44) — the per-project forms Support fills in.

A template is an ordered list of fields. Submitting one composes the values
into the new item's description (``app/support_report.py``); the values are
never stored as columns (BR-34), so editing or deactivating a template never
rewrites an existing report (BR-35).
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FieldType(str, enum.Enum):
    """Input kinds a template field can ask for (§8.3)."""

    short_text = "short_text"
    long_text = "long_text"
    number = "number"
    date = "date"
    datetime = "datetime"
    single_select = "single_select"
    url = "url"


class SupportTemplate(Base):
    __tablename__ = "support_templates"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_support_templates_project_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    project = relationship("Project")
    fields = relationship(
        "SupportTemplateField", back_populates="template",
        cascade="all, delete-orphan", order_by="SupportTemplateField.position",
    )

    def __repr__(self) -> str:
        return f"<SupportTemplate id={self.id} project={self.project_id} name={self.name!r}>"


class SupportTemplateField(Base):
    __tablename__ = "support_template_fields"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "position", name="uq_support_template_fields_template_position",
            deferrable=True, initially="DEFERRED",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("support_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    field_type: Mapped[FieldType] = mapped_column(String(16), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Single select only: ``[{"value": "...", "label": "..."}]``.
    options: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    template = relationship("SupportTemplate", back_populates="fields")
