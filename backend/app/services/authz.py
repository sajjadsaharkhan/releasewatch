"""Authorization glue — turns ORM rows into Policy inputs and Policy denials into HTTP errors.

``app/policy.py`` stays pure; this module is the one place that knows how to
snapshot a ``User``/``Issue``/``Project`` for it, how a denial maps to a
status code (404 when the actor may not know the item exists, 403
otherwise), and how Support visibility (BR-30) is expressed as SQL.

Every read path over issues filters through ``visibility_clause`` /
``visible_issues`` — lists, detail, by-number, export, search, timeline,
attachments, inbox.
"""

from typing import Any

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app import policy
from app.core.auth import get_current_user
from app.core.errors import DomainError
from app.db.models.issue import Issue, IssueSource
from app.db.models.issue_subscriber import IssueSubscriber
from app.db.models.project import Project
from app.db.models.user import User, UserRole
from app.policy import Actor, Target


def actor_of(user: User) -> Actor:
    return Actor(id=user.id, role=getattr(user.role, "value", user.role))


def project_target(project: Project | None) -> Target:
    if project is None:
        return Target()
    return Target(
        project_id=project.id,
        project_kind=getattr(project.kind, "value", project.kind),
        triage_lead_id=project.triage_lead_id,
    )


def issue_target(issue: Issue, project: Project | None = None, **extra: Any) -> Target:
    """Snapshot an issue. ``project`` defaults to ``issue.project`` when it's already loaded."""
    if project is None:
        project = issue.__dict__.get("project")  # never trigger a lazy load in async code
    subscriptions = issue.__dict__.get("subscriptions") or ()
    return Target(
        item_id=issue.id,
        item_type=getattr(issue.type, "value", issue.type),
        status=getattr(issue.status, "value", issue.status),
        source=getattr(issue.source, "value", issue.source),
        subscriber_ids=frozenset(s.user_id for s in subscriptions),
        assignee_id=issue.assignee_id,
        reporter_id=issue.reporter_id,
        project_id=issue.project_id,
        project_kind=getattr(project.kind, "value", project.kind) if project is not None else None,
        triage_lead_id=project.triage_lead_id if project is not None else None,
        **extra,
    )


def raise_if_denied(decision: policy.Decision) -> None:
    if decision.ok:
        return
    if decision.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    raise DomainError(status.HTTP_403_FORBIDDEN, decision.detail, decision.code)


def authorize(user: User, action: Any, target: Target | None = None) -> None:
    """Raise 404/403 unless Policy allows ``user`` to do ``action`` on ``target``."""
    raise_if_denied(policy.decide(actor_of(user), action, target))


def require_action(action: policy.Action):
    """Dependency factory for actions that aren't about one item or project.

    Usage: ``current_user: User = Depends(require_action(Action.manage_users))``.
    """

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        authorize(current_user, action)
        return current_user

    return _check


# ── Visibility (BR-30) ────────────────────────────────────────────────────────


def support_visibility_clause(user: User):
    """SQL for what Support may see (BR-30): support-sourced items, plus items
    the user is subscribed to (slice 06 — a report merged into an internal original)."""
    subscribed = select(IssueSubscriber.issue_id).where(IssueSubscriber.user_id == user.id)
    return or_(Issue.source == IssueSource.support.value, Issue.id.in_(subscribed))


def visibility_clause(user: User):
    """WHERE clause restricting ``Issue`` rows to what ``user`` may see."""
    if getattr(user.role, "value", user.role) == UserRole.support.value:
        return support_visibility_clause(user)
    return true()


def visible_issues(user: User) -> Select:
    """The base ``select(Issue)`` every issue read path starts from."""
    return select(Issue).where(Issue.deleted_at.is_(None), visibility_clause(user))


def sees_internal(user: User) -> bool:
    """BR-31 — internal notes are for tech roles only."""
    return policy.is_tech(user.role)


async def load_visible_issue(db: AsyncSession, issue_id: int, user: User, *options) -> Issue:
    """Fetch a non-deleted issue the user may see, or 404 (never 403 — no probing, spec note)."""
    q = visible_issues(user).where(Issue.id == issue_id)
    if options:
        q = q.options(*options)
    issue = (await db.execute(q)).scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return issue


async def authorize_issue(
    db: AsyncSession, issue_id: int, user: User, action: Any, **extra: Any,
) -> Issue:
    """Load a visible issue with its project and check ``action`` on it."""
    from sqlalchemy.orm import selectinload

    issue = await load_visible_issue(db, issue_id, user, selectinload(Issue.project))
    authorize(user, action, issue_target(issue, issue.project, **extra))
    return issue

