"""add comment reactions

Revision ID: 9186202809a6
Revises: b3f8c1a29d47
Create Date: 2026-08-07 18:54:00.057402

Autogenerate reported a large amount of pre-existing drift between the models
and the live schema (server defaults, unique constraints on users/labels/
projects, the issue_embeddings vector dimension).  None of it belongs to this
feature, so this revision was trimmed by hand to the comment_reactions table
only.  The drift is untouched and still outstanding.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9186202809a6'
down_revision: Union[str, None] = 'b3f8c1a29d47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'comment_reactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('timeline_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('emoji_key', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['timeline_id'], ['issue_timeline.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('timeline_id', 'user_id', 'emoji_key', name='uq_comment_reaction'),
    )
    op.create_index(
        op.f('ix_comment_reactions_timeline_id'),
        'comment_reactions',
        ['timeline_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_comment_reactions_timeline_id'), table_name='comment_reactions')
    op.drop_table('comment_reactions')
