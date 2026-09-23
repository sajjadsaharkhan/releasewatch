"""SupportService — support templates and support reports (slice 05, FR-07–12, FR-44/45).

Templates are per-project forms. A report is a bug filed through
``IssueService.create`` with ``source=support`` and a description composed
from the template (``app/support_report.py``). Having an active template is
what makes a project reportable — there is no separate toggle (05 notes).
"""

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import DomainError
from app.db.models.issue import Issue, IssueSource, IssueStatus, IssueType, issue_key
from app.db.models.project import Project
from app.db.models.support_template import SupportTemplate, SupportTemplateField
from app.db.models.user import User
from app.schemas.issue import IssueCreate, UserSummary
from app.schemas.support import (
    SupportReportCreate,
    SupportReportList,
    SupportReportRow,
    TemplateCreate,
    TemplateFieldIn,
)
from app.services.authz import visible_issues
from app.support_report import FieldSpec, TemplateSpec, compose_report


def template_spec(template: SupportTemplate) -> TemplateSpec:
    """Snapshot an ORM template (fields loaded) for ``compose_report``."""
    return TemplateSpec(
        id=template.id,
        name=template.name,
        fields=tuple(
            FieldSpec(
                id=f.id,
                label=f.label,
                field_type=getattr(f.field_type, "value", f.field_type),
                is_required=f.is_required,
                options=tuple(f.options or ()),
            )
            for f in sorted(template.fields, key=lambda f: f.position)
        ),
    )


def report_row(issue: Issue) -> SupportReportRow:
    """One Support reports row. Needs ``project``, ``reporter`` and ``assignee`` loaded."""
    return SupportReportRow(
        id=issue.id,
        issue_number=issue.issue_number,
        key=issue_key(issue.type, issue.issue_number),
        title=issue.title,
        status=issue.status,
        project_id=issue.project_id,
        project_name=issue.project.name,
        project_color=issue.project.color,
        recurrence_count=issue.recurrence_count,
        reporter_name=issue.reporter.name if issue.reporter else None,
        assignee_user=UserSummary.model_validate(issue.assignee) if issue.assignee else None,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


async def load_report(db: AsyncSession, issue_id: int) -> Issue:
    return (await db.execute(
        select(Issue)
        .options(selectinload(Issue.project), selectinload(Issue.reporter), selectinload(Issue.assignee))
        .where(Issue.id == issue_id)
        .execution_options(populate_existing=True)
    )).scalar_one()


def _active_project_clause():
    return Project.archived_at.is_(None)


class SupportService:
    # ── Support-facing reads ────────────────────────────────────────────────

    async def reportable_projects(self, db: AsyncSession) -> list[Project]:
        """Projects with at least one active template (FR-08, BR-33, AC-01)."""
        has_active = (
            select(SupportTemplate.id)
            .where(SupportTemplate.project_id == Project.id, SupportTemplate.is_active.is_(True))
            .exists()
        )
        result = await db.execute(
            select(Project).where(_active_project_clause(), has_active).order_by(Project.name)
        )
        return list(result.scalars().all())

    async def template_counts(self, db: AsyncSession, project_id: int) -> tuple[int, int]:
        """``(all, active)`` template counts for one project — shown in Settings."""
        row = (await db.execute(
            select(
                func.count(SupportTemplate.id),
                func.count(SupportTemplate.id).filter(SupportTemplate.is_active.is_(True)),
            ).where(SupportTemplate.project_id == project_id)
        )).one()
        return int(row[0]), int(row[1])

    async def active_templates(self, db: AsyncSession, project_id: int) -> list[SupportTemplate]:
        result = await db.execute(
            select(SupportTemplate)
            .options(selectinload(SupportTemplate.fields))
            .join(Project, Project.id == SupportTemplate.project_id)
            .where(
                SupportTemplate.project_id == project_id,
                SupportTemplate.is_active.is_(True),
                _active_project_clause(),
            )
            .order_by(SupportTemplate.position, SupportTemplate.id)
        )
        return list(result.scalars().all())

    # ── Submission ──────────────────────────────────────────────────────────

    async def submit(self, db: AsyncSession, payload: SupportReportCreate, actor: User) -> Issue:
        """Validate, compose, and file a support report as a New bug (FR-10, AC-02/03/05)."""
        from app.services.issue_service import issue_service

        template = (await db.execute(
            select(SupportTemplate)
            .options(selectinload(SupportTemplate.fields), selectinload(SupportTemplate.project))
            .where(SupportTemplate.id == payload.template_id)
        )).scalar_one_or_none()
        if template is None or template.project.archived_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        if not template.is_active:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "This template is no longer available. Your answers are still here — "
                "copy them into another template.",
                "template_inactive",
            )

        composed = compose_report(template_spec(template), payload.values, payload.description)
        if composed.errors:
            raise DomainError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Some fields need attention.",
                "invalid_fields",
                errors=composed.errors,
            )

        data = IssueCreate(
            type=IssueType.bug,
            project_id=template.project_id,
            title=payload.title.strip(),
            description=composed.markdown,
            pending_attachments=payload.pending_attachments,
        )
        return await issue_service.create(
            db, data, actor,
            source=IssueSource.support,
            # Forensic copy only — the UI never reads it (BR-34).
            filed_meta={
                "template_id": template.id,
                "template_name": template.name,
                "values": composed.values,
            },
        )

    # ── Support reports list (FR-11) ────────────────────────────────────────

    async def list_reports(
        self,
        db: AsyncSession,
        actor: User,
        *,
        q: str | None = None,
        project_id: int | None = None,
        statuses: list[IssueStatus] | None = None,
        page: int = 1,
        size: int = 50,
    ) -> SupportReportList:
        base = visible_issues(actor).where(Issue.source == IssueSource.support.value)
        if project_id:
            base = base.where(Issue.project_id == project_id)
        if statuses:
            base = base.where(Issue.status.in_([s.value for s in statuses]))
        if q and q.strip():
            term = f"%{q.strip()}%"
            base = base.where(or_(
                Issue.title.ilike(term),
                Issue.description.ilike(term),
                cast(Issue.issue_number, String).ilike(term),
            ))

        total = (await db.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()

        rows = (await db.execute(
            base.options(selectinload(Issue.project), selectinload(Issue.reporter), selectinload(Issue.assignee))
            .order_by(Issue.updated_at.desc(), Issue.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )).scalars().all()

        return SupportReportList(
            items=[report_row(i) for i in rows],
            total=total,
            page=page,
            size=size,
        )

    # ── Template admin (FR-44, manage_templates) ─────────────────────────────

    async def _project(self, db: AsyncSession, project_id: int) -> Project:
        project = await db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    async def get_template(
        self, db: AsyncSession, project_id: int, template_id: int,
    ) -> SupportTemplate:
        template = (await db.execute(
            select(SupportTemplate)
            .options(selectinload(SupportTemplate.fields))
            .where(SupportTemplate.id == template_id, SupportTemplate.project_id == project_id)
            .execution_options(populate_existing=True)
        )).scalar_one_or_none()
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        return template

    async def list_templates(self, db: AsyncSession, project_id: int) -> list[SupportTemplate]:
        await self._project(db, project_id)
        result = await db.execute(
            select(SupportTemplate)
            .options(selectinload(SupportTemplate.fields))
            .where(SupportTemplate.project_id == project_id)
            .order_by(SupportTemplate.position, SupportTemplate.id)
        )
        return list(result.scalars().all())

    async def _ensure_name_free(
        self, db: AsyncSession, project_id: int, name: str, exclude_id: int | None = None,
    ) -> None:
        q = select(SupportTemplate.id).where(
            SupportTemplate.project_id == project_id,
            func.lower(SupportTemplate.name) == name.strip().lower(),
        )
        if exclude_id is not None:
            q = q.where(SupportTemplate.id != exclude_id)
        if (await db.execute(q)).first() is not None:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "This project already has a template with that name.",
                "template_name_taken",
            )

    async def create_template(
        self, db: AsyncSession, project_id: int, payload: TemplateCreate, actor: User,
    ) -> SupportTemplate:
        await self._project(db, project_id)
        await self._ensure_name_free(db, project_id, payload.name)
        next_position = (await db.execute(
            select(func.coalesce(func.max(SupportTemplate.position), -1) + 1)
            .where(SupportTemplate.project_id == project_id)
        )).scalar_one()
        template = SupportTemplate(
            project_id=project_id,
            name=payload.name.strip(),
            is_active=payload.is_active,
            position=next_position,
            created_by_id=actor.id,
        )
        db.add(template)
        await db.flush()
        await self._write_fields(db, template, payload.fields, existing=[])
        return await self.get_template(db, project_id, template.id)

    async def rename_template(
        self, db: AsyncSession, project_id: int, template_id: int, name: str,
    ) -> SupportTemplate:
        template = await self.get_template(db, project_id, template_id)
        await self._ensure_name_free(db, project_id, name, exclude_id=template.id)
        template.name = name.strip()
        await db.flush()
        return await self.get_template(db, project_id, template_id)

    async def set_active(
        self, db: AsyncSession, project_id: int, template_id: int, active: bool,
    ) -> SupportTemplate:
        """Deactivate/reactivate (FR-44). Existing reports never change (BR-35, AC-04/06)."""
        template = await self.get_template(db, project_id, template_id)
        template.is_active = active
        await db.flush()
        return await self.get_template(db, project_id, template_id)

    async def replace_fields(
        self, db: AsyncSession, project_id: int, template_id: int, fields: list[TemplateFieldIn],
    ) -> SupportTemplate:
        template = await self.get_template(db, project_id, template_id)
        await self._write_fields(db, template, fields, existing=list(template.fields))
        return await self.get_template(db, project_id, template_id)

    async def _write_fields(
        self,
        db: AsyncSession,
        template: SupportTemplate,
        fields: list[TemplateFieldIn],
        existing: list[SupportTemplateField],
    ) -> None:
        """Make ``template``'s fields exactly ``fields``, in order.

        Fields sent with an ``id`` keep it, so a form a Support user already
        has open still submits cleanly; the rest are added; missing ones go.
        """
        labels = [f.label.strip().lower() for f in fields]
        if len(labels) != len(set(labels)):
            raise DomainError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Each field in a template needs a different label.",
                "duplicate_field_label",
            )
        by_id = {f.id: f for f in existing}
        unknown = [f.id for f in fields if f.id is not None and f.id not in by_id]
        if unknown:
            raise DomainError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "A field doesn't belong to this template.",
                "unknown_field",
            )

        keep_ids = {f.id for f in fields if f.id is not None}
        for f in existing:
            if f.id not in keep_ids:
                await db.delete(f)

        for position, spec in enumerate(fields):
            options = [o.model_dump() for o in spec.options] if spec.options else None
            values = dict(
                position=position,
                label=spec.label.strip(),
                field_type=spec.field_type.value,
                is_required=spec.is_required,
                help_text=(spec.help_text or None),
                options=options,
            )
            if spec.id is not None:
                row = by_id[spec.id]
                for k, v in values.items():
                    setattr(row, k, v)
            else:
                db.add(SupportTemplateField(template_id=template.id, **values))
        try:
            await db.flush()
        except IntegrityError as exc:  # pragma: no cover — guarded above
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "The field list changed underneath you.",
                "fields_conflict",
            ) from exc


support_service = SupportService()
