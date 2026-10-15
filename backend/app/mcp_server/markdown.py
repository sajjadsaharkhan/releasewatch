"""Markdown renderings of the read tools' answers (slice 16).

Each function takes the exact dict a tool returns as structured content and
renders it for clients that show only text. Nothing here reads the database
or decides anything: if a fact is not in the dict, it is not in the text.
``item`` is also the body of the ``rw://item/{key}`` resource.
"""

from datetime import date, datetime

_STATUS_LABELS = {"todo": "To do"}


def _status(value: str | None) -> str:
    if value is None:
        return "—"
    return _STATUS_LABELS.get(value, value.replace("_", " ").capitalize())


def _when(value: datetime | date | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M UTC")
    return value.isoformat()


def _who(person: dict | None) -> str:
    return f"@{person['username']}" if person else "system"


def _size(size: int | None) -> str:
    if size is None:
        return "size unknown"
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


def _quote(text: str | None) -> str:
    return "\n".join(f"> {line}" for line in (text or "").splitlines()) or ">"


def _line(row: dict) -> str:
    """One item in a list: key, title, then what changes the decision."""
    parts = [f"**{row['key']}** {row['title']}", _status(row["status"])]
    if row.get("priority"):
        parts.append(row["priority"])
    if row.get("project"):
        parts.append(row["project"]["name"])
    if row.get("assignee"):
        parts.append(_who(row["assignee"]))
    if row.get("is_release_blocker"):
        parts.append("release blocker")
    if row.get("due_date"):
        parts.append(f"due {_when(row['due_date'])}")
    return " · ".join(parts)


# ── Tools ─────────────────────────────────────────────────────────────────────


def queue(data: dict) -> str:
    if not data["items"]:
        return "Your queue is empty."
    lines = ["# Your queue", ""]
    for n, e in enumerate(data["items"], start=1):
        extra = []
        if e["pinned"]:
            extra.append("pinned")
        if e["cycle_number"] and e["cycle_number"] > 1:
            extra.append(f"cycle {e['cycle_number']}")
        lines.append(f"{n}. {_line(e)}" + (f" · {' · '.join(extra)}" if extra else ""))
    return "\n".join(lines)


def _event(e: dict) -> str:
    head = f"- **{_who(e['author'])}** · {_when(e['at'])} · "
    if e["type"] == "comment":
        kind = "internal note" if e["internal"] else "comment"
        quoted = _quote(e["body"]).splitlines()
        return f"{head}{kind}\n\n" + "\n".join(f"  {line}" for line in quoted)
    meta = e["meta"]
    detail = ""
    if "from" in meta or "to" in meta:
        detail = f": {_status(meta.get('from'))} → {_status(meta.get('to'))}"
    elif meta.get("outcome"):
        detail = f": {meta['outcome']}"
    text = f"{head}{e['type'].replace('_', ' ')}{detail}"
    return text + (f" — {e['body']}" if e["body"] else "")


def item(data: dict) -> str:
    lines = [f"# {data['key']} · {data['title']}", ""]
    facts = [
        f"**Status:** {_status(data['status'])}",
        f"**Type:** {data['type']}",
        f"**Priority:** {data['priority'] or '—'}",
        f"**Project:** {data['project']['name']} ({data['project']['key']})",
    ]
    lines.append(" · ".join(facts))
    container = data["container"]
    where = (
        f"{'Stream' if container['kind'] == 'stream' else 'Release'} {container['name']}"
        if container else "Backlog (no container)"
    )
    assignee = _who(data["assignee"]) if data["assignee"] else "—"
    lines.append(
        f"**Container:** {where} · **Assignee:** {assignee}"
        f" · **Reporter:** {_who(data['reporter'])} · **Due:** {_when(data['due_date'])}"
    )
    flags = [
        label for label, on in (
            ("release blocker", data["is_release_blocker"]),
            ("technical debt", data["is_tech_debt"]),
            (f"reported ×{data['recurrence_count']}", data["recurrence_count"] > 1),
        ) if on
    ]
    if data["labels"]:
        flags.append("labels: " + ", ".join(data["labels"]))
    if flags:
        lines.append("**Flags:** " + " · ".join(flags))

    if data["reject"]:
        lines += ["", "## Rejected", "", f"Reason: {data['reject']['reason']}."]
        comment = data["reject"]["comment"]
        if comment:
            lines += [
                f"{_who(comment['author'])} wrote on {_when(comment['at'])}:",
                "",
                _quote(comment["body"]),
            ]

    lines += ["", "## Description", "", data["description"] or "_No description._"]
    if data["reproduction_steps"]:
        lines += ["", "## Reproduction steps", ""]
        for step in data["reproduction_steps"]:
            text = f"{step.get('step_order', '-')}. {step.get('description', '')}"
            if step.get("expected_result"):
                text += f" — expected: {step['expected_result']}"
            if step.get("actual_result"):
                text += f" — actual: {step['actual_result']}"
            lines.append(text)
    if data["curl_command"]:
        lines += ["", "## cURL", "", "```sh", data["curl_command"], "```"]
    env = {k: v for k, v in data["environment"].items() if v}
    if env:
        lines += ["", "## Environment", ""]
        lines += [f"- {k.replace('_', ' ')}: {v}" for k, v in env.items()]

    if data["cycles"]:
        lines += ["", "## Cycles", ""]
        for c in data["cycles"]:
            closed = f" · closed {_when(c['closed_at'])}" if c["closed_at"] else ""
            lines.append(
                f"{c['number']}. {c['start_reason']} · {c['container'] or '—'} · started "
                f"{_when(c['started_at'])}{closed}"
            )
    if data["attachments"]:
        lines += ["", "## Attachments", ""]
        for a in data["attachments"]:
            lines.append(
                f"- [{a['id']}] {a['file_name']} ({a['mime_type']}, {_size(a['size'])}) "
                f"by {_who(a['author'])} — read with rw_get_attachment"
            )

    scope = "every event" if data["full_timeline"] else (
        "comments, notes and significant events; full_timeline=true for every event"
    )
    lines += ["", f"## Timeline ({scope})", ""]
    lines += [_event(e) for e in data["timeline"]] or ["_Empty._"]
    return "\n".join(lines)


def attachment(data: dict) -> str:
    head = f"{data['file_name']} ({data['mime_type']}, {_size(data['size'])})"
    if "download_url" not in data:
        return f"{head} — shown as an image."
    return f"{head}\n\nDownload until {_when(data['expires_at'])}:\n{data['download_url']}"


def _hits(rows: list[dict]) -> list[str]:
    out = []
    for r in rows:
        line = f"- {_line(r)}"
        if r["snippet"]:
            line += f"\n  {r['snippet']}"
        out.append(line)
    return out


def search(data: dict) -> str:
    if not data["results"] and not data["less_relevant"]:
        return "No matching items."
    lines = ["# Results", ""] + (_hits(data["results"]) or ["_No close matches._"])
    if data["less_relevant"]:
        lines += ["", "## Less relevant", ""] + _hits(data["less_relevant"])
    return "\n".join(lines)


def similar(data: dict) -> str:
    if not data["items"]:
        return "No similar items."
    head = (
        "# Possible duplicates (judged by Jev)" if data["jev_used"]
        else "# Closest local matches (no verdict — judge them yourself)"
    )
    lines = [head, ""]
    for row in data["items"]:
        verdict = f" · {row['verdict']} ({row['confidence']:.2f})" if row["verdict"] else ""
        lines.append(f"- {_line(row['issue'])}{verdict}")
    return "\n".join(lines)


_MERGE_EFFECTS = {
    "unchanged": "stays as it is",
    "stays_cancelled": "stays cancelled",
    "returns_release_qa": "comes back from release QA",
    "returns_production": "comes back from production",
}


def triage_queue(data: dict) -> str:
    if not data["items"]:
        return f"The triage queue of {data['project']['name']} is empty."
    lines = [f"# Triage queue · {data['project']['name']}", ""]
    for row in data["items"]:
        lines.append(
            f"- **{row['key']}** {row['title']} · {_status(row['status'])} · {row['source']} · "
            f"reported by {_who(row['reporter'])} · ×{row['recurrence_count']}"
        )
        for d in row["possible_duplicates"]:
            effect = _MERGE_EFFECTS.get(d["merge_effect"], d["merge_effect"])
            lines.append(
                f"  - possible duplicate of **{d['key']}** {d['title']} ({_status(d['status'])}, "
                f"{d['confidence']:.2f}); merging: it {effect}"
            )
    return "\n".join(lines)


def board(data: dict) -> str:
    c = data["container"]
    if c["kind"] == "stream":
        lines = [
            f"# {data['project']['name']} · Stream", "", f"Done since {_when(data['done_from'])}.",
        ]
    else:
        progress = "—" if c["progress"] is None else f"{c['progress']:.0%}"
        lines = [
            f"# {data['project']['name']} · Release {c['name']}",
            "",
            f"**Status:** {_status(c['status'])}{' · **Overdue**' if c['is_overdue'] else ''} · "
            f"**Progress:** {progress} · **Target:** {_when(c['target_date'])} · "
            f"**Code freeze:** {_when(c['code_freeze_date'])} · "
            f"**Go/no-go:** {c['go_nogo']['status']}",
        ]
        if c["open_blockers"]:
            lines += ["", "## Open release blockers", ""]
            lines += [f"- {_line(b)}" for b in c["open_blockers"]]
    for col in data["columns"]:
        lines += ["", f"## {_status(col['status'])} ({len(col['items'])})", ""]
        lines += [f"- {_line(i)}" for i in col["items"]]
    if not data["columns"]:
        lines += ["", "_No items._"]
    return "\n".join(lines)


def tech_debt(data: dict) -> str:
    if not data["items"]:
        return "No technical-debt tasks match."
    shown = len(data["items"])
    lines = [f"# Technical debt ({shown} of {data['total']})", ""]
    lines += [f"- {_line(i)}" for i in data["items"]]
    return "\n".join(lines)
