"""Schema guard: timestamp defaults are evaluated per row."""

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_no_timestamp_default_is_frozen(db_session):
    """A default written as the string ``'now()'`` is evaluated once, at CREATE
    TABLE, and stamps every later row with that moment (users.created_at did,
    which What's new's new-account rule relies on). Defaults must be ``now()``."""
    rows = await db_session.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND column_default LIKE '''%'"
        " AND data_type LIKE 'timestamp%'"
    ))
    assert rows.all() == []
