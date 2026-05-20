"""RegressionService — detection and analysis of regressed issues.

A regression occurs when an issue transitions back to ``regression`` status
in a new release after previously being ``verified`` or ``closed``.
"""

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue import Issue, IssueStatus
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.regression_history import RegressionHistory
from app.db.models.release import Release
from app.db.models.user import User


class RegressionService:
    """Handles regression recording and fragility analytics."""

    # ── Recording ─────────────────────────────────────────────────────────────

    async def record_regression(
        self,
        db: AsyncSession,
        issue: Issue,
        release: Release,
        detected_by: User,
    ) -> RegressionHistory:
        """Record a regression event for an issue and update its counter.

        Should be called whenever an issue's status is set to ``regression``.
        Finds the most recent ``fixed`` timeline event to back-link the previous
        fix author.

        Parameters
        ----------
        db:
            Active async session.
        issue:
            The regressed ``Issue`` row (already updated to ``regression`` status).
        release:
            The release in which the regression was detected.
        detected_by:
            The user who identified the regression.

        Returns
        -------
        RegressionHistory
            The newly created history row.
        """
        # Find the most recent "fixed" event for this issue
        fix_event_result = await db.execute(
            select(IssueTimeline)
            .where(
                IssueTimeline.issue_id == issue.id,
                IssueTimeline.event_type == TimelineEventType.fixed,
            )
            .order_by(IssueTimeline.created_at.desc())
            .limit(1)
        )
        last_fix_event = fix_event_result.scalar_one_or_none()

        regression_number = (issue.regression_count or 0) + 1
        issue.regression_count = regression_number
        issue.is_regression = True
        db.add(issue)

        history = RegressionHistory(
            issue_id=issue.id,
            release_id=release.id,
            regression_number=regression_number,
            detected_by_id=detected_by.id,
            previous_fix_by_id=last_fix_event.actor_id if last_fix_event else None,
            previous_fix_timeline_id=last_fix_event.id if last_fix_event else None,
        )
        db.add(history)
        await db.flush()
        return history

    # ── Fragility analysis ────────────────────────────────────────────────────

    async def get_component_fragility(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        n_releases: int = 10,
    ) -> list[dict[str, Any]]:
        """Return the components (labels) with the highest regression frequency.

        Aggregates regressions across the last ``n_releases`` releases ordered
        by recency and groups them by label string.

        Parameters
        ----------
        db:
            Active async session.
        project_id:
            UUID of the project to analyse.
        n_releases:
            How many recent releases to consider.

        Returns
        -------
        list of dict
            Each entry: ``{label, regression_count, affected_issues}``.
        """
        # Fetch the N most recent releases for the project
        releases_result = await db.execute(
            select(Release.id)
            .where(Release.project_id == project_id)
            .order_by(Release.created_at.desc())
            .limit(n_releases)
        )
        release_ids = [row[0] for row in releases_result.all()]
        if not release_ids:
            return []

        # Fetch regressed issues in those releases
        issues_result = await db.execute(
            select(Issue)
            .where(
                Issue.project_id == project_id,
                Issue.release_id.in_(release_ids),
                Issue.is_regression.is_(True),
            )
        )
        regressed_issues = issues_result.scalars().all()

        # Tally by label
        label_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"label": "", "regression_count": 0, "affected_issues": 0}
        )
        for iss in regressed_issues:
            for label in (iss.labels or []):
                label_stats[label]["label"] = label
                label_stats[label]["regression_count"] += iss.regression_count
                label_stats[label]["affected_issues"] += 1

        return sorted(
            label_stats.values(),
            key=lambda x: x["regression_count"],
            reverse=True,
        )

    # ── Recurrence matrix ─────────────────────────────────────────────────────

    async def get_recurrence_matrix(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Build a recurrence matrix: releases × issue regression counts.

        Returns a dict suitable for rendering as a heatmap on the dashboard.

        Parameters
        ----------
        db:
            Active async session.
        project_id:
            UUID of the project.

        Returns
        -------
        dict
            ``{releases: [...], issues: [...], matrix: [[...]]}``.
        """
        # Load all regression history rows for the project
        result = await db.execute(
            select(RegressionHistory)
            .join(Issue, RegressionHistory.issue_id == Issue.id)
            .where(Issue.project_id == project_id)
            .order_by(RegressionHistory.detected_at)
        )
        histories = result.scalars().all()

        # Collect unique release and issue IDs (preserving order)
        seen_releases: list[uuid.UUID] = []
        seen_issues: list[uuid.UUID] = []
        cell: dict[tuple[uuid.UUID, uuid.UUID], int] = defaultdict(int)

        for h in histories:
            if h.release_id not in seen_releases:
                seen_releases.append(h.release_id)
            if h.issue_id not in seen_issues:
                seen_issues.append(h.issue_id)
            cell[(h.release_id, h.issue_id)] += 1

        # Build 2-D matrix (rows=releases, cols=issues)
        matrix = [
            [cell.get((rel_id, iss_id), 0) for iss_id in seen_issues]
            for rel_id in seen_releases
        ]

        return {
            "releases": [str(r) for r in seen_releases],
            "issues": [str(i) for i in seen_issues],
            "matrix": matrix,
        }


# Module-level singleton
regression_service = RegressionService()
