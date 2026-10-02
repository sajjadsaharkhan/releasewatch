"""Duplicate hints (slice 14, engine PRD A.4/A.5, FR-S12–S15, BR-S09–S12).

A hint is a stored possible duplicate of a **New bug**: what
``compute_duplicate_hints`` found (stage-1 candidates → Jev's same/related/
unrelated judgment → the top ``same`` verdicts at ``T_SAME``). The job runs
when a bug enters New, when its title or description changes while New, and
when it moves project during triage — only while Jev is enabled. Hints are
replaced wholesale on each computation and never exceed
``DUPLICATE_HINT_LIMIT``; a dismissed pair is never stored again.

Two rules keep the hint honest:

- ``merge_effect`` is computed with ``cycle_service.return_reason_for_done``
  — the function ``MergeService`` reaches through ``IssueService.reject_with``
  when a merge actually runs — so the hint's sentence and the merge's effect
  can never disagree (BR-49).
- With Jev off (or failing mid-run) stored hints stay: hidden, not deleted
  (BR-S03), and switching Jev back on shows them again without recomputation.

The API layer (``GET/POST /issues/{id}/duplicate-hints``) hides hints unless
the item is New and Jev is enabled; Support never reaches either endpoint
(FR-S13, Policy ``view_duplicate_hints``).
"""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue import Issue, IssueStatus, IssueType, issue_key
from app.db.models.release import Release
from app.db.models.search import DuplicateDismissal, DuplicateHint
from app.search import jev_settings
from app.search.constants import DUPLICATE_HINT_LIMIT, SIMILAR_CANDIDATES, T_SAME
from app.search.documents import body_text
from app.search.jev import JevItem
from app.search.normalize import normalize, strip_markdown
from app.search.retrieval import Filters, same_problem_candidates

#: What "Merge into this" will do to the candidate (BR-49).
MERGE_EFFECTS = ("unchanged", "stays_cancelled", "returns_release_qa", "returns_production")


def _value(x):
    return getattr(x, "value", x)


def merge_effect_of(status: str, container: Release | None) -> str:
    """The hint's merge effect, from the same reason function the merge uses
    (``return_reason_for_done`` via ``IssueService.reject_with``): Done returns
    — release QA in an unshipped Release, production otherwise, a None
    container included — Cancelled stays cancelled, anything else is untouched."""
    from app.db.models.issue_cycle import CycleStartReason
    from app.services.cycle_service import return_reason_for_done

    if status == IssueStatus.done.value:
        reason = (
            return_reason_for_done(container) if container is not None
            else CycleStartReason.production
        )
        return (
            "returns_release_qa"
            if reason == CycleStartReason.release_qa
            else "returns_production"
        )
    if status == IssueStatus.cancelled.value:
        return "stays_cancelled"
    return "unchanged"


def is_hintable(issue: Issue) -> bool:
    """Hints exist only for New bugs (FR-S15, BR-S09: tech items, bugs only —
    tasks never enter triage)."""
    return (
        _value(issue.type) == IssueType.bug.value
        and _value(issue.status) == IssueStatus.new.value
    )


def candidate_filters(issue: Issue) -> Filters:
    """The triage candidate rule (BR-S09, PRD BR-20): same project, bugs and
    tasks, not Cancelled, never the item itself."""
    return Filters(
        project_id=issue.project_id,
        types=[IssueType.bug.value, IssueType.task.value],
        exclude_statuses=[IssueStatus.cancelled.value],
        exclude_issue_id=issue.id,
    )


async def compute_in(db: AsyncSession, issue_id: int) -> dict:
    """Recompute one item's hints inside ``db`` (not committed). Replaces the
    stored set wholesale; a Jev-off or failing run leaves what is stored."""
    issue = await db.get(Issue, issue_id)
    if issue is None or issue.deleted_at is not None or not is_hintable(issue):
        await db.execute(delete(DuplicateHint).where(DuplicateHint.issue_id == issue_id))
        return {"issue_id": issue_id, "hints": 0, "skipped": "not_hintable"}

    jev = await jev_settings.client(db)
    if jev is None:
        # Jev off: nothing is written and nothing is lost (BR-S03).
        return {"issue_id": issue_id, "hints": -1, "skipped": "jev_off"}

    dismissed = set(
        (await db.execute(
            select(DuplicateDismissal.candidate_id).where(DuplicateDismissal.issue_id == issue_id)
        )).scalars()
    )
    hits = [
        h for h in await same_problem_candidates(
            db, None, body_text(issue), filters=candidate_filters(issue),
            k=SIMILAR_CANDIDATES,
        )
        if h.issue_id not in dismissed
    ]
    rows = (await db.execute(
        select(Issue).where(Issue.id.in_([h.issue_id for h in hits]))
    )).scalars().all()
    by_id = {r.id: r for r in rows}
    # Cancelled between index refreshes is still excluded — BR-S11/AC-S14.
    items = [
        JevItem(
            id=r.id, title=r.title,
            description=normalize(strip_markdown(r.description)),
            type=_value(r.type),
        )
        for r in (by_id.get(h.issue_id) for h in hits)
        if r is not None and _value(r.status) != IssueStatus.cancelled.value
    ]
    outcome, verdicts = await jev.judge_same(
        issue.title, normalize(strip_markdown(issue.description)), items, background=True,
    )
    if not outcome.ok:
        return {"issue_id": issue_id, "hints": -1, "skipped": outcome.reason}

    kept = sorted(
        (
            (item_id, verdict[1])
            for item_id, verdict in verdicts.items()
            if verdict[0] == "same" and verdict[1] >= T_SAME
        ),
        key=lambda pair: -pair[1],
    )[:DUPLICATE_HINT_LIMIT]

    await db.execute(delete(DuplicateHint).where(DuplicateHint.issue_id == issue_id))
    for candidate_id, confidence in kept:
        db.add(DuplicateHint(
            issue_id=issue_id,
            candidate_id=candidate_id,
            confidence=confidence,
            jev_model=outcome.model or jev.model,
        ))
    await db.flush()
    return {"issue_id": issue_id, "hints": len(kept), "jev_model": outcome.model}


async def hydrate(db: AsyncSession, issue_id: int) -> list[dict]:
    """The stored hints of one item, best first, with the candidate summary and
    merge effect the triage pane and the item page render. The caller decides
    visibility and the New/Jev gates."""
    hints = (await db.execute(
        select(DuplicateHint, Issue, Release)
        .join(Issue, Issue.id == DuplicateHint.candidate_id)
        .outerjoin(Release, Release.id == Issue.release_id)
        .where(DuplicateHint.issue_id == issue_id, Issue.deleted_at.is_(None))
        .order_by(DuplicateHint.confidence.desc(), DuplicateHint.candidate_id)
    )).all()
    out = []
    for hint, candidate, container in hints:
        status = _value(candidate.status)
        out.append({
            "candidate_id": candidate.id,
            "confidence": round(hint.confidence, 4),
            "merge_effect": merge_effect_of(status, container),
            "candidate": {
                "id": candidate.id,
                "key": issue_key(_value(candidate.type), candidate.issue_number),
                "type": _value(candidate.type),
                "title": candidate.title,
                "status": status,
                "issue_number": candidate.issue_number,
                "container": (
                    {
                        "id": container.id,
                        "name": container.version,
                        "is_stream": container.is_stream,
                    }
                    if container is not None else None
                ),
            },
        })
    return out


async def dismiss(db: AsyncSession, issue_id: int, candidate_id: int, actor_id: int) -> None:
    """Record "Not a duplicate" forever and drop the stored hint (BR-S12, AC-S12).

    The row also keeps what the triager saw — Jev's confidence and model, and
    both items' title, description and the candidate's status — so the
    dismissals can later tune the threshold or train the similarity model.
    Idempotent: dismissing a pair again refreshes who and when, and keeps the
    first snapshot."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    hint = (await db.execute(
        select(DuplicateHint).where(
            DuplicateHint.issue_id == issue_id, DuplicateHint.candidate_id == candidate_id,
        )
    )).scalar_one_or_none()
    issue = await db.get(Issue, issue_id)
    candidate = await db.get(Issue, candidate_id)

    stamp = {"dismissed_by_id": actor_id, "dismissed_at": func.now()}
    snapshot = {
        "confidence": hint.confidence if hint else None,
        "jev_model": hint.jev_model if hint else None,
        "hint_computed_at": hint.computed_at if hint else None,
        "issue_title": issue.title if issue else None,
        "issue_description": issue.description if issue else None,
        "candidate_title": candidate.title if candidate else None,
        "candidate_description": candidate.description if candidate else None,
        "candidate_status": _value(candidate.status) if candidate else None,
    }
    stmt = pg_insert(DuplicateDismissal).values(
        issue_id=issue_id, candidate_id=candidate_id, **stamp, **snapshot
    )
    await db.execute(stmt.on_conflict_do_update(
        index_elements=[DuplicateDismissal.issue_id, DuplicateDismissal.candidate_id],
        set_=stamp,
    ))
    await db.execute(
        delete(DuplicateHint).where(
            DuplicateHint.issue_id == issue_id, DuplicateHint.candidate_id == candidate_id,
        )
    )
    await db.flush()
