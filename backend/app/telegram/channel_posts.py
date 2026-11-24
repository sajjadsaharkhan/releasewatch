"""Rendering of Support channel posts (slice 21, FR-71) — HTML parse mode.

Pure: a stored ``support_channel_posts`` row in, the message text out. Titles
and free text are HTML-escaped; Persian and English pass through as written.
"""

import html
from typing import Any

#: The longest reason or comment shown in a post.
_MAX_TEXT = 500

_STATUS_EMOJI = {
    "verified": "🟢", "done": "🟢", "needs_info": "❓", "cancelled": "🔴",
    "rejected": "🔴", "blocked": "⛔",
}


def status_label(value: str | None) -> str:
    if not value:
        return "—"
    return {"todo": "To do"}.get(value, value.replace("_", " ").capitalize())


def _esc(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def _clip(text: str | None) -> str:
    text = (text or "").strip()
    return text if len(text) <= _MAX_TEXT else text[: _MAX_TEXT - 1].rstrip() + "…"


def _reporter(payload: dict) -> str | None:
    reporter = payload.get("reporter") or {}
    if reporter.get("username"):
        return "@" + reporter["username"].lstrip("@")
    return reporter.get("name")


def _head(emoji: str, payload: dict) -> str:
    return f"{emoji} <b>{_esc(payload['key'])} · {_esc(payload['title'])}</b>"


def _foot(payload: dict) -> list[str]:
    lines = []
    reporter = _reporter(payload)
    if reporter:
        lines.append(f"Reporter: {_esc(reporter)}")
    lines.append(_esc(payload["url"]))
    return lines


def render(kind: str, first_status: str | None, last_status: str | None, payload: dict) -> str:
    """The message text for one outbox row."""
    project = _esc(payload.get("project_name"))
    if kind == "batch":
        items = payload.get("items") or []
        # A ship also sends the unfinished items to the backlog: they are listed,
        # but only what reached Done is counted as released.
        delivered = [i for i in items if i.get("to") == "done"]
        backlog = [i for i in items if i.get("to") != "done"]

        def line(item: dict) -> str:
            return (
                f"• <a href=\"{_esc(item['url'])}\">{_esc(item['key'])}</a> "
                f"{_esc(item['title'])}"
                f" ({status_label(item.get('from'))} → {status_label(item.get('to'))})"
            )

        title = _esc(payload.get("title"))
        if delivered:
            noun = "item" if len(delivered) == 1 else "items"
            title = f"{title} · {len(delivered)} {noun}"
        lines = [f"🚀 <b>{title}</b>", f"Project: {project}", *(line(i) for i in delivered)]
        if backlog:
            lines.append(f"Back to the backlog · {len(backlog)}")
            lines.extend(line(i) for i in backlog)
        return "\n".join(lines)

    text = _clip(payload.get("text"))
    if kind == "new_report":
        lines = [_head("🆕", payload), f"Project: {project} · New report"]
    elif kind == "status":
        lines = [
            _head(_STATUS_EMOJI.get(last_status or "", "🔵"), payload),
            f"Project: {project} · {status_label(first_status)} → {status_label(last_status)}",
        ]
        if text:
            label = (
                "Problem on production" if first_status == "done" and last_status == "rejected"
                else "Reason"
            )
            lines.append(f"{label}: {_esc(text)}")
    elif kind == "return_requested":
        lines = [
            _head("↩️", payload), f"Project: {project} · Return requested — the problem is back",
        ]
        if text:
            lines.append(f"Comment: {_esc(text)}")
    elif kind == "return_confirmed":
        lines = [
            _head("↩️", payload),
            f"Project: {project} · Return confirmed — going back for a fix",
        ]
    elif kind == "return_dismissed":
        lines = [_head("✋", payload), f"Project: {project} · Return dismissed — stays Done"]
        if text:
            lines.append(f"Reason: {_esc(text)}")
    else:
        raise ValueError(f"Unknown channel post kind: {kind!r}")
    return "\n".join(lines + _foot(payload))
