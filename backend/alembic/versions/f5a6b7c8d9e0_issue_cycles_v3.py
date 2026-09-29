"""issue_cycles: the v3 cycle model (08a Part 2)

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-09-30

docs/phase-2/cycle-model.md §6. One table holds cycles, including why each one
started; it replaces the Phase 1 regression model.

- ``issue_cycles`` gains ``release_id`` (the cycle's container, not null),
  ``start_reason`` (planned | review | release_qa | production),
  ``start_comment_id``, ``start_merged_issue_id``, ``start_by_id``,
  ``delivered_by_id``, ``picked_up_at``, ``submitted_at`` (was ``fixed_at``)
  and ``closed_at``; ``cycle_start_at`` becomes ``started_at``;
  ``regression_history_id``, ``triaged_at`` and the ``time_to_*_h`` columns go.
  ``(issue_id, cycle_number)`` is unique.
- ``issues.current_cycle_id`` — null exactly when ``release_id`` is null.
- ``regression_history``, ``issues.is_regression`` and
  ``issues.regression_count`` are dropped.

No data is carried over (Phase 2 has not shipped; rebuild dev databases with
``make db-reset``). Existing cycles are deleted; every item that has a
container gets a fresh cycle 1 (``planned``) so the invariant holds.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM issue_cycles")

    # ── The Phase 1 regression model goes ───────────────────────────────────
    op.drop_column('issue_cycles', 'regression_history_id')
    op.drop_table('regression_history')
    op.drop_column('issues', 'is_regression')
    op.drop_column('issues', 'regression_count')

    # ── issue_cycles, v3 shape ──────────────────────────────────────────────
    op.alter_column('issue_cycles', 'cycle_start_at', new_column_name='started_at')
    op.alter_column('issue_cycles', 'fixed_at', new_column_name='submitted_at')
    for column in ('triaged_at', 'time_to_triage_h', 'time_to_fix_h', 'time_to_verify_h'):
        op.drop_column('issue_cycles', column)
    op.alter_column('issue_cycles', 'cycle_number', server_default=None)

    op.add_column('issue_cycles', sa.Column(
        'release_id', sa.Integer(),
        sa.ForeignKey('releases.id', ondelete='CASCADE', name='fk_issue_cycles_release_id'),
        nullable=False,
    ))
    op.add_column('issue_cycles', sa.Column('start_reason', sa.String(length=16), nullable=False))
    op.add_column('issue_cycles', sa.Column(
        'start_comment_id', sa.Integer(),
        sa.ForeignKey('issue_timeline.id', ondelete='SET NULL', name='fk_issue_cycles_start_comment_id'),
        nullable=True,
    ))
    op.add_column('issue_cycles', sa.Column(
        'start_merged_issue_id', sa.Integer(),
        sa.ForeignKey('issues.id', ondelete='SET NULL', name='fk_issue_cycles_start_merged_issue_id'),
        nullable=True,
    ))
    op.add_column('issue_cycles', sa.Column(
        'start_by_id', sa.Integer(),
        sa.ForeignKey('users.id', ondelete='SET NULL', name='fk_issue_cycles_start_by_id'),
        nullable=True,
    ))
    op.add_column('issue_cycles', sa.Column(
        'delivered_by_id', sa.Integer(),
        sa.ForeignKey('users.id', ondelete='SET NULL', name='fk_issue_cycles_delivered_by_id'),
        nullable=True,
    ))
    op.add_column('issue_cycles', sa.Column('picked_up_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('issue_cycles', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_issue_cycles_release_id', 'issue_cycles', ['release_id'])
    op.create_index('ix_issue_cycles_delivered_by_id', 'issue_cycles', ['delivered_by_id'])
    op.create_unique_constraint(
        'uq_issue_cycles_issue_id_cycle_number', 'issue_cycles', ['issue_id', 'cycle_number'],
    )
    op.create_check_constraint(
        'ck_issue_cycles_start_reason', 'issue_cycles',
        "start_reason IN ('planned', 'review', 'release_qa', 'production')",
    )

    # ── issues.current_cycle_id ─────────────────────────────────────────────
    op.add_column('issues', sa.Column(
        'current_cycle_id', sa.Integer(),
        sa.ForeignKey('issue_cycles.id', ondelete='SET NULL', name='fk_issues_current_cycle_id'),
        nullable=True,
    ))

    # Every placed item starts fresh at cycle 1 (planned).
    op.execute("""
        INSERT INTO issue_cycles (issue_id, cycle_number, release_id, start_reason, assignee_id, started_at)
        SELECT id, 1, release_id, 'planned', assignee_id, coalesce(triaged_at, filed_at, created_at)
        FROM issues WHERE release_id IS NOT NULL
    """)
    op.execute("""
        UPDATE issues SET current_cycle_id = c.id
        FROM issue_cycles c WHERE c.issue_id = issues.id
    """)


def downgrade() -> None:
    op.drop_column('issues', 'current_cycle_id')
    op.execute("DELETE FROM issue_cycles")

    op.drop_constraint('ck_issue_cycles_start_reason', 'issue_cycles', type_='check')
    op.drop_constraint('uq_issue_cycles_issue_id_cycle_number', 'issue_cycles', type_='unique')
    op.drop_index('ix_issue_cycles_delivered_by_id', table_name='issue_cycles')
    op.drop_index('ix_issue_cycles_release_id', table_name='issue_cycles')
    for column in (
        'closed_at', 'picked_up_at', 'delivered_by_id', 'start_by_id',
        'start_merged_issue_id', 'start_comment_id', 'start_reason', 'release_id',
    ):
        op.drop_column('issue_cycles', column)
    op.alter_column('issue_cycles', 'cycle_number', server_default='1')
    op.add_column('issue_cycles', sa.Column('triaged_at', sa.DateTime(timezone=True), nullable=True))
    for column in ('time_to_triage_h', 'time_to_fix_h', 'time_to_verify_h'):
        op.add_column('issue_cycles', sa.Column(column, sa.Float(), nullable=True))
    op.alter_column('issue_cycles', 'submitted_at', new_column_name='fixed_at')
    op.alter_column('issue_cycles', 'started_at', new_column_name='cycle_start_at')

    op.add_column('issues', sa.Column(
        'regression_count', sa.SmallInteger(), nullable=False, server_default='0',
    ))
    op.add_column('issues', sa.Column(
        'is_regression', sa.Boolean(), nullable=False, server_default='false',
    ))
    op.create_table(
        'regression_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('issue_id', sa.Integer(), sa.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('release_id', sa.Integer(), sa.ForeignKey('releases.id', ondelete='CASCADE'), nullable=True),
        sa.Column('source', sa.String(length=16), nullable=False, server_default='action'),
        sa.Column('regression_number', sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('detected_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('previous_fix_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column(
            'previous_fix_timeline_id', sa.Integer(),
            sa.ForeignKey('issue_timeline.id', ondelete='SET NULL'), nullable=True,
        ),
    )
    op.alter_column('regression_history', 'source', server_default=None)
    op.create_index('ix_regression_history_issue_id', 'regression_history', ['issue_id'])
    op.create_index('ix_regression_history_release_id', 'regression_history', ['release_id'])
    op.add_column('issue_cycles', sa.Column(
        'regression_history_id', sa.Integer(),
        sa.ForeignKey('regression_history.id', ondelete='SET NULL'), nullable=True,
    ))
