"""keep what the triager saw when dismissing a duplicate hint

Revision ID: b4d8e2f6a1c9
Revises: a7c3d9e1f2b4
Create Date: 2026-10-02

``duplicate_dismissals`` gains Jev's confidence and model, when the hint was
computed, and a snapshot of both items' title and description (plus the
candidate's status), so "Not a duplicate" clicks can later tune the similarity
threshold or train a model. All nullable: existing rows have none of it.

Written by hand.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b4d8e2f6a1c9'
down_revision: Union[str, None] = 'a7c3d9e1f2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ('confidence', sa.Float()),
    ('jev_model', sa.String(length=64)),
    ('hint_computed_at', sa.DateTime(timezone=True)),
    ('issue_title', sa.Text()),
    ('issue_description', sa.Text()),
    ('candidate_title', sa.Text()),
    ('candidate_description', sa.Text()),
    ('candidate_status', sa.String(length=32)),
)


def upgrade() -> None:
    for name, type_ in _COLUMNS:
        op.add_column('duplicate_dismissals', sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_COLUMNS):
        op.drop_column('duplicate_dismissals', name)
