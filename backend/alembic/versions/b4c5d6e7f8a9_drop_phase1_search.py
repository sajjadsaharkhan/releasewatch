"""Remove the Phase 1 search objects (slice 12, engine PRD A.11, AC-S22)

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-01

- ``issue_embeddings`` goes, with whatever constraints and indexes it has —
  ``7f60b302c290`` altered its vector column and constraints and may or may
  not have run to completion on a given install, so nothing here assumes
  which state it left.
- ``issues.search_tsv`` and ``ix_issues_search_tsv`` go, if present.
- The ``llm`` settings go. An ``api`` provider's base URL becomes the new
  ``search.embedding_endpoint``; a ``local`` provider (or none) keeps the
  default endpoint, so no ``search`` row is written for it.

**Downgrade recreates nothing from Phase 1 search**: it is a no-op, and
downgrading the previous revision drops the engine tables. The index is
derived data (principle S5); the Phase 1 tables cannot be refilled without
the Phase 1 code this slice removed. This is the one sanctioned
non-reversible data effect of slice 12.
"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _endpoint_from_llm(value) -> str | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if not isinstance(value, dict):
        return None
    provider = value.get("embedding_provider") or value.get("embeddingProvider") or "local"
    base_url = value.get("base_url") or value.get("baseUrl") or ""
    if provider == "api" and base_url.strip():
        return base_url.strip().rstrip("/")
    return None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS issue_embeddings CASCADE")
    op.execute("DROP INDEX IF EXISTS ix_issues_search_tsv")
    op.execute("ALTER TABLE issues DROP COLUMN IF EXISTS search_tsv")

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT value FROM system_settings WHERE category = 'llm' AND key = 'config'")
    ).fetchall()
    endpoint = next((e for e in (_endpoint_from_llm(r[0]) for r in rows) if e), None)
    if endpoint:
        exists = conn.execute(
            sa.text("SELECT 1 FROM system_settings WHERE category = 'search' AND key = 'config'")
        ).first()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO system_settings (category, key, value, is_active) "
                    "VALUES ('search', 'config', CAST(:v AS jsonb), true)"
                ),
                {"v": json.dumps({"embedding_endpoint": endpoint})},
            )
    conn.execute(sa.text("DELETE FROM system_settings WHERE category = 'llm'"))


def downgrade() -> None:
    # Intentionally empty — see the module docstring.
    pass
