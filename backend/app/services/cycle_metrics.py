"""The Phase 1 regression set, read from cycles (08a Part 2).

Phase 1 recorded a regression when a bug in a release was sent back from In
review or from Done before its release shipped. Those are exactly the cycles
with ``start_reason in (review, release_qa)`` of a bug whose cycle container
is a Release (``kind = release``) — so every Phase 1 report reads this one
predicate and keeps its numbers. Cycles in the Stream, ``production`` returns
and task cycles stay out (CY-09: Phase 3 reports them per reason).
"""

from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue import Issue, IssueType
from app.db.models.issue_cycle import PHASE1_REGRESSION_REASONS, IssueCycle
from app.db.models.release import Release, ReleaseKind

_REASONS = tuple(r.value for r in PHASE1_REGRESSION_REASONS)


def regression_cycle_clause(cycle=IssueCycle):
    """A cycle Phase 1 would have recorded as a regression (the item's type is
    checked by the caller's join to ``Issue``, see ``regression_cycles``)."""
    return and_(
        cycle.start_reason.in_(_REASONS),
        cycle.release_id.in_(select(Release.id).where(Release.kind == ReleaseKind.release.value)),
    )


def regression_cycles():
    """``select(IssueCycle)`` joined to its bug, limited to the Phase 1 set."""
    return (
        select(IssueCycle)
        .join(Issue, Issue.id == IssueCycle.issue_id)
        .where(Issue.type == IssueType.bug.value, regression_cycle_clause())
    )


def regression_count_expr(issue=Issue):
    """Per-item Phase 1 regression count, as a correlated SQL expression."""
    count = (
        select(func.count(IssueCycle.id))
        .where(IssueCycle.issue_id == issue.id, regression_cycle_clause())
        .correlate(issue)
        .scalar_subquery()
    )
    return case((issue.type == IssueType.bug.value, count), else_=0)


def is_regression_expr(issue=Issue):
    """Phase 1's ``is_regression`` flag, as SQL: a bug with at least one such cycle."""
    return and_(
        issue.type == IssueType.bug.value,
        exists().where(IssueCycle.issue_id == issue.id, regression_cycle_clause()),
    )


async def regression_counts(db: AsyncSession, issue_ids) -> dict[int, int]:
    """``{issue_id: count}`` for items with at least one Phase 1 regression cycle."""
    ids = list(issue_ids)
    if not ids:
        return {}
    rows = (await db.execute(
        regression_cycles()
        .with_only_columns(IssueCycle.issue_id, func.count(IssueCycle.id))
        .where(IssueCycle.issue_id.in_(ids))
        .group_by(IssueCycle.issue_id)
    )).all()
    return {issue_id: count for issue_id, count in rows}
