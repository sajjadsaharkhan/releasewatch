"""ReportService — pre-computed analytics and dashboard aggregations.

All queries are async and cache their results in Redis to avoid re-computation
on every request.  Cache is invalidated by the ``invalidate_report_cache``
Celery task whenever issues or releases are mutated.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue import Issue, IssueSeverity, IssueStatus
from app.db.models.release import Release
from app.db.models.user import User


class ReportService:
    """Analytics reports — each method may read from Redis cache first."""

    # ── Release report ────────────────────────────────────────────────────────

    async def get_release_report(
        self,
        db: AsyncSession,
        release_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Return aggregate statistics for a single release.

        Parameters
        ----------
        db:
            Active async session.
        release_id:
            UUID of the release to report on.

        Returns
        -------
        dict
            Matches ``ReleaseReportResponse`` schema.
        """
        from app.core.redis_client import get_cached, set_cached

        cache_key = f"report:release:{release_id}"
        cached = await get_cached(cache_key)
        if cached is not None:
            return cached

        release_result = await db.execute(
            select(Release).where(Release.id == release_id)
        )
        release = release_result.scalar_one_or_none()
        if release is None:
            return {}

        # Issue aggregates
        issues_result = await db.execute(
            select(Issue).where(Issue.release_id == release_id)
        )
        issues = issues_result.scalars().all()

        severity_breakdown = {s.value: 0 for s in IssueSeverity}
        status_breakdown = {s.value: 0 for s in IssueStatus}
        open_statuses = {IssueStatus.new, IssueStatus.triaged, IssueStatus.in_progress, IssueStatus.regression}

        triage_times: list[float] = []
        fix_times: list[float] = []
        verify_times: list[float] = []

        for iss in issues:
            severity_breakdown[iss.severity.value] += 1
            status_breakdown[iss.status.value] += 1
            if iss.time_to_triage_h is not None:
                triage_times.append(iss.time_to_triage_h)
            if iss.time_to_fix_h is not None:
                fix_times.append(iss.time_to_fix_h)
            if iss.time_to_verify_h is not None:
                verify_times.append(iss.time_to_verify_h)

        def avg(lst: list[float]) -> float | None:
            return round(sum(lst) / len(lst), 2) if lst else None

        report = {
            "release_id": str(release_id),
            "version": release.version,
            "project_name": release.project.name if release.project else "",
            "total_issues": len(issues),
            "open_issues": sum(1 for i in issues if i.status in open_statuses),
            "blocker_count": sum(1 for i in issues if i.is_release_blocker),
            "regression_count": sum(1 for i in issues if i.is_regression),
            "go_nogo_status": release.go_nogo_status.value,
            "severity_breakdown": severity_breakdown,
            "status_breakdown": status_breakdown,
            "avg_time_to_triage_h": avg(triage_times),
            "avg_time_to_fix_h": avg(fix_times),
            "avg_time_to_verify_h": avg(verify_times),
        }

        await set_cached(cache_key, report)
        return report

    # ── Contributions ─────────────────────────────────────────────────────────

    async def get_contributions(
        self,
        db: AsyncSession,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        """Return per-user filing / fixing / verifying counts.

        Parameters
        ----------
        db:
            Active async session.
        filters:
            Optional filter dict, keys: ``project_id``, ``release_id``,
            ``period_start`` (ISO date), ``period_end`` (ISO date).

        Returns
        -------
        dict
            Matches ``ContributionsResponse`` schema.
        """
        query = select(Issue)
        if pid := filters.get("project_id"):
            query = query.where(Issue.project_id == uuid.UUID(str(pid)))
        if rid := filters.get("release_id"):
            query = query.where(Issue.release_id == uuid.UUID(str(rid)))

        result = await db.execute(query)
        issues = result.scalars().all()

        stats: dict[str, dict[str, Any]] = {}

        def _user_entry(user_id: uuid.UUID) -> dict[str, Any]:
            return {
                "user_id": str(user_id),
                "name": "",
                "username": "",
                "issues_filed": 0,
                "issues_fixed": 0,
                "issues_verified": 0,
            }

        for iss in issues:
            if iss.reporter_id:
                uid = str(iss.reporter_id)
                stats.setdefault(uid, _user_entry(iss.reporter_id))
                stats[uid]["issues_filed"] += 1
            if iss.assignee_id and iss.status in (IssueStatus.fixed, IssueStatus.verified, IssueStatus.closed):
                uid = str(iss.assignee_id)
                stats.setdefault(uid, _user_entry(iss.assignee_id))
                stats[uid]["issues_fixed"] += 1
            if iss.verified_at and iss.status == IssueStatus.verified:
                # We don't have a verifier column — use assignee as approximation
                if iss.assignee_id:
                    uid = str(iss.assignee_id)
                    stats.setdefault(uid, _user_entry(iss.assignee_id))
                    stats[uid]["issues_verified"] += 1

        # Hydrate names from DB
        if stats:
            user_ids = [uuid.UUID(uid) for uid in stats]
            user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
            for user in user_result.scalars().all():
                uid = str(user.id)
                if uid in stats:
                    stats[uid]["name"] = user.name
                    stats[uid]["username"] = user.username

        return {
            "contributors": list(stats.values()),
            "period_start": filters.get("period_start"),
            "period_end": filters.get("period_end"),
        }

    # ── Time to fix ───────────────────────────────────────────────────────────

    async def get_time_to_fix(
        self,
        db: AsyncSession,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        """Return per-developer average time-to-fix metrics.

        Parameters
        ----------
        db:
            Active async session.
        filters:
            Optional: ``project_id``, ``release_id``.

        Returns
        -------
        dict
            Matches ``TimeToFixResponse`` schema.
        """
        query = (
            select(
                Issue.assignee_id,
                func.avg(Issue.time_to_fix_h).label("avg_fix_h"),
                func.count(Issue.id).label("sample_size"),
            )
            .where(Issue.time_to_fix_h.isnot(None))
            .group_by(Issue.assignee_id)
        )
        if pid := filters.get("project_id"):
            query = query.where(Issue.project_id == uuid.UUID(str(pid)))

        rows = (await db.execute(query)).all()

        entries = []
        for row in rows:
            if row.assignee_id is None:
                continue
            user_res = await db.execute(select(User).where(User.id == row.assignee_id))
            user = user_res.scalar_one_or_none()
            entries.append(
                {
                    "user_id": str(row.assignee_id),
                    "name": user.name if user else "",
                    "avg_time_to_fix_h": round(float(row.avg_fix_h or 0), 2),
                    "sample_size": row.sample_size,
                }
            )

        return {"entries": sorted(entries, key=lambda e: e["avg_time_to_fix_h"])}

    # ── Regressions ───────────────────────────────────────────────────────────

    async def get_regressions(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Return issues sorted by regression frequency for a project.

        Parameters
        ----------
        db:
            Active async session.
        project_id:
            UUID of the project to analyse.

        Returns
        -------
        dict
            Matches ``RegressionsResponse`` schema.
        """
        result = await db.execute(
            select(Issue)
            .where(
                Issue.project_id == project_id,
                Issue.is_regression.is_(True),
            )
            .order_by(Issue.regression_count.desc())
        )
        issues = result.scalars().all()

        entries = [
            {
                "issue_id": str(iss.id),
                "issue_number": iss.issue_number,
                "title": iss.title,
                "regression_count": iss.regression_count,
                "last_regression_at": (
                    iss.updated_at.isoformat() if iss.updated_at else None
                ),
            }
            for iss in issues
        ]

        return {"project_id": str(project_id), "entries": entries}

    # ── Dashboard ─────────────────────────────────────────────────────────────

    async def get_dashboard(
        self,
        db: AsyncSession,
        project_ids: list[uuid.UUID],
    ) -> dict[str, Any]:
        """Return a high-level dashboard aggregation across multiple projects.

        Parameters
        ----------
        db:
            Active async session.
        project_ids:
            The projects to include (typically all projects the user has access to).

        Returns
        -------
        dict
            Matches ``DashboardResponse`` schema.
        """
        open_statuses = [
            IssueStatus.new.value,
            IssueStatus.triaged.value,
            IssueStatus.in_progress.value,
            IssueStatus.regression.value,
        ]

        all_issues_result = await db.execute(
            select(Issue).where(
                Issue.project_id.in_(project_ids),
                Issue.status.in_(open_statuses),
            )
        )
        issues = all_issues_result.scalars().all()

        project_stats: dict[str, Any] = {}
        for iss in issues:
            pid = str(iss.project_id)
            if pid not in project_stats:
                project_stats[pid] = {
                    "project_id": pid,
                    "open_issues": 0,
                    "blockers": 0,
                    "regressions": 0,
                }
            project_stats[pid]["open_issues"] += 1
            if iss.is_release_blocker:
                project_stats[pid]["blockers"] += 1
            if iss.is_regression:
                project_stats[pid]["regressions"] += 1

        return {
            "total_open_issues": len(issues),
            "total_blockers": sum(1 for i in issues if i.is_release_blocker),
            "total_regressions": sum(1 for i in issues if i.is_regression),
            "projects": list(project_stats.values()),
        }


# Module-level singleton
report_service = ReportService()
