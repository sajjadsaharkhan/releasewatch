"""Default notification matrix — shared between settings API and inbox fan-out.

Keys align with InboxEventType values.
Roles: reporter/assignee are per-issue relationships; triage/cto are team roles.
"""

DEFAULT_NOTIFICATION_MATRIX: dict[str, dict[str, bool]] = {
    "filed":               {"reporter": True,  "assignee": False, "triage": True,  "cto": True},
    "assigned":            {"reporter": False, "assignee": True,  "triage": False, "cto": False},
    "mention":             {"reporter": True,  "assignee": True,  "triage": True,  "cto": True},
    "comment":             {"reporter": True,  "assignee": True,  "triage": False, "cto": False},
    "status_changed":      {"reporter": True,  "assignee": True,  "triage": False, "cto": False},
    "regression":          {"reporter": True,  "assignee": True,  "triage": True,  "cto": True},
    "fixed":               {"reporter": True,  "assignee": False, "triage": False, "cto": False},
    "verified":            {"reporter": False, "assignee": True,  "triage": False, "cto": False},
    "blocker_filed":       {"reporter": False, "assignee": False, "triage": True,  "cto": True},
    "blocker_cleared":     {"reporter": True,  "assignee": True,  "triage": True,  "cto": True},
    "release_gate":        {"reporter": False, "assignee": False, "triage": True,  "cto": True},
    "environment_changed": {"reporter": True,  "assignee": True,  "triage": False, "cto": False},
    "release_changed":     {"reporter": True,  "assignee": True,  "triage": False, "cto": False},
    "attachment_added":    {"reporter": True,  "assignee": True,  "triage": False, "cto": False},
    "severity_changed":    {"reporter": True,  "assignee": True,  "triage": True,  "cto": False},
}
