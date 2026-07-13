"""Telegram notification message templates (HTML parse mode).

Keys align with InboxEventType values so inbox_service can dispatch by event
key.  Dynamic fields are filled in by the sender:
  issue_number, title, issue_url, comment_url, actor, actor_url, severity,
  excerpt, project_name, release_name, release_deadline,
  old_status/new_status, old_environment/new_environment, old_release/new_release,
  old_severity/new_severity, version, gate_status, approver, blocker, note
"""

MESSAGE_TEMPLATES: dict[str, str] = {
    "filed": (
        "🐛 <b>New issue filed!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "Severity: <code>{severity}</code>"
    ),
    "assigned": (
        "👋 <b>You've been assigned!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "Severity: <code>{severity}</code>\n"
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
    "regression": (
        "🔁 <b>Regression detected!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "Severity: <code>{severity}</code>\n"
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
        "Severity: <code>{severity}</code>\n"
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
    "severity_changed": (
        "🔥 <b>Severity just changed!</b>\n"
        "🐛 <a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "🗂 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "📤 From: <code>{old_severity}</code>\n"
        "📥 To:      <code>{new_severity}</code>\n"
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
