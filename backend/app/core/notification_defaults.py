"""Default notification matrix — shared between settings API and inbox fan-out.

Keys align with InboxEventType values.
Roles: reporter/assignee are per-issue relationships; triage/cto are team roles;
subscriber (slice 06) is anyone on the item's ``issue_subscribers`` list.
"""

#: Every relationship a matrix row can switch on — the settings UI renders one column each.
MATRIX_KEYS: tuple[str, ...] = ("reporter", "assignee", "triage", "cto", "subscriber")


def _row(reporter=False, assignee=False, triage=False, cto=False, subscriber=False) -> dict[str, bool]:
    return {
        "reporter": reporter, "assignee": assignee, "triage": triage, "cto": cto,
        "subscriber": subscriber,
    }


DEFAULT_NOTIFICATION_MATRIX: dict[str, dict[str, bool]] = {
    "filed":               _row(reporter=True, triage=True, cto=True),
    "assigned":            _row(assignee=True),
    "mention":             _row(reporter=True, assignee=True, triage=True, cto=True),
    "comment":             _row(reporter=True, assignee=True),
    "status_changed":      _row(reporter=True, assignee=True),
    "item_returned":       _row(assignee=True),
    "fixed":               _row(reporter=True),
    "verified":            _row(assignee=True),
    "blocker_filed":       _row(triage=True, cto=True),
    "blocker_cleared":     _row(reporter=True, assignee=True, triage=True, cto=True),
    "release_gate":        _row(triage=True, cto=True),
    "environment_changed": _row(reporter=True, assignee=True),
    "release_changed":     _row(reporter=True, assignee=True, triage=True),
    "due_date_changed":    _row(reporter=True, assignee=True),
    "project_changed":     _row(reporter=True, assignee=True, triage=True),
    "attachment_added":    _row(reporter=True, assignee=True),
    "priority_changed":    _row(reporter=True, assignee=True, triage=True),
    "needs_clarification": _row(reporter=True),
    # Slice 06 — to the triage lead (§13).
    "needs_info_replied":      _row(triage=True),
    "moved_into_project":      _row(triage=True),
    "recurrence_on_cancelled": _row(triage=True),
    # Slice 06 — to Support subscribers, the only events Support receives (§13).
    "support_needs_info":  _row(subscriber=True),
    "support_cancelled":   _row(subscriber=True),
    "support_done":        _row(subscriber=True),
    # Slice 09 — about a release, not an item.
    "release_shipped":     _row(assignee=True, cto=True),
    "release_overdue":     _row(cto=True),
    # Slice 10 — to the queue owner / assignee only.
    "queue_changed":       _row(assignee=True),
    "due_soon":            _row(assignee=True),
    "overdue":             _row(assignee=True),
}


def resolve_matrix(stored: dict | None) -> dict[str, dict[str, bool]]:
    """Overlay a saved matrix on the defaults, row by row.

    Merging per row (not per event) means a matrix saved before a key existed
    — ``subscriber`` from slice 06 — still gets that key's default.
    """
    matrix = {event: dict(row) for event, row in DEFAULT_NOTIFICATION_MATRIX.items()}
    for event, row in (stored or {}).items():
        if isinstance(row, dict):
            matrix[event] = {**matrix.get(event, _row()), **row}
    return matrix
