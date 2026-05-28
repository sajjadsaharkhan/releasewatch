"""Labels endpoints — manage predefined issue tags.

GET    /labels              — list all labels
POST   /labels              — create a label
GET    /labels/{id}         — get label by id
PATCH  /labels/{id}         — update label
DELETE /labels/{id}         — delete label
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_role
from app.db.models.issue import Issue
from app.db.models.label import Label
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.label import LabelCreate, LabelUpdate, LabelResponse, LabelWithCount

router = APIRouter()


@router.get("", response_model=List[LabelWithCount], summary="List all labels")
async def list_labels(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[LabelWithCount]:
    """Return all labels with their issue counts."""
    # Get all labels first
    labels_result = await db.execute(
        select(Label).order_by(Label.name)
    )
    labels = labels_result.scalars().all()

    # For each label, count issues that have it in their labels array
    result = []
    for label in labels:
        count_result = await db.execute(
            select(func.count())
            .select_from(Issue)
            .where(Issue.labels.any(label.name))
        )
        issue_count = count_result.scalar() or 0

        result.append(LabelWithCount(
            id=label.id,
            name=label.name,
            color=label.color,
            created_at=label.created_at,
            issue_count=issue_count,
        ))

    return result


@router.post(
    "",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a label",
)
async def create_label(
    payload: LabelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cto, UserRole.triage_lead)),
) -> LabelResponse:
    """Create a new label (admin / CTO / triage lead only)."""
    # Check name uniqueness
    existing = await db.execute(select(Label).where(Label.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Label '{payload.name}' already exists.",
        )

    label = Label(
        name=payload.name,
        color=payload.color,
    )
    db.add(label)
    await db.commit()
    await db.refresh(label)
    return LabelResponse.model_validate(label)


@router.get("/{label_id}", response_model=LabelWithCount, summary="Get label by id")
async def get_label(
    label_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LabelWithCount:
    """Return a single label with its issue count."""
    try:
        label_int_id = int(label_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid label ID format.",
        )

    # Get the label
    result = await db.execute(select(Label).where(Label.id == label_int_id))
    label = result.scalar_one_or_none()

    if label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label '{label_id}' not found.",
        )

    # Get issue count for this label (count issues where label name is in the labels array)
    issue_count_result = await db.execute(
        select(func.count())
        .select_from(Issue)
        .where(Issue.labels.any(label.name))
    )
    issue_count = issue_count_result.scalar() or 0

    return LabelWithCount(
        id=label.id,
        name=label.name,
        color=label.color,
        created_at=label.created_at,
        issue_count=issue_count,
    )


@router.patch("/{label_id}", response_model=LabelResponse, summary="Update label")
async def update_label(
    label_id: str,
    payload: LabelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cto, UserRole.triage_lead)),
) -> LabelResponse:
    """Partially update a label's metadata."""
    try:
        label_int_id = int(label_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid label ID format.",
        )

    label = await _get_label_or_404(db, label_int_id)
    update_data = payload.model_dump(exclude_unset=True)

    # Check name uniqueness if name is being updated
    if "name" in update_data and update_data["name"] != label.name:
        existing = await db.execute(select(Label).where(Label.name == update_data["name"]))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Label '{update_data['name']}' already exists.",
            )

    for field, value in update_data.items():
        setattr(label, field, value)
    db.add(label)
    await db.commit()
    await db.refresh(label)
    return LabelResponse.model_validate(label)


@router.delete(
    "/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a label",
)
async def delete_label(
    label_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cto)),
) -> None:
    """Delete a label (admin / CTO only)."""
    try:
        label_int_id = int(label_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid label ID format.",
        )

    label = await _get_label_or_404(db, label_int_id)
    await db.delete(label)
    await db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_label_or_404(db: AsyncSession, label_id: int) -> Label:
    result = await db.execute(select(Label).where(Label.id == label_id))
    label = result.scalar_one_or_none()
    if label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label '{label_id}' not found",
        )
    return label
