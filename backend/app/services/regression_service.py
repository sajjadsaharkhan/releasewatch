"""RegressionService — component fragility, read from cycles (08a Part 2).

Phase 1 recorded regressions in ``regression_history``; the v3 cycle model
(docs/phase-2/cycle-model.md) replaces it. Fragility counts the Phase 1
regression set (``app/services/cycle_metrics.py``) and attributes each cycle
to the container of the cycle before it — the container that shipped the work
that came back (CY-04).
"""

from collections import defaultdict
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models.issue import Issue
from app.db.models.issue_cycle import IssueCycle
from app.db.models.release import Release, ReleaseKind
from app.services.cycle_metrics import regression_cycles


class RegressionService:
    """Fragility analytics over the Phase 1 regression set."""

    async def get_component_fragility(
        self,
        db: AsyncSession,
        project_id: int,
        n_releases: int = 10,
    ) -> list[dict[str, Any]]:
        """Return the components (labels) with the highest regression frequency
        across the project's last ``n_releases`` releases.

        Each entry: ``{label, regression_count, affected_issues}``.
        """
        release_ids = (await db.execute(
            select(Release.id)
            .where(Release.project_id == project_id, Release.kind == ReleaseKind.release.value)
            .order_by(Release.created_at.desc())
            .limit(n_releases)
        )).scalars().all()
        if not release_ids:
            return []

        previous = aliased(IssueCycle)
        rows = (await db.execute(
            regression_cycles()
            .join(previous, and_(
                previous.issue_id == IssueCycle.issue_id,
                previous.cycle_number == IssueCycle.cycle_number - 1,
            ))
            .where(Issue.project_id == project_id, previous.release_id.in_(release_ids))
            .with_only_columns(Issue.id, Issue.labels, func.count(IssueCycle.id))
            .group_by(Issue.id, Issue.labels)
        )).all()

        label_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"label": "", "regression_count": 0, "affected_issues": 0}
        )
        for _issue_id, labels, count in rows:
            for label in (labels or []):
                label_stats[label]["label"] = label
                label_stats[label]["regression_count"] += count
                label_stats[label]["affected_issues"] += 1

        return sorted(label_stats.values(), key=lambda x: x["regression_count"], reverse=True)


# Module-level singleton
regression_service = RegressionService()
