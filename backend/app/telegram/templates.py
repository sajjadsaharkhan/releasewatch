"""Telegram notification message templates (HTML parse mode).

Keys align with InboxEventType values so inbox_service can dispatch by event
key.  Dynamic fields are filled in by the sender:
  issue_number, title, issue_url, comment_url, actor, actor_url, priority,
  excerpt, project_name, release_name, release_deadline,
  old_status/new_status, old_environment/new_environment, old_release/new_release,
  old_priority/new_priority, version, gate_status, approver, blocker, note,
  cancel_reason (support_cancelled)
"""

MESSAGE_TEMPLATES: dict[str, str] = {
    # Slice 09 — release-only notices (no item): release_name, release_url,
    # project_name, release_deadline, actor, moved_count.
    "release_shipped": (
        "🚀 <b>Shipped: <a href=\"{release_url}\">{release_name}</a></b>\n"
        "📦 <b>{project_name}</b>\n"
        "\n"
        "Unfinished items moved to the backlog: <b>{moved_count}</b>\n"
        "\n"
        "<i>Shipped by {actor}</i>"
    ),
    "release_overdue": (
        "⏰ <b>Release overdue: <a href=\"{release_url}\">{release_name}</a></b>\n"
        "📦 <b>{project_name}</b>\n"
        "\n"
        "Target ship date <b>{release_deadline}</b> has passed and it hasn't shipped."
    ),
    "filed": (
        "🐛 <b>New issue filed!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "Priority: <code>{priority}</code>"
    ),
    # ``filed`` for a support-sourced item (slice 05) — same audience, Support copy.
    "support_report_filed": (
        "🎧 <b>New support report in {project_name}</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "\n"
        "<i>Reported by <a href=\"{actor_url}\">{actor}</a></i>"
    ),
    # Slice 06 — to the triage lead (§13).
    "needs_info_replied": (
        "↩️ <b>Reporter replied — back in your triage queue</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a>:</i> \"{excerpt}\""
    ),
    "moved_into_project": (
        "📥 <b>Moved into your triage queue</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📤 From: <b>{old_project}</b>\n"
        "📥 To:      <b>{new_project}</b>\n"
        "\n"
        "<i>Moved by <a href=\"{actor_url}\">{actor}</a></i>"
    ),
    "recurrence_on_cancelled": (
        "🔂 <b>A cancelled item was reported again</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b>\n"
        "\n"
        "<i>Reported by <a href=\"{actor_url}\">{actor}</a> — it stays cancelled.</i>"
    ),
    # Slice 06 — the only three messages Support receives (§13).
    "support_needs_info": (
        "❓ <b>Your report needs more information</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> asks:</i> \"{excerpt}\"\n"
        "\n"
        "<a href=\"{issue_url}\">Reply on the report →</a>"
    ),
    "support_cancelled": (
        "🚫 <b>Your report was closed without a fix</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "\n"
        "Reason: <b>{cancel_reason}</b>"
    ),
    # support_cancelled for a report merged as a duplicate — not a dead end.
    "support_merged": (
        "🔗 <b>Your report was merged into another report</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "\n"
        "It's the same problem as <a href=\"{merged_into_url}\">{merged_into_key}</a>. "
        "You'll hear from us when that one is fixed."
    ),
    "support_done": (
        "✅ <b>Your report is fixed</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "\n"
        "<i>You can let the customer know.</i>"
    ),
    "assigned": (
        "👋 <b>You've been assigned!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "Priority: <code>{priority}</code>\n"
        "\n"
        "<i>Time to shine ⭐ — assigned by <a href=\"{actor_url}\">{actor}</a></i>"
    ),
    "comment": (
        "💬 <b>New comment on your issue</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a>:</i> \"{excerpt}\"\n"
        "\n"
        "<a href=\"{comment_url}\">Jump to comment →</a>"
    ),
    "mention": (
        "📣 <b>Psst — you were mentioned!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> said:</i> \"{excerpt}\"\n"
        "\n"
        "<a href=\"{comment_url}\">View mention →</a>"
    ),
    "reaction": (
        "{emoji} <b>Someone reacted to a comment</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> reacted {emoji} to:</i> \"{excerpt}\"\n"
        "\n"
        "<a href=\"{comment_url}\">Jump to comment →</a>"
    ),
    "status_changed": (
        "⚡️ <b>Status just moved!</b>\n"
        "🐛 <a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "🗂 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "📤 From: <code>{old_status}</code>\n"
        "📥 To:      <code>{new_status}</code>\n"
        "\n"
        "🧑‍💻 Moved by <a href=\"{actor_url}\">{actor}</a>"
    ),
    # Slice 10 — to the queue owner / assignee.
    "queue_changed": (
        "📌 <b>Your queue changed</b>\n"
        "<a href=\"{actor_url}\">{actor}</a> {queue_action} "
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "Position: <code>{old_index}</code> → <code>{new_index}</code>\n"
        "\n"
        "<a href=\"{queue_url}\">Open My Work →</a>"
    ),
    "due_soon": (
        "⏳ <b>Due within 24 hours</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b>\n"
        "Due: <b>{due_date}</b>"
    ),
    "overdue": (
        "⏰ <b>Overdue</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b>\n"
        "Was due: <b>{due_date}</b>"
    ),
    "item_returned": (
        "↩️ <b>Back to you: {return_reason}</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<blockquote>{excerpt}</blockquote>\n"
        "\n"
        "<i>Sent back by <a href=\"{actor_url}\">{actor}</a> — it's in To do.</i> "
        "<a href=\"{comment_url}\">Read the comment →</a>"
    ),
    "regression": (
        "🔁 <b>Regression detected!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "Priority: <code>{priority}</code>\n"
        "\n"
        "<i>This one came back from the dead 👻</i>"
    ),
    "fixed": (
        "🛠 <b>Fix ready for verification!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> says it's done — QA, your turn! 🔍</i>"
    ),
    "verified": (
        "🎉 <b>Fix verified!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> gave it the green light ✅</i>"
    ),
    "blocker_filed": (
        "🚨 <b>RELEASE BLOCKER FILED!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "Priority: <code>{priority}</code>\n"
        "⏰ <b>Deadline:</b> {release_deadline}\n"
        "\n"
        "<i>Filed by <a href=\"{actor_url}\">{actor}</a> — all hands on deck! 🚒</i>"
    ),
    "blocker_cleared": (
        "✅ <b>Blocker cleared!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> cleared the path — release is unblocked 🚀</i>"
    ),
    "environment_changed": (
        "🌍 <b>Environment changed</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "📤 From: <code>{old_environment}</code>\n"
        "📥 To:      <code>{new_environment}</code>\n"
        "\n"
        "<i>Updated by <a href=\"{actor_url}\">{actor}</a></i>"
    ),
    "project_changed": (
        "📁 <b>Issue moved to a different project</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "\n"
        "📤 From: <b>{old_project}</b>\n"
        "📥 To:      <b>{new_project}</b>\n"
        "\n"
        "<i>Moved by <a href=\"{actor_url}\">{actor}</a></i>"
    ),
    "release_changed": (
        "📦 <b>Issue moved to a different release</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📁 <b>{project_name}</b>\n"
        "\n"
        "📤 From: <code>{old_release}</code>\n"
        "📥 To:      <code>{new_release}</code>\n"
        "\n"
        "<i>Moved by <a href=\"{actor_url}\">{actor}</a></i>"
    ),
    "attachment_added": (
        "📎 <b>New attachment added</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> attached a file</i>"
    ),
    "priority_changed": (
        "🔥 <b>Priority just changed!</b>\n"
        "🐛 <a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "🗂 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "📤 From: <code>{old_priority}</code>\n"
        "📥 To:      <code>{new_priority}</code>\n"
        "\n"
        "⚠️ Updated by <a href=\"{actor_url}\">{actor}</a>"
    ),
    "release_gate": (
        "🚀 <b>Release gate update</b> — <code>{version}</code>\n"
        "📦 <b>{project_name}</b>\n"
        "Gate: <code>{gate_status}</code>\n"
        "\n"
        "<i>Updated by <a href=\"{actor_url}\">{actor}</a></i>"
    ),
    "release_approved": (
        "🥳 <b>Release approved!</b> — <code>{version}</code>\n"
        "📦 <b>{project_name}</b>\n"
        "\n"
        "<i>Approved by {approver}</i> 🎉\n"
        "{note}"
    ),
    "release_blocked": (
        "🚫 <b>Release blocked!</b> — <code>{version}</code>\n"
        "📦 <b>{project_name}</b>\n"
        "\n"
        "<i>Blocked by {blocker}</i>\n"
        "Reason: {note}"
    ),
}
