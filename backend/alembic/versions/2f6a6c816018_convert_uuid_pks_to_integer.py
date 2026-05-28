"""Convert all UUID primary keys to auto-increment integers.

All entity tables previously used UUID v4 PKs. This migration drops and
recreates every table with INTEGER GENERATED ALWAYS AS IDENTITY primary keys
and INTEGER foreign key references. Existing data is not preserved — intended
for development environments only.

Revision ID: 2f6a6c816018
Revises: f1a2b3c4d5e6
Create Date: 2026-05-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f6a6c816018"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop all tables in reverse-FK order (children before parents)
    op.execute("DROP TABLE IF EXISTS inbox_items CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_cycles CASCADE")
    op.execute("DROP TABLE IF EXISTS regression_history CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_attachments CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_timeline CASCADE")
    op.execute("DROP TABLE IF EXISTS issues CASCADE")
    op.execute("DROP TABLE IF EXISTS releases CASCADE")
    op.execute("DROP TABLE IF EXISTS projects CASCADE")
    op.execute("DROP TABLE IF EXISTS labels CASCADE")
    op.execute("DROP TABLE IF EXISTS system_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP SEQUENCE IF EXISTS issue_number_seq CASCADE")

    # Recreate issue_number sequence
    op.execute("CREATE SEQUENCE issue_number_seq START 10")

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="qa"),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True, unique=True),
        sa.Column("telegram_handle", sa.String(128), nullable=True),
        sa.Column("telegram_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connect_token", sa.String(64), nullable=True),
        sa.Column("connect_token_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("bio", sa.String(2000), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("avatar_color", sa.String(7), nullable=False, server_default="#6366f1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"])
    op.create_index("ix_users_connect_token", "users", ["connect_token"])

    # labels
    op.create_table(
        "labels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("color", sa.String(7), nullable=False, server_default="#6366f1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_labels_name", "labels", ["name"])

    # system_settings
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_system_settings_category", "system_settings", ["category"])
    op.create_index("ix_system_settings_key", "system_settings", ["key"])

    # projects
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("color", sa.String(7), nullable=False, server_default="#6366f1"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_labels", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_projects_slug", "projects", ["slug"])

    # releases
    op.create_table(
        "releases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("staging_url", sa.String(512), nullable=True),
        sa.Column("go_nogo_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("go_nogo_note", sa.Text(), nullable=True),
        sa.Column("go_nogo_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("go_nogo_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_releases_project_id", "releases", ["project_id"])

    # issues
    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issue_number", sa.Integer(), nullable=False, server_default=sa.text("nextval('issue_number_seq')")),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("release_id", sa.Integer(), sa.ForeignKey("releases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(32), nullable=False, server_default="minor"),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("labels", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("is_release_blocker", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_regression", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("regression_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("parent_issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("environment_browser", sa.String(128), nullable=True),
        sa.Column("environment_os", sa.String(128), nullable=True),
        sa.Column("environment_build_hash", sa.String(64), nullable=True),
        sa.Column("environment_staging_url", sa.String(512), nullable=True),
        sa.Column("curl_command", sa.Text(), nullable=True),
        sa.Column("environment_name", sa.String(32), nullable=True),
        sa.Column("reproduction_steps", sa.JSON(), nullable=True),
        sa.Column("time_to_triage_h", sa.Float(), nullable=True),
        sa.Column("time_to_fix_h", sa.Float(), nullable=True),
        sa.Column("time_to_verify_h", sa.Float(), nullable=True),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triaged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fixed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_issues_project_id", "issues", ["project_id"])
    op.create_index("ix_issues_release_id", "issues", ["release_id"])
    op.create_index("ix_issues_reporter_id", "issues", ["reporter_id"])
    op.create_index("ix_issues_assignee_id", "issues", ["assignee_id"])

    # issue_timeline
    op.create_table(
        "issue_timeline",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_issue_timeline_issue_id", "issue_timeline", ["issue_id"])

    # issue_attachments
    op.create_table(
        "issue_attachments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("s3_key", sa.String(1024), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("attachment_type", sa.String(32), nullable=False, server_default="other"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_issue_attachments_issue_id", "issue_attachments", ["issue_id"])

    # regression_history
    op.create_table(
        "regression_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("release_id", sa.Integer(), sa.ForeignKey("releases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("regression_number", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("detected_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("previous_fix_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("previous_fix_timeline_id", sa.Integer(), sa.ForeignKey("issue_timeline.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_regression_history_issue_id", "regression_history", ["issue_id"])
    op.create_index("ix_regression_history_release_id", "regression_history", ["release_id"])

    # issue_cycles
    op.create_table(
        "issue_cycles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cycle_number", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("regression_history_id", sa.Integer(), sa.ForeignKey("regression_history.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cycle_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("triaged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fixed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_to_triage_h", sa.Float(), nullable=True),
        sa.Column("time_to_fix_h", sa.Float(), nullable=True),
        sa.Column("time_to_verify_h", sa.Float(), nullable=True),
    )
    op.create_index("ix_issue_cycles_issue_id", "issue_cycles", ["issue_id"])

    # inbox_items
    op.create_table(
        "inbox_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timeline_id", sa.Integer(), sa.ForeignKey("issue_timeline.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_inbox_items_actor_id", "inbox_items", ["actor_id"])
    op.create_index("ix_inbox_items_issue_id", "inbox_items", ["issue_id"])
    op.create_index("ix_inbox_items_user_is_read", "inbox_items", ["user_id", "is_read"])


def downgrade() -> None:
    # This migration is destructive — no safe downgrade path.
    # To revert, restore from backup or re-run the previous migration chain.
    op.execute("DROP TABLE IF EXISTS inbox_items CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_cycles CASCADE")
    op.execute("DROP TABLE IF EXISTS regression_history CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_attachments CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_timeline CASCADE")
    op.execute("DROP TABLE IF EXISTS issues CASCADE")
    op.execute("DROP TABLE IF EXISTS releases CASCADE")
    op.execute("DROP TABLE IF EXISTS projects CASCADE")
    op.execute("DROP TABLE IF EXISTS labels CASCADE")
    op.execute("DROP TABLE IF EXISTS system_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP SEQUENCE IF EXISTS issue_number_seq CASCADE")
