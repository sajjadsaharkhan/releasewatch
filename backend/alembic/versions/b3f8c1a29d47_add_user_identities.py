"""add user_identities table and make users.hashed_password nullable

Revision ID: b3f8c1a29d47
Revises: 1ac9e1dbe524
Create Date: 2026-08-07

Adds the vendor-neutral external-identity link table used by optional
Keycloak (OIDC) and LDAP federated login, and relaxes users.hashed_password
to nullable so users provisioned purely via a provider need no local password.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3f8c1a29d47'
down_revision: Union[str, None] = '1ac9e1dbe524'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_identities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('provider_subject', sa.String(length=255), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'provider', 'provider_subject', name='uq_identity_provider_subject'
        ),
    )
    op.create_index(
        op.f('ix_user_identities_user_id'), 'user_identities', ['user_id'], unique=False
    )

    # Users provisioned purely via a provider have no local password.
    op.alter_column('users', 'hashed_password', existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    # Backfill any NULL passwords before re-imposing NOT NULL, so downgrade never fails.
    op.execute("UPDATE users SET hashed_password = '' WHERE hashed_password IS NULL")
    op.alter_column('users', 'hashed_password', existing_type=sa.String(length=255), nullable=False)

    op.drop_index(op.f('ix_user_identities_user_id'), table_name='user_identities')
    op.drop_table('user_identities')
