"""Slice 10 — the pure queue-ordering rules (``app/queue_order.py``).

The behaviour is proven end to end through ``GET /users/{id}/queue`` in
``test_personal_queue.py``; these pin down the edge cases of the default rule
and the move arithmetic without a database.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.queue_order import (
    QueueItem,
    QueueRuleError,
    absolute_index,
    default_key,
    insertion_index,
    move_index,
    position_at,
    renumbered,
)

T0 = datetime(2026, 9, 1, tzinfo=UTC)


def _item(
    issue_id, priority="medium", due=None, recurrence=1, age_days=0, pinned=False, position=0.0,
):
    return QueueItem(
        issue_id=issue_id, priority=priority, due_date=due, recurrence_count=recurrence,
        created_at=T0 - timedelta(days=age_days), pinned=pinned, position=position,
    )


def test_ties_on_every_key_fall_back_to_age():
    older, newer = _item(1, age_days=3), _item(2, age_days=1)
    assert default_key(older) < default_key(newer)


def test_null_due_date_sorts_after_any_date():
    dated, undated = _item(1, due=date(2099, 1, 1)), _item(2, due=None, age_days=10)
    assert default_key(dated) < default_key(undated)


def test_priority_beats_due_date_and_recurrence():
    high = _item(1, priority="high")
    medium = _item(2, priority="medium", due=date(2026, 9, 2), recurrence=9)
    assert default_key(high) < default_key(medium)


def test_more_reports_rank_higher_within_a_due_date():
    assert default_key(_item(1, recurrence=5)) < default_key(_item(2, recurrence=2, age_days=5))


def test_unrated_sorts_after_low():
    assert default_key(_item(1, priority="low")) < default_key(_item(2, priority=None, age_days=5))


def test_insertion_above_first_lower_ranked_even_in_manual_order():
    # Manual order deliberately not the default: low, critical, medium.
    rest = [_item(1, "low"), _item(2, "critical"), _item(3, "medium")]
    new = _item(4, "high")
    # The first item ranking lower than High is the Low one at index 0.
    assert insertion_index(new, rest) == 0


def test_insertion_at_end_when_nothing_ranks_lower():
    rest = [_item(1, "critical"), _item(2, "high")]
    assert insertion_index(_item(3, "low"), rest) == 2


def test_position_at_ends_and_midpoint():
    assert position_at([], 0) == 1024.0
    assert position_at([10.0, 20.0], 0) < 10.0
    assert position_at([10.0, 20.0], 2) > 20.0
    assert position_at([10.0, 20.0], 1) == 15.0


def test_position_at_refuses_a_too_narrow_gap():
    assert position_at([1.0, 1.0 + 1e-7], 1) is None
    assert renumbered(3) == [1024.0, 2048.0, 3072.0]


def test_position_never_collides_with_a_dormant_entry():
    # Visible 1024 and 3072 with a dormant item at 2048 between them: the
    # plain midpoint would be 2048. The new item goes directly above 3072.
    position = position_at([1024.0, 3072.0], 1, dormant=[2048.0])
    assert 2048.0 < position < 3072.0
    # At the top of the group, above every visible item but below a dormant one above them.
    assert 512.0 < position_at([1024.0], 0, dormant=[512.0]) < 1024.0
    # At the end, past the dormant tail too.
    assert position_at([1024.0], 1, dormant=[4096.0]) > 4096.0


def test_move_within_group():
    items = [_item(1, position=1), _item(2, position=2), _item(3, position=3)]
    assert move_index(items, 3, before_id=1) == 0
    assert move_index(items, 1, after_id=3) == 2


def test_move_across_groups_is_refused():
    items = [_item(1, pinned=True, position=1), _item(2, position=1)]
    with pytest.raises(QueueRuleError) as err:
        move_index(items, 2, before_id=1)
    assert err.value.code == "queue_group_boundary"
    assert "Pin" in err.value.detail


def test_move_needs_exactly_one_anchor():
    items = [_item(1, position=1), _item(2, position=2)]
    with pytest.raises(QueueRuleError):
        move_index(items, 1)
    with pytest.raises(QueueRuleError):
        move_index(items, 1, before_id=2, after_id=2)


def test_absolute_index_counts_pins_first():
    items = [_item(1, position=1), _item(2, pinned=True, position=5)]
    assert absolute_index(items, 2) == 1
    assert absolute_index(items, 1) == 2
