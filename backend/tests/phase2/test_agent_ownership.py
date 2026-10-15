"""Agent ownership — the last-writer rule as a pure unit table (slice 18).

docs/phase-2/18-mcp-own-content-and-prompts.md, prd-mcp.md BR-M07, BR-M14, A.5.
One row per piece kind × last writer × item state, like the Workflow and
Policy tables. ``app/agent_ownership.py`` takes plain values, so no database.
"""

import pytest

from app.agent_ownership import (
    ITEM_CLOSED,
    ITEM_TRIAGED,
    NOT_OWNER,
    ItemState,
    Piece,
    Record,
    decide,
)

USER, OTHER = 1, 2
USER_TOKENS = frozenset({10, 11})

#: The last writers of a piece.
WRITERS = {
    "agent": Record(USER, 10),             # this user's agent, the token in use
    "other_token": Record(USER, 11),       # this user's agent, another of their tokens
    "person": Record(USER, None),          # this user in the UI
    "other_person": Record(OTHER, None),   # someone else in the UI
    "other_agent": Record(OTHER, 20),      # another user's agent
    "foreign_token": Record(USER, 20),     # actor matches, token is not the user's
    "none": None,                          # no record at all
}
OWNERS = {"agent", "other_token"}

#: Item states: (type, status, in_backlog, filed_by_agent).
STATES = {
    "bug_new": ItemState("bug", "new", False, True),
    "bug_needs_info": ItemState("bug", "needs_info", False, True),
    "bug_todo": ItemState("bug", "todo", False, True),
    "bug_in_progress": ItemState("bug", "in_progress", False, True),
    "bug_done": ItemState("bug", "done", False, True),
    "bug_cancelled": ItemState("bug", "cancelled", False, True),
    "bug_new_by_person": ItemState("bug", "new", False, False),
    "task_backlog": ItemState("task", "todo", True, True),
    "task_placed": ItemState("task", "todo", False, True),
    "task_backlog_by_person": ItemState("task", "todo", True, False),
}

#: Expected verdict for an owned piece, per piece and state; ``None`` = allowed.
#: Every non-owner writer is ``not_owner`` in every state.
OWNED = {
    Piece.note: {s: None for s in STATES},
    Piece.attachment: {s: None for s in STATES},
    Piece.field: {
        "bug_new": None, "bug_needs_info": None, "bug_todo": None, "bug_in_progress": None,
        "bug_done": ITEM_CLOSED, "bug_cancelled": ITEM_CLOSED, "bug_new_by_person": None,
        "task_backlog": None, "task_placed": None, "task_backlog_by_person": None,
    },
    **{
        piece: {
            "bug_new": None, "bug_needs_info": ITEM_TRIAGED, "bug_todo": ITEM_TRIAGED,
            "bug_in_progress": ITEM_TRIAGED, "bug_done": ITEM_TRIAGED,
            "bug_cancelled": ITEM_TRIAGED,
            # Only an item the agent filed (BR-M14).
            "bug_new_by_person": NOT_OWNER,
            "task_backlog": None, "task_placed": ITEM_TRIAGED,
            "task_backlog_by_person": NOT_OWNER,
        }
        for piece in (Piece.title, Piece.description)
    },
}

ROWS = [
    pytest.param(
        piece, writer, state,
        OWNED[piece][state] if writer in OWNERS else NOT_OWNER,
        id=f"{piece.value}-{writer}-{state}",
    )
    for piece in Piece
    for writer in WRITERS
    for state in STATES
]


@pytest.mark.parametrize(("piece", "writer", "state", "expected"), ROWS)
def test_last_writer_table(piece, writer, state, expected):
    verdict = decide(STATES[state], piece, WRITERS[writer], USER, USER_TOKENS)
    assert verdict.allowed is (expected is None)
    assert verdict.code == expected
    if expected:
        assert verdict.reason and verdict.reason.endswith("Add a note instead.")


def test_a_revoked_token_still_counts_when_the_caller_passes_it():
    """Any of the user's tokens, active or not (BR-M07): the loader passes them all."""
    state = STATES["bug_todo"]
    assert decide(state, Piece.note, Record(USER, 99), USER, USER_TOKENS | {99}).allowed
    assert not decide(state, Piece.note, Record(USER, 99), USER, USER_TOKENS).allowed
