"""Similar-item suggestions for the create forms (slice 14, FR-S08–S10, A.9).

``suggest`` is what POST /search/similar serves: stage-1 candidates
(``retrieval.same_problem_candidates``) with the consumer's rule, Jev's
same/related judgment, and the context's thresholds — at most ``SIMILAR_LIMIT``
rows, ``same`` first. Support sees only ``same`` ≥ ``T_SAME`` (a panel worth
reading, FR-S09); the tech form also shows ``related`` ≥ ``T_RELATED`` for
information (FR-S08).

``None`` means "behave as if Jev were off" — Jev disabled, or the call failed
(BR-S02): the route answers 204 and the UI shows no panel, never an error and
never a stale one. The support draft is composed with ``compose_report`` (05),
so the query is the body the report would have.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.issue import Issue, IssueSource, IssueStatus, issue_key
from app.db.models.support_template import SupportTemplate
from app.db.models.user import User
from app.schemas.search import SimilarItemsRequest
from app.search import jev_settings
from app.search.constants import SIMILAR_LIMIT, T_RELATED, T_SAME
from app.search.jev import JevItem
from app.search.normalize import normalize, strip_markdown
from app.search.retrieval import Filters, same_problem_candidates
from app.support_report import compose_report


def _value(x):
    return getattr(x, "value", x)


async def _support_description(db: AsyncSession, body: SimilarItemsRequest) -> str:
    """The support draft's description: the report as ``compose_report`` (05)
    will store it. A template that is gone or not yet chosen falls back to the
    free text — the panel is advisory, the form's own validation decides."""
    if body.template_id is None:
        return body.description or ""
    from app.services.support_service import template_spec

    template = (await db.execute(
        select(SupportTemplate)
        .where(SupportTemplate.id == body.template_id)
        .options(selectinload(SupportTemplate.fields))
    )).scalar_one_or_none()
    if template is None:
        return body.description or ""
    return compose_report(template_spec(template), body.values, body.description).markdown


async def suggest(db: AsyncSession, actor: User, body: SimilarItemsRequest) -> list[dict] | None:
    jev = await jev_settings.client(db)
    if jev is None:
        return None

    if body.context == "support":
        description = await _support_description(db, body)
        filters = Filters(
            project_id=body.project_id,
            sources=[IssueSource.support.value],
            exclude_statuses=[IssueStatus.done.value, IssueStatus.cancelled.value],
        )
    else:
        description = body.description or ""
        filters = Filters(
            project_id=body.project_id,
            exclude_statuses=[IssueStatus.cancelled.value],
        )

    hits = await same_problem_candidates(
        db, actor, " ".join(p for p in (body.title, description) if p), filters=filters,
    )
    if not hits:
        return []

    issues = (await db.execute(
        select(Issue)
        .where(Issue.id.in_([h.issue_id for h in hits]))
        .options(selectinload(Issue.project))
    )).scalars().all()
    by_id = {i.id: i for i in issues}
    # A candidate cancelled since its last index refresh is never suggested (AC-S14).
    items = [
        JevItem(
            id=i.id, title=i.title,
            description=normalize(strip_markdown(i.description)),
            type=_value(i.type),
        )
        for i in (by_id.get(h.issue_id) for h in hits)
        if i is not None and _value(i.status) != IssueStatus.cancelled.value
    ]
    outcome, verdicts = await jev.judge_same(
        body.title, normalize(strip_markdown(description)), items,
    )
    if not outcome.ok:
        return None

    def shown(verdict: tuple) -> bool:
        label, confidence = verdict[0], verdict[1]
        return (
            label == "same" and confidence >= T_SAME
            or (body.context == "tech" and label == "related" and confidence >= T_RELATED)
        )

    picked = [h for h in hits if h.issue_id in verdicts and shown(verdicts[h.issue_id])]
    picked.sort(key=lambda h: (verdicts[h.issue_id][0] != "same", -verdicts[h.issue_id][1]))
    out = []
    for h in picked[:SIMILAR_LIMIT]:
        issue = by_id.get(h.issue_id)
        if issue is None:
            continue
        verdict, confidence, _probs = verdicts[h.issue_id]
        out.append({
            "verdict": verdict,
            "confidence": round(confidence, 4),
            "issue": {
                "id": issue.id,
                "key": issue_key(_value(issue.type), issue.issue_number),
                "type": _value(issue.type),
                "title": issue.title,
                "status": _value(issue.status),
                "issue_number": issue.issue_number,
                "project": {
                    "id": issue.project_id,
                    "name": issue.project.name if issue.project else None,
                    "slug": issue.project.slug if issue.project else None,
                },
            },
        })
    return out
