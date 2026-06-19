"""ReportService — pre-computed analytics and dashboard aggregations.

All queries are async and cache their results in Redis to avoid re-computation
on every request.  Cache is invalidated by the ``invalidate_report_cache``
Celery task whenever issues or releases are mutated.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.db.models.issue import Issue, IssueSeverity, IssueStatus
from app.db.models.issue_cycle import IssueCycle
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.regression_history import RegressionHistory
from app.db.models.release import GoNogoStatus, Release, ReleaseStatus
from app.db.models.telegram_integration import TelegramIntegration
from app.db.models.user import User


class ReportService:
    """Analytics reports — each method may read from Redis cache first."""

    # ── Release report ────────────────────────────────────────────────────────

    async def get_release_report(
        self,
        db: AsyncSession,
        release_id: int,
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
        """Return per-user contribution metrics: table rows, segmented chart data, and label distribution."""
        SEVERITIES = ["blocker", "critical", "major", "minor", "enhancement"]
        FIXED_STATUSES = {IssueStatus.fixed.value, IssueStatus.verified.value, IssueStatus.closed.value}

        query = select(Issue)
        if pid := filters.get("project_id"):
            query = query.where(Issue.project_id == int(pid))
        if rid := filters.get("release_id"):
            query = query.where(Issue.release_id == int(rid))
        if date_from := filters.get("date_from"):
            try:
                query = query.where(Issue.created_at >= datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc))
            except ValueError:
                pass
        if date_to := filters.get("date_to"):
            try:
                query = query.where(Issue.created_at <= datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc))
            except ValueError:
                pass

        result = await db.execute(query)
        issues = result.scalars().all()

        # Load all active users
        user_result = await db.execute(select(User).where(User.is_active.is_(True)))
        users: dict[int, User] = {u.id: u for u in user_result.scalars().all()}

        def _empty(uid: int) -> dict[str, Any]:
            return {
                "user_id": uid,
                "reported": 0,
                "reported_breakdown": {s: 0 for s in SEVERITIES},
                "fixed": 0,
                "fixed_breakdown": {s: 0 for s in SEVERITIES},
                "assigned": 0,
                "ttf_list": [],
                "ttv_list": [],
                "labels": {},
            }

        stats: dict[int, dict[str, Any]] = {}

        for iss in issues:
            sev = iss.severity if isinstance(iss.severity, str) else (iss.severity.value if iss.severity else "minor")
            status = iss.status if isinstance(iss.status, str) else (iss.status.value if iss.status else "")

            if iss.reporter_id and iss.reporter_id in users:
                uid = iss.reporter_id
                stats.setdefault(uid, _empty(uid))
                stats[uid]["reported"] += 1
                stats[uid]["reported_breakdown"][sev] = stats[uid]["reported_breakdown"].get(sev, 0) + 1
                for label in (iss.labels or []):
                    stats[uid]["labels"][label] = stats[uid]["labels"].get(label, 0) + 1

            if iss.assignee_id and iss.assignee_id in users:
                uid = iss.assignee_id
                stats.setdefault(uid, _empty(uid))
                stats[uid]["assigned"] += 1
                if status in FIXED_STATUSES:
                    stats[uid]["fixed"] += 1
                    stats[uid]["fixed_breakdown"][sev] = stats[uid]["fixed_breakdown"].get(sev, 0) + 1
                    if iss.time_to_fix_h is not None:
                        stats[uid]["ttf_list"].append(iss.time_to_fix_h)
                    if iss.time_to_verify_h is not None:
                        stats[uid]["ttv_list"].append(iss.time_to_verify_h)

        def _avg(lst: list[float]) -> float | None:
            return round(sum(lst) / len(lst), 2) if lst else None

        contributors = []
        segmented = []
        labels_per_person = []

        for uid, s in sorted(stats.items(), key=lambda x: x[1]["reported"], reverse=True):
            user = users.get(uid)
            if not user:
                continue
            fix_rate = round(s["fixed"] / s["assigned"] * 100, 1) if s["assigned"] > 0 else None
            first_name = user.name.split()[0] if user.name else user.username

            contributors.append({
                "user_id": uid,
                "reported": s["reported"],
                "reported_breakdown": s["reported_breakdown"],
                "fixed": s["fixed"],
                "fix_rate": fix_rate,
                "avg_ttf": _avg(s["ttf_list"]),
                "avg_ttv": _avg(s["ttv_list"]),
            })

            segmented.append({
                "user_id": uid,
                "name": first_name,
                "reported": {**s["reported_breakdown"], "total": s["reported"]},
                "fixed": {**s["fixed_breakdown"], "total": s["fixed"]},
            })

            labels_per_person.append({
                "user_id": uid,
                "name": first_name,
                "labels": s["labels"],
            })

        return {
            "contributors": contributors,
            "segmented": segmented,
            "labels_per_person": labels_per_person,
        }

    # ── Contribution metrics time-series ──────────────────────────────────────

    async def get_contribution_metrics(
        self,
        db: AsyncSession,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        """Return weekly time-series of regression_rate, avg_time_to_triage, avg_time_to_verify, avg_time_to_fix.

        Optionally scoped to a single user (reporter metrics for that user's reported issues,
        fixer metrics for issues assigned to them).
        """
        user_id = filters.get("user_id")
        now = datetime.now(timezone.utc)

        date_to = now
        date_from = now - timedelta(days=30)

        if date_from_str := filters.get("date_from"):
            try:
                parsed = datetime.fromisoformat(date_from_str)
                date_from = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if date_to_str := filters.get("date_to"):
            try:
                parsed = datetime.fromisoformat(date_to_str)
                date_to = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        query = select(Issue).where(Issue.created_at >= date_from, Issue.created_at <= date_to)
        if pid := filters.get("project_id"):
            query = query.where(Issue.project_id == int(pid))
        if rid := filters.get("release_id"):
            query = query.where(Issue.release_id == int(rid))
        if user_id:
            query = query.where(or_(Issue.reporter_id == int(user_id), Issue.assignee_id == int(user_id)))

        result = await db.execute(query)
        issues = result.scalars().all()

        # Pick bucket size to produce ~5-7 points
        total_days = max(1, (date_to - date_from).days)
        if total_days <= 7:
            bucket_days = 1
        elif total_days <= 30:
            bucket_days = 7
        elif total_days <= 90:
            bucket_days = 14
        else:
            bucket_days = 30

        buckets: list[tuple[datetime, datetime]] = []
        cursor = date_from
        while cursor < date_to:
            buckets.append((cursor, cursor + timedelta(days=bucket_days)))
            cursor += timedelta(days=bucket_days)

        def _avg(lst: list[float]) -> float | None:
            return round(sum(lst) / len(lst), 2) if lst else None

        series = []
        for b_start, b_end in buckets:
            if user_id:
                uid = int(user_id)
                reported_iss = [i for i in issues if i.reporter_id == uid and b_start <= i.created_at < b_end]
                assigned_iss = [i for i in issues if i.assignee_id == uid and b_start <= i.created_at < b_end]
            else:
                reported_iss = [i for i in issues if b_start <= i.created_at < b_end]
                assigned_iss = reported_iss

            total = len(reported_iss)
            regression_rate = round(sum(1 for i in reported_iss if i.is_regression) / total * 100, 1) if total else 0

            series.append({
                "date": b_start.strftime("%Y-%m-%d"),
                "regression_rate": regression_rate,
                "avg_time_to_triage": _avg([i.time_to_triage_h for i in reported_iss if i.time_to_triage_h is not None]),
                "avg_time_to_verify": _avg([i.time_to_verify_h for i in assigned_iss if i.time_to_verify_h is not None]),
                "avg_time_to_fix": _avg([i.time_to_fix_h for i in assigned_iss if i.time_to_fix_h is not None]),
            })

        # Summary aggregates over the full period (used by summary cards)
        if user_id:
            uid = int(user_id)
            all_reported = [i for i in issues if i.reporter_id == uid]
            all_assigned = [i for i in issues if i.assignee_id == uid]
        else:
            all_reported = issues
            all_assigned = issues

        total_all = len(all_reported)
        summary = {
            "regression_rate": round(sum(1 for i in all_reported if i.is_regression) / total_all * 100, 1) if total_all else 0,
            "avg_time_to_triage": _avg([i.time_to_triage_h for i in all_reported if i.time_to_triage_h is not None]),
            "avg_time_to_verify": _avg([i.time_to_verify_h for i in all_assigned if i.time_to_verify_h is not None]),
            "avg_time_to_fix": _avg([i.time_to_fix_h for i in all_assigned if i.time_to_fix_h is not None]),
        }

        return {"series": series, "summary": summary}

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
            query = query.where(Issue.project_id == int(pid))

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
        project_id: int | str | None,
        n_releases: int = 6,
        date_from: str | None = None,
        date_to: str | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        """Regression analytics dashboard payload — all aggregation at DB level.

        Uses 9 targeted SQL queries (GROUP BY / FILTER / unnest) instead of
        loading issues into Python, so it stays fast at 100K+ issue scale.
        """
        EMPTY: dict[str, Any] = {
            "globalRegressionRate": 0,
            "totalRegressionTax": 0,
            "mostFragileComponent": "N/A",
            "chronicRegressionCount": 0,
            "regressionRateByRelease": [],
            "regressionTaxByRelease": [],
            "labelRegressionRates": [],
            "severityByRelease": [],
            "topDetectors": [],
            "reworkByDeveloper": [],
            "topRegressionIssues": [],
        }

        VERIFIED = (
            IssueStatus.verified.value,
            IssueStatus.closed.value,
            IssueStatus.fixed.value,
        )

        def _val(x: Any) -> Any:
            return x.value if hasattr(x, "value") else x

        # ── Q1: N most-recent releases ─────────────────────────────────────────
        releases_q = (
            select(Release.id, Release.version)
            .order_by(Release.created_at.desc())
            .limit(n_releases)
        )
        if project_id is not None:
            try:
                releases_q = releases_q.where(Release.project_id == int(project_id))
            except (ValueError, TypeError):
                pass
        if date_from is not None:
            try:
                dt_from = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
                releases_q = releases_q.where(Release.created_at >= dt_from)
            except ValueError:
                pass
        if date_to is not None:
            try:
                dt_to = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
                releases_q = releases_q.where(Release.created_at <= dt_to)
            except ValueError:
                pass

        releases = list(reversed((await db.execute(releases_q)).all()))
        if not releases:
            return EMPTY
        release_ids = [r.id for r in releases]

        # ── Q2: Per-release aggregations (one round-trip) ──────────────────────
        # All KPI inputs + all chart series inputs come from this single query.
        # PostgreSQL FILTER (WHERE …) keeps the GROUP BY to one pass over issues.
        # Label is added to the JOIN condition (not WHERE) so that releases with
        # no matching-label issues still appear in the chart as zero-count rows.
        issue_join_cond = (
            and_(Issue.release_id == Release.id, Issue.labels.contains([label]))
            if label
            else Issue.release_id == Release.id
        )
        per_rel_q = (
            select(
                Release.id.label("release_id"),
                Release.version,
                func.count(Issue.id).label("total_count"),
                func.count(Issue.id).filter(
                    Issue.status.in_(VERIFIED)
                ).label("verified_count"),
                func.count(Issue.id).filter(
                    Issue.is_regression.is_(True)
                ).label("reg_count"),
                func.count(Issue.id).filter(
                    Issue.is_regression.is_(True),
                    Issue.severity == IssueSeverity.blocker.value,
                ).label("sev_blocker"),
                func.count(Issue.id).filter(
                    Issue.is_regression.is_(True),
                    Issue.severity == IssueSeverity.critical.value,
                ).label("sev_critical"),
                func.count(Issue.id).filter(
                    Issue.is_regression.is_(True),
                    Issue.severity == IssueSeverity.major.value,
                ).label("sev_major"),
                func.count(Issue.id).filter(
                    Issue.is_regression.is_(True),
                    Issue.severity == IssueSeverity.minor.value,
                ).label("sev_minor"),
                func.count(Issue.id).filter(Issue.regression_count >= 3).label("chronic"),
            )
            .select_from(Release)
            .outerjoin(Issue, issue_join_cond)
            .where(Release.id.in_(release_ids))
            .group_by(Release.id, Release.version)
        )
        per_rel_rows = {r.release_id: r for r in (await db.execute(per_rel_q)).all()}

        # ── Q2b: Cycle-based tax breakdown per release ─────────────────────────
        # Cycle 1 = initial fix effort; cycle >1 = rework after regression.
        # Uses IssueCycle.time_to_fix_h so every pass is counted correctly,
        # including the first-time fix on issues that later regressed (which
        # Issue.time_to_fix_h would overwrite with the most recent cycle only).
        cycle_tax_q = (
            select(
                Issue.release_id,
                func.coalesce(
                    func.sum(IssueCycle.time_to_fix_h).filter(IssueCycle.cycle_number == 1),
                    0.0,
                ).label("first_time_fix_h"),
                func.coalesce(
                    func.sum(IssueCycle.time_to_fix_h).filter(IssueCycle.cycle_number > 1),
                    0.0,
                ).label("rework_h"),
            )
            .join(Issue, Issue.id == IssueCycle.issue_id)
            .where(
                Issue.release_id.in_(release_ids),
                *([Issue.labels.contains([label])] if label else []),
            )
            .group_by(Issue.release_id)
        )
        tax_by_release: dict[int, tuple[float, float]] = {
            r.release_id: (float(r.first_time_fix_h), float(r.rework_h))
            for r in (await db.execute(cycle_tax_q)).all()
        }

        # Global KPIs derived from the per-release aggregates (no extra round-trip).
        all_rows = list(per_rel_rows.values())
        total_verified = sum(r.verified_count for r in all_rows)
        total_regressions = sum(r.reg_count for r in all_rows)
        global_rate = (
            round(total_regressions / total_verified * 100, 1) if total_verified else 0
        )
        total_tax = round(sum(rw for _, rw in tax_by_release.values()), 1)
        chronic_count = sum(r.chronic for r in all_rows)

        # ── Q3: Top-5 most-regressed labels ────────────────────────────────────
        top_labels_q = (
            select(
                func.unnest(Issue.labels).label("label"),
                func.count().label("cnt"),
            )
            .where(
                Issue.release_id.in_(release_ids),
                Issue.is_regression.is_(True),
                *([Issue.labels.contains([label])] if label else []),
            )
            .group_by(func.unnest(Issue.labels))
            .order_by(func.count().desc())
            .limit(5)
        )
        top_label_rows = (await db.execute(top_labels_q)).all()
        top_labels = [r.label for r in top_label_rows]
        most_fragile = top_labels[0] if top_labels else "N/A"

        # ── Q4: Regression count per label per release (trend chart) ───────────
        label_per_rel_q = (
            select(
                Issue.release_id,
                func.unnest(Issue.labels).label("label"),
                func.count().label("cnt"),
            )
            .where(
                Issue.release_id.in_(release_ids),
                Issue.is_regression.is_(True),
                *([Issue.labels.contains([label])] if label else []),
            )
            .group_by(Issue.release_id, func.unnest(Issue.labels))
        )
        label_by_release: dict[int, dict[str, int]] = defaultdict(dict)
        for row in (await db.execute(label_per_rel_q)).all():
            label_by_release[row.release_id][row.label] = row.cnt

        # ── Build chart series from Q2 + Q4 results ────────────────────────────
        rate_series: list[dict] = []
        tax_series: list[dict] = []
        sev_series: list[dict] = []
        label_series: list[dict] = []

        for rel in releases:
            row = per_rel_rows.get(rel.id)
            ver = rel.version
            empty_labels = {lbl: 0.0 for lbl in top_labels}

            if not row or row.total_count == 0:
                rate_series.append({"release": ver, "rate": 0})
                tax_series.append({"release": ver, "firstTimeFixHours": 0.0, "regressionReworkHours": 0.0})
                sev_series.append({"release": ver, "blocker": 0, "critical": 0, "major": 0, "minor": 0})
                label_series.append({"release": ver, **empty_labels})
                continue

            rate_series.append({
                "release": ver,
                "rate": round(row.reg_count / row.verified_count * 100, 1) if row.verified_count else 0,
            })
            first_fix_h, rework_h = tax_by_release.get(rel.id, (0.0, 0.0))
            tax_series.append({
                "release": ver,
                "firstTimeFixHours": round(first_fix_h, 1),
                "regressionReworkHours": round(rework_h, 1),
            })
            sev_series.append({
                "release": ver,
                "blocker": row.sev_blocker,
                "critical": row.sev_critical,
                "major": row.sev_major,
                "minor": row.sev_minor,
            })
            lbl_counts = label_by_release.get(rel.id, {})
            label_series.append({
                "release": ver,
                **{
                    lbl: round(lbl_counts.get(lbl, 0) / row.total_count * 100, 1)
                    for lbl in top_labels
                },
            })

        # ── Q5: Top regression detectors ───────────────────────────────────────
        det_q = (
            select(
                RegressionHistory.detected_by_id,
                func.count(RegressionHistory.id).label("detected"),
                User.name,
                User.username,
                User.role,
                User.avatar_color,
                User.avatar_url,
                User.title,
                User.bio,
                TelegramIntegration.telegram_user_id.label("tg_user_id"),
                TelegramIntegration.telegram_username.label("tg_username"),
            )
            .join(User, User.id == RegressionHistory.detected_by_id)
            .join(Issue, Issue.id == RegressionHistory.issue_id)
            .outerjoin(TelegramIntegration, TelegramIntegration.user_id == User.id)
            .where(
                RegressionHistory.release_id.in_(release_ids),
                *([Issue.labels.contains([label])] if label else []),
            )
            .group_by(
                RegressionHistory.detected_by_id,
                User.name,
                User.username,
                User.role,
                User.avatar_color,
                User.avatar_url,
                User.title,
                User.bio,
                TelegramIntegration.telegram_user_id,
                TelegramIntegration.telegram_username,
            )
            .order_by(func.count(RegressionHistory.id).desc())
            .limit(5)
        )
        top_detectors = [
            {
                "user": {
                    "id": r.detected_by_id,
                    "name": r.name,
                    "username": r.username,
                    "role": _val(r.role),
                    "avatar_color": r.avatar_color,
                    "avatar_url": r.avatar_url,
                    "title": r.title,
                    "bio": r.bio,
                    "tgConnected": r.tg_user_id is not None,
                    "tgHandle": r.tg_username,
                },
                "detected": r.detected,
            }
            for r in (await db.execute(det_q)).all()
        ]

        # ── Q6: Regression count per developer (their fixes that later broke) ──
        reg_count_q = (
            select(
                RegressionHistory.previous_fix_by_id.label("user_id"),
                func.count(RegressionHistory.id).label("regression_count"),
            )
            .join(Issue, Issue.id == RegressionHistory.issue_id)
            .where(
                RegressionHistory.release_id.in_(release_ids),
                RegressionHistory.previous_fix_by_id.isnot(None),
                *([Issue.labels.contains([label])] if label else []),
            )
            .group_by(RegressionHistory.previous_fix_by_id)
        )
        reg_count_map = {
            r.user_id: r.regression_count
            for r in (await db.execute(reg_count_q)).all()
        }

        # ── Q7: Rework hours per developer — uses cycle-level assignee so hours
        #        are attributed to whoever actually did each re-fix, not the
        #        current issue assignee (which may differ across cycles).
        rework_hrs_q = (
            select(
                IssueCycle.assignee_id,
                func.coalesce(
                    func.sum(IssueCycle.time_to_fix_h),
                    0.0,
                ).label("rework_hours"),
            )
            .join(Issue, Issue.id == IssueCycle.issue_id)
            .where(
                Issue.release_id.in_(release_ids),
                IssueCycle.cycle_number > 1,
                IssueCycle.assignee_id.isnot(None),
                *([Issue.labels.contains([label])] if label else []),
            )
            .group_by(IssueCycle.assignee_id)
        )
        rework_hrs_map = {
            r.assignee_id: float(r.rework_hours)
            for r in (await db.execute(rework_hrs_q)).all()
        }

        # ── Q8: User detail rows for rework developers ─────────────────────────
        dev_ids = set(reg_count_map) | {uid for uid, h in rework_hrs_map.items() if h > 0}
        rework_by_dev: list[dict] = []
        if dev_ids:
            dev_q = (
                select(
                    User.id,
                    User.name,
                    User.username,
                    User.role,
                    User.avatar_color,
                    User.avatar_url,
                    User.title,
                    User.bio,
                    TelegramIntegration.telegram_user_id.label("tg_user_id"),
                    TelegramIntegration.telegram_username.label("tg_username"),
                )
                .outerjoin(TelegramIntegration, TelegramIntegration.user_id == User.id)
                .where(User.id.in_(dev_ids))
            )
            rework_by_dev = sorted(
                [
                    {
                        "user": {
                            "id": u.id,
                            "name": u.name,
                            "username": u.username,
                            "role": _val(u.role),
                            "avatar_color": u.avatar_color,
                            "avatar_url": u.avatar_url,
                            "title": u.title,
                            "bio": u.bio,
                            "tgConnected": u.tg_user_id is not None,
                            "tgHandle": u.tg_username,
                        },
                        "reworkHours": round(rework_hrs_map.get(u.id, 0.0), 1),
                        "regressionCount": reg_count_map.get(u.id, 0),
                    }
                    for u in (await db.execute(dev_q)).all()
                ],
                key=lambda x: x["reworkHours"],
                reverse=True,
            )[:5]

        # ── Q9: Top-10 regression issues with assignee join ────────────────────
        AssigneeUser = aliased(User)
        top_issues_q = (
            select(
                Issue.issue_number,
                Issue.title,
                Issue.severity,
                Issue.status,
                Issue.labels,
                Issue.regression_count,
                Issue.created_at,
                Issue.assignee_id,
                AssigneeUser.name.label("assignee_name"),
                AssigneeUser.username.label("assignee_username"),
                AssigneeUser.role.label("assignee_role"),
                AssigneeUser.avatar_color.label("assignee_avatar_color"),
                AssigneeUser.avatar_url.label("assignee_avatar_url"),
            )
            .outerjoin(AssigneeUser, AssigneeUser.id == Issue.assignee_id)
            .where(
                Issue.release_id.in_(release_ids),
                Issue.regression_count > 0,
                *([Issue.labels.contains([label])] if label else []),
            )
            .order_by(Issue.regression_count.desc())
            .limit(10)
        )
        top_regression_issues = [
            {
                "id": r.issue_number,
                "title": r.title,
                "severity": _val(r.severity),
                "status": _val(r.status),
                "labels": r.labels or [],
                "regressions": r.regression_count or 0,
                "assignee": {
                    "id": r.assignee_id,
                    "name": r.assignee_name,
                    "username": r.assignee_username,
                    "role": _val(r.assignee_role),
                    "avatar_color": r.assignee_avatar_color,
                    "avatar_url": r.assignee_avatar_url,
                } if r.assignee_id else None,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
            for r in (await db.execute(top_issues_q)).all()
        ]

        return {
            "globalRegressionRate": global_rate,
            "totalRegressionTax": total_tax,
            "mostFragileComponent": most_fragile,
            "chronicRegressionCount": chronic_count,
            "regressionRateByRelease": rate_series,
            "regressionTaxByRelease": tax_series,
            "labelRegressionRates": label_series,
            "severityByRelease": sev_series,
            "topDetectors": top_detectors,
            "reworkByDeveloper": rework_by_dev,
            "topRegressionIssues": top_regression_issues,
        }

    # ── Dashboard ─────────────────────────────────────────────────────────────

    async def get_dashboard(
        self,
        db: AsyncSession,
        current_user: User,
    ) -> dict[str, Any]:
        """Return full dashboard payload matching the frontend DashboardPage shape."""
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)
        thirty_days_ago = now - timedelta(days=30)
        sixty_days_ago = now - timedelta(days=60)
        triage_cutoff = now - timedelta(hours=24)
        verify_cutoff = now - timedelta(hours=48)

        OPEN = [IssueStatus.new.value, IssueStatus.triaged.value, IssueStatus.in_progress.value, IssueStatus.regression.value]
        DONE = [IssueStatus.fixed.value, IssueStatus.verified.value, IssueStatus.closed.value]

        def _val(x: Any) -> Any:
            return x.value if hasattr(x, "value") else x

        def _user_obj(u: User | None) -> dict | None:
            if not u:
                return None
            return {
                "id": u.id,
                "name": u.name,
                "username": u.username,
                "role": _val(u.role),
                "avatar_color": u.avatar_color,
                "avatar_url": u.avatar_url,
            }

        # ── 1. My action items ────────────────────────────────────────────────
        my_issues = (await db.execute(
            select(Issue).where(Issue.assignee_id == current_user.id, Issue.status.in_(OPEN))
        )).scalars().all()

        # ── 2. Active releases with computed health ───────────────────────────
        active_releases = (await db.execute(
            select(Release)
            .where(Release.status.in_([ReleaseStatus.active.value, ReleaseStatus.blocked.value]))
            .options(selectinload(Release.issues), selectinload(Release.project))
            .order_by(Release.created_at.desc())
            .limit(6)
        )).scalars().all()

        on_track = at_risk = off_track = 0
        releases_data: list[dict] = []
        for rel in active_releases:
            total = len(rel.issues)
            fixed_cnt = sum(1 for i in rel.issues if _val(i.status) in DONE)
            open_cnt = total - fixed_cnt
            blockers = sum(1 for i in rel.issues if i.is_release_blocker and _val(i.status) not in DONE)
            progress = round(fixed_cnt / total * 100) if total > 0 else 0
            go_nogo = _val(rel.go_nogo_status)

            if go_nogo == "blocked" or blockers >= 2:
                health = "red"
                off_track += 1
            elif blockers == 1 or progress < 60:
                health = "amber"
                at_risk += 1
            else:
                health = "green"
                on_track += 1

            releases_data.append({
                "id": rel.id,
                "version": rel.version,
                "projectName": rel.project.name if rel.project else "",
                "health": health,
                "goNoGoStatus": go_nogo,
                "progress": progress,
                "openIssues": open_cnt,
                "blockers": blockers,
                "fixedIssues": fixed_cnt,
                "totalIssues": total,
                "targetDate": rel.target_date.isoformat() if rel.target_date else None,
            })

        # ── 3. Team velocity ──────────────────────────────────────────────────
        this_week = (await db.execute(select(func.count(Issue.id)).where(Issue.fixed_at >= week_ago))).scalar() or 0
        last_week_cnt = (await db.execute(select(func.count(Issue.id)).where(Issue.fixed_at >= two_weeks_ago, Issue.fixed_at < week_ago))).scalar() or 0

        if last_week_cnt > 0:
            delta_pct = round((this_week - last_week_cnt) / last_week_cnt * 100)
            vel_trend = "up" if delta_pct > 0 else ("down" if delta_pct < 0 else "neutral")
            vel_delta = f"+{delta_pct}%" if delta_pct > 0 else f"{delta_pct}%"
        else:
            vel_trend = "neutral"
            vel_delta = "—"

        # ── 4. Quality score (fix rate over last 30 days vs prior 30 days) ───
        async def _count(q: Any) -> int:
            return (await db.execute(q)).scalar() or 0

        recent_total = await _count(select(func.count(Issue.id)).where(Issue.created_at >= thirty_days_ago))
        recent_done = await _count(select(func.count(Issue.id)).where(Issue.created_at >= thirty_days_ago, Issue.status.in_(DONE)))
        prev_total = await _count(select(func.count(Issue.id)).where(Issue.created_at >= sixty_days_ago, Issue.created_at < thirty_days_ago))
        prev_done = await _count(select(func.count(Issue.id)).where(Issue.created_at >= sixty_days_ago, Issue.created_at < thirty_days_ago, Issue.status.in_(DONE)))

        quality = round(recent_done / recent_total * 100) if recent_total > 0 else 0
        prev_quality = round(prev_done / prev_total * 100) if prev_total > 0 else 0
        q_delta = quality - prev_quality
        q_trend = "up" if q_delta > 0 else ("down" if q_delta < 0 else "neutral")
        q_delta_str = (f"+{q_delta}%" if q_delta > 0 else f"{q_delta}%") if prev_total > 0 else "—"

        # ── 5. Stale items ────────────────────────────────────────────────────
        # Use filed_at (set by services/seed) rather than created_at (DB default = now).
        # Use coalesce(fixed_at, updated_at) for verification since seed/legacy rows may have NULL fixed_at.
        filed_or_created = func.coalesce(Issue.filed_at, Issue.created_at)
        fixed_or_updated = func.coalesce(Issue.fixed_at, Issue.updated_at)

        awaiting_triage = (await db.execute(
            select(Issue).where(Issue.status == IssueStatus.new.value, filed_or_created <= triage_cutoff)
            .order_by(filed_or_created.asc()).limit(5)
        )).scalars().all()

        awaiting_verify = (await db.execute(
            select(Issue).where(Issue.status == IssueStatus.fixed.value, fixed_or_updated <= verify_cutoff)
            .order_by(fixed_or_updated.asc()).limit(5)
        )).scalars().all()

        low_fruit = (await db.execute(
            select(Issue).where(
                Issue.status.in_([IssueStatus.new.value, IssueStatus.triaged.value]),
                Issue.severity.in_([IssueSeverity.minor.value, IssueSeverity.enhancement.value]),
                Issue.assignee_id.is_(None),
            ).order_by(filed_or_created.asc()).limit(5)
        )).scalars().all()

        fixer_ids = [i.assignee_id for i in awaiting_verify if i.assignee_id]
        fixers: dict[int, User] = {}
        if fixer_ids:
            fixers = {u.id: u for u in (await db.execute(select(User).where(User.id.in_(fixer_ids)))).scalars().all()}

        stale_items: list[dict] = []
        for iss in awaiting_triage:
            ref = iss.filed_at or iss.created_at
            h = round((now - ref).total_seconds() / 3600) if ref else 0
            stale_items.append({"id": iss.issue_number, "title": iss.title, "severity": _val(iss.severity), "status": _val(iss.status), "category": "awaiting_triage", "waitingHours": h})
        for iss in awaiting_verify:
            ref = iss.fixed_at or iss.updated_at
            h = round((now - ref).total_seconds() / 3600) if ref else 0
            stale_items.append({"id": iss.issue_number, "title": iss.title, "severity": _val(iss.severity), "status": _val(iss.status), "category": "awaiting_verification", "waitingHours": h, "fixer": _user_obj(fixers.get(iss.assignee_id))})
        for iss in low_fruit:
            ref = iss.filed_at or iss.created_at
            h = round((now - ref).total_seconds() / 3600) if ref else 0
            stale_items.append({"id": iss.issue_number, "title": iss.title, "severity": _val(iss.severity), "status": _val(iss.status), "category": "low_hanging_fruit", "waitingHours": h, "estimatedTime": "1-2h"})

        # ── 6. Activity stream ────────────────────────────────────────────────
        ActorUser = aliased(User)
        ACTIVITY_TYPES = [
            TimelineEventType.filed.value, TimelineEventType.fixed.value,
            TimelineEventType.verified.value, TimelineEventType.assigned.value,
            TimelineEventType.comment.value, TimelineEventType.regression.value,
            TimelineEventType.status_changed.value,
        ]
        activity_rows = (await db.execute(
            select(
                IssueTimeline.id, IssueTimeline.event_type, IssueTimeline.meta, IssueTimeline.created_at,
                Issue.issue_number, Issue.title.label("issue_title"),
                Release.version.label("release_version"),
                ActorUser.id.label("actor_id"), ActorUser.name.label("actor_name"),
                ActorUser.username.label("actor_username"), ActorUser.role.label("actor_role"),
                ActorUser.avatar_color.label("actor_avatar_color"), ActorUser.avatar_url.label("actor_avatar_url"),
            )
            .join(Issue, Issue.id == IssueTimeline.issue_id)
            .outerjoin(Release, Release.id == Issue.release_id)
            .outerjoin(ActorUser, ActorUser.id == IssueTimeline.actor_id)
            .where(IssueTimeline.event_type.in_(ACTIVITY_TYPES))
            .order_by(IssueTimeline.created_at.desc())
            .limit(30)
        )).all()

        # Batch-load assignee users for 'assigned' events
        assignee_ids = {
            int(r.meta["assignee_id"])
            for r in activity_rows
            if _val(r.event_type) == "assigned" and (r.meta or {}).get("assignee_id")
        }
        to_actors: dict[int, dict] = {}
        if assignee_ids:
            to_actors = {u.id: _user_obj(u) for u in (await db.execute(select(User).where(User.id.in_(assignee_ids)))).scalars().all()}

        activity_stream: list[dict] = []
        for row in activity_rows:
            et = _val(row.event_type)
            meta = row.meta or {}

            if et == "status_changed":
                if meta.get("to") == "triaged":
                    activity_type = "triaged"
                else:
                    continue
            elif et == "comment":
                activity_type = "commented"
            else:
                activity_type = et

            actor = {"id": row.actor_id, "name": row.actor_name, "username": row.actor_username, "role": _val(row.actor_role), "avatar_color": row.actor_avatar_color, "avatar_url": row.actor_avatar_url} if row.actor_id else None
            item: dict[str, Any] = {
                "id": row.id,
                "type": activity_type,
                "actor": actor,
                "issueId": row.issue_number,
                "issueTitle": row.issue_title,
                "releaseVersion": row.release_version,
                "timestamp": row.created_at.isoformat() if row.created_at else None,
            }
            if et == "assigned" and meta.get("assignee_id"):
                try:
                    item["toActor"] = to_actors.get(int(meta["assignee_id"]))
                except (ValueError, TypeError):
                    pass

            activity_stream.append(item)
            if len(activity_stream) >= 10:
                break

        return {
            "heroMetrics": {
                "myActionItems": {
                    "count": len(my_issues),
                    "urgent": sum(1 for i in my_issues if _val(i.severity) in ("blocker", "critical")),
                    "breakdown": {
                        "blockers": sum(1 for i in my_issues if _val(i.severity) == "blocker"),
                        "critical": sum(1 for i in my_issues if _val(i.severity) == "critical"),
                        "major": sum(1 for i in my_issues if _val(i.severity) == "major"),
                    },
                },
                "activeReleases": {
                    "count": len(active_releases),
                    "onTrack": on_track,
                    "atRisk": at_risk,
                    "offTrack": off_track,
                },
                "teamVelocity": {
                    "thisWeek": this_week,
                    "lastWeek": last_week_cnt,
                    "delta": vel_delta,
                    "trend": vel_trend,
                },
                "qualityScore": {
                    "value": quality,
                    "max": 100,
                    "delta": q_delta_str,
                    "trend": q_trend,
                },
            },
            "releases": releases_data,
            "staleItems": stale_items,
            "activityStream": activity_stream,
        }


# Module-level singleton
report_service = ReportService()
