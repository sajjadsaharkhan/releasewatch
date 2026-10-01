"""AC-S22 — the slice-12 migrations, from a Phase 1 install and from nothing.

Phase 1 path: downgrade the test database to the pre-12 head, put back the
Phase 1 search objects in the state ``7f60b302c290`` left them (1536-dim
vector column, the per-group unique constraint, no HNSW index, a generated
``search_tsv``) plus an ``api`` LLM setting, then upgrade to head and inspect.

Fresh path: migrate a brand-new, empty database from base to head. Both must
end with the same schema. Always leaves the test database back at ``head``.
"""

import asyncio
import json
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config

from alembic import command
from app.config import settings
from app.db.session import get_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PRE_12_HEAD = "f2a3b4c5d6e7"
FRESH_DB = f"{settings.POSTGRES_DB}_fresh"


def _alembic_config(database_url: str | None = None) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    if database_url:
        cfg.attributes["database_url"] = database_url
    return cfg


async def _connect(database: str) -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=database,
    )


async def _schema(conn: asyncpg.Connection) -> dict:
    columns = await conn.fetch(
        "SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' ORDER BY table_name, column_name"
    )
    indexes = await conn.fetch(
        "SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public' "
        "ORDER BY tablename, indexname"
    )
    extensions = await conn.fetch("SELECT extname FROM pg_extension ORDER BY extname")
    return {
        "columns": [tuple(r) for r in columns],
        "indexes": [tuple(r) for r in indexes],
        "extensions": [r[0] for r in extensions],
    }


def _assert_engine_schema(schema: dict) -> None:
    tables = {c[0] for c in schema["columns"]}
    assert {"search_items", "search_vectors", "comment_labels"} <= tables
    assert "issue_embeddings" not in tables
    assert ("issues", "search_tsv") not in {(c[0], c[1]) for c in schema["columns"]}
    index_names = {i[1] for i in schema["indexes"]}
    assert "ix_issues_search_tsv" not in index_names
    assert {"ix_search_items_keyword_trgm", "ix_search_vectors_embedding_hnsw"} <= index_names
    assert "pg_trgm" in schema["extensions"]


async def _put_back_phase1_search() -> None:
    conn = await _connect(settings.POSTGRES_DB)
    try:
        await conn.execute("""
            CREATE TABLE issue_embeddings (
                id serial PRIMARY KEY,
                issue_id integer NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
                project_id integer NOT NULL,
                field_group varchar(16) NOT NULL,
                embedding vector(1536) NOT NULL,
                content_hash varchar(64) NOT NULL,
                model varchar(128) NOT NULL,
                updated_at timestamptz NOT NULL,
                CONSTRAINT uq_issue_embeddings_issue_group UNIQUE (issue_id, field_group)
            )
        """)
        await conn.execute(
            "CREATE INDEX ix_issue_embeddings_issue_id ON issue_embeddings (issue_id)"
        )
        await conn.execute("""
            ALTER TABLE issues ADD COLUMN search_tsv tsvector GENERATED ALWAYS AS (
                setweight(to_tsvector('english', coalesce(title,'')), 'A') ||
                setweight(to_tsvector('english', coalesce(description,'')), 'B')
            ) STORED
        """)
        await conn.execute("CREATE INDEX ix_issues_search_tsv ON issues USING GIN (search_tsv)")
        await conn.execute(
            "INSERT INTO system_settings (category, key, value, is_active) "
            "VALUES ('llm', 'config', $1::jsonb, true)",
            json.dumps(
                {
                    "embedding_provider": "api",
                    "base_url": "https://embed.internal/v1/",
                    "api_key": "phase1-key",
                    "embedding_model": "text-embedding-3-small",
                }
            ),
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_ac_s22_migration_from_phase1_and_fresh(factories, db_session):
    # An item exists, so "a reindex can populate the engine tables" has something to do.
    project = await factories.project()
    await factories.issue(project_id=project.id, title="Phase 1 item")

    await db_session.rollback()
    await get_engine().dispose()
    try:
        await asyncio.to_thread(command.downgrade, _alembic_config(), PRE_12_HEAD)
        await _put_back_phase1_search()
        await asyncio.to_thread(command.upgrade, _alembic_config(), "head")
    finally:
        # Whatever happened above, hand the rest of the suite a head database.
        await asyncio.to_thread(command.upgrade, _alembic_config(), "head")

    conn = await _connect(settings.POSTGRES_DB)
    try:
        upgraded = await _schema(conn)
        settings_rows = await conn.fetch(
            "SELECT category, value FROM system_settings WHERE category IN ('llm', 'search')"
        )
        assert await conn.fetchval("SELECT count(*) FROM search_items") == 0
        assert await conn.fetchval("SELECT count(*) FROM issues") == 1
    finally:
        await conn.close()
    _assert_engine_schema(upgraded)
    assert [(r["category"], json.loads(r["value"])) for r in settings_rows] == [
        ("search", {"embedding_endpoint": "https://embed.internal/v1"}),
    ]

    admin = await _connect("postgres")
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{FRESH_DB}" WITH (FORCE)')
        await admin.execute(f'CREATE DATABASE "{FRESH_DB}"')
    finally:
        await admin.close()
    fresh_url = settings.database_url.rsplit("/", 1)[0] + f"/{FRESH_DB}"
    try:
        await asyncio.to_thread(command.upgrade, _alembic_config(fresh_url), "head")
        conn = await _connect(FRESH_DB)
        try:
            fresh = await _schema(conn)
        finally:
            await conn.close()
    finally:
        admin = await _connect("postgres")
        try:
            await admin.execute(f'DROP DATABASE IF EXISTS "{FRESH_DB}" WITH (FORCE)')
        finally:
            await admin.close()

    _assert_engine_schema(fresh)
    assert fresh == upgraded


@pytest.mark.asyncio
async def test_a_local_llm_provider_keeps_the_default_endpoint(db_session):
    await db_session.rollback()
    await get_engine().dispose()
    try:
        await asyncio.to_thread(command.downgrade, _alembic_config(), PRE_12_HEAD)
        conn = await _connect(settings.POSTGRES_DB)
        try:
            await conn.execute(
                "INSERT INTO system_settings (category, key, value, is_active) "
                "VALUES ('llm', 'config', $1::jsonb, true)",
                json.dumps({"embedding_provider": "local", "base_url": "https://ignored/v1"}),
            )
        finally:
            await conn.close()
    finally:
        await asyncio.to_thread(command.upgrade, _alembic_config(), "head")

    conn = await _connect(settings.POSTGRES_DB)
    try:
        rows = await conn.fetch(
            "SELECT category FROM system_settings WHERE category IN ('llm', 'search')"
        )
    finally:
        await conn.close()
    assert rows == []
