"""Search API (slice 12, engine PRD Appendix A.9).

GET  /search                    — stage-1 search; the search page and the command palette
POST /search/similar            — same-problem suggestions while writing a report (slice 14)
GET  /features                  — what the UI may show ({jev_enabled})
GET  /settings/search           — Admin: endpoint, model, index status, Jev (FR-S17)
PUT  /settings/search           — Admin: change the endpoint; a change reindexes (FR-S19)
POST /settings/search/reindex   — Admin: Reindex all
PUT  /settings/search/jev       — Admin: Jev switch, key (write-only), model (FR-S18)
POST /settings/search/jev/test  — Admin: Test connection with the saved key
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_role
from app.db.models.issue import IssueStatus, IssueType
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.policy import Action, is_tech
from app.schemas.search import SimilarItemsRequest
from app.schemas.settings import JevSettingsUpdate, SearchSettingsUpdate
from app.search import admin, jev_settings
from app.search.retrieval import Filters, search
from app.search.similar import suggest
from app.services.authz import authorize
from app.tasks import search_index

router = APIRouter()
features_router = APIRouter()
settings_router = APIRouter()


@router.get("", summary="Search items (stage 1)")
async def search_items(
    q: str = Query(..., min_length=1, max_length=500),
    scope: Literal["project", "all"] = Query("project"),
    project_id: int | None = Query(None, description="Required when scope=project"),
    type_: list[IssueType] | None = Query(None, alias="type"),
    status_: list[IssueStatus] | None = Query(None, alias="status"),
    mode: Literal["page", "palette"] = Query("page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """``mode=palette`` returns at most 8 results and no comment snippets, and
    never calls Jev (BR-S05). Results only ever include items the caller may
    see, matched only through content they may see (BR-S06)."""
    if scope == "project" and project_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="project_id is required when scope=project",
        )
    filters = Filters(
        project_id=project_id if scope == "project" else None,
        types=[t.value for t in type_ or []],
        statuses=[s.value for s in status_ or []],
    )
    ranked = await search(db, current_user, q, filters=filters, mode=mode)
    return ranked.as_dict()


@router.post(
    "/similar",
    response_model=None,
    summary="Same-problem suggestions while writing a report (slice 14)",
    responses={200: {"description": "Suggestions"}, 204: {"description": "No panel"}},
)
async def similar_items(
    body: SimilarItemsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict | Response:
    """``context=support`` is the Support form's panel (Support and Admin);
    ``context=tech`` is the create form's (every tech role — a Support caller
    gets 403). Jev off or failing answers 204: the UI hides the panel, never
    errors (BR-S02). Suggestions only ever include items the caller may see."""
    if body.context == "support":
        authorize(current_user, Action.submit_support_report)
    elif not is_tech(current_user.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tech roles only")

    items = await suggest(db, current_user, body)
    if items is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return {"items": items}


@features_router.get("", summary="Feature flags the UI reads")
async def features(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return {"jev_enabled": await jev_settings.is_enabled(db)}



@settings_router.get("", summary="Search settings and index status (Admin)")
async def get_search_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> dict:
    return await admin.status_of(db)


@settings_router.put("", summary="Change the embedding endpoint (Admin)")
async def put_search_settings(
    body: SearchSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> dict:
    changed = await admin.change_endpoint(db, body.embedding_endpoint)
    await db.commit()
    reindex_started = search_index.request_reindex_all() if changed else False
    return {**await admin.status_of(db), "reindex_started": reindex_started}


@settings_router.post(
    "/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reindex all items (Admin)",
)
async def reindex(current_user: User = Depends(require_role(UserRole.admin))) -> dict:
    return {"reindex_started": search_index.request_reindex_all()}


@settings_router.put("/jev", summary="Jev switch, key and model (Admin)")
async def put_jev_settings(
    body: JevSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> dict:
    """409 ``jev_test_required`` when switching on without a passing test with the
    saved key. Saving a new key switches Jev off and clears the test."""
    _, switched_on = await jev_settings.update(
        db, enabled=body.enabled, api_key=body.api_key, model=body.model,
    )
    await db.commit()
    if switched_on:
        search_index.request_backfill()
    return await admin.jev_status(db)


@settings_router.post("/jev/test", summary="Test the Jev connection with the saved key (Admin)")
async def test_jev_connection(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> dict:
    result = await admin.test_jev(db)
    await db.commit()
    return result
