# 21 — Support channel (per-project Telegram topic)

> **Depends on:** 20 · **PRD:** [v3.1](prd-v2.md) §8.1, §8.11, FR-70, FR-71, BR-31, BR-72, §13; AC-94–AC-98
> **One session.**

## Problem Statement

Support's notices go to **subscribers** only: the reporter, recurrence reporters, and requesters (`support_needs_info`, `support_cancelled`, `support_done`, and the Support `status_changed` notice since 2026-10-14). Support works as a team. When the reporter is away, nobody else on the team hears that a report changed, and the customer waits. The team already runs a Telegram supergroup with one topic per area.

## Solution

- Each project can have a **Support channel**: a Telegram chat ID, an optional topic (thread) ID, and an enabled flag. CTO and Admin set it in project settings, with **Send test message**.
- For a project with an enabled channel, the bot posts about the project's **support-sourced items**:
  - a new report;
  - every status change;
  - every return-request event (requested, confirmed, dismissed).
- **No spam:**
  - one item's changes within 60 s become one post showing first → final status;
  - On production on several items, and a ship, are one post per project;
  - each event is posted once.
- The private Telegram notices to subscribers don't change.
- **Deliberate exception to "everything goes through `fan_out`"** (00-README → Notifications). An inbox row belongs to a user, and a chat topic is not a user. Channel posts get their own small outbox, `support_channel_posts`. The outbox reuses the Telegram client, the bot token and proxy settings, and the retry/backoff of `tasks/notifications.py`. Nothing else may send to a chat this way.

---

## User Stories

1. As a CTO, I want to point a project at our Support supergroup topic and test it, so that I know posts will arrive.
2. As a Support user, I want every new report and every status change of my project's support reports in our topic, so that anyone on shift can answer the customer.
3. As a Support user, I want rapid changes and bulk deploys summarized in one post, so that the topic stays readable.
4. As anyone, I want internal notes never to appear in the group.
5. As a developer, I want a Telegram outage never to block or undo a status change.

## Implementation Decisions

### Settings

- New columns on `projects`: `support_chat_id BIGINT NULL`, `support_thread_id INT NULL`, `support_channel_enabled BOOL NOT NULL DEFAULT false`, and `support_channel_tested_at TIMESTAMPTZ NULL`.
- Policy action `manage_support_channel`: CTO and Admin, the same as `manage_templates`.
- `PUT /projects/{id}/support-channel {chat_id, thread_id?, enabled}`. Enabling requires a successful test since the last change of `chat_id`/`thread_id` (409 `support_channel_untested`).
- `POST /projects/{id}/support-channel/test` sends "Releasewatch test message for <project>" to the chat and topic (`message_thread_id`). It returns `{ok, error?}` with Telegram's description, for example "chat not found" or "bot is not a member", and stamps `support_channel_tested_at` on success.
- `TelegramClient.send_message` gains an optional `message_thread_id`.

### Events → posts

- One writer: `SupportChannelService.record(db, issue, kind, meta, batch_id=None)`. It is called from:
  - `SupportService` on report submission (`new_report`);
  - `IssueService.transition` on every status change of a `source = support` item (`status`), with `reason` and, for Needs info / Cancelled / Reject-from-Done, the public reason comment's text;
  - `ReturnRequestService` (`return_requested`, `return_confirmed`, `return_dismissed`, with the comment);
  - `ReleaseService.ship` and `bulk-production` pass a `batch_id`, the one slice 19 writes for On production, and a new one per ship.
- `record` does nothing unless the project's channel is enabled. It never reads internal notes. The reason text comes from the public comment the action wrote. BR-31 is enforced by construction, and a test asserts it.
- Outbox table `support_channel_posts`:
  - `id`, `project_id`, `issue_id NULL`, `batch_id NULL`, `kind`, `first_status`, `last_status`, `payload JSONB`;
  - `status` (`pending | sent | failed`), `not_before TIMESTAMPTZ`, `attempts`, `last_error`, `created_at`, `sent_at`.

### Grouping (no spam)

- **Per item:** a `status` event for an item with a `pending` post whose `not_before` is still in the future updates that row. `last_status` and the payload change, and `first_status` stays. No new row is created. Otherwise a new row is created with `not_before = now + 60 s`.
- **Batch:** events with a `batch_id` collapse into one row per `(project_id, batch_id)`. The row lists the item keys and titles, and is sent with `not_before = now + 5 s`. Each item of the batch does not also get its own row.
- `new_report` and return-request events are sent at once (`not_before = now`) and are never merged into other posts. A `status` change of the same item within the next 60 s still merges into its own per-item row.
- A per-item post whose `first_status == last_status` after merging (moved and moved back) is dropped, not sent.
- Celery task `send_support_channel_posts`, every 15 s by beat, sends rows that are due, oldest first. Failures retry with the same backoff as `flush_telegram_notifications`, stop after 8 attempts (status `failed`), and are logged. The action that created the event never waits for the post.

### Message format (HTML, as the existing templates)

```
🟢 BUG-42 · Login fails on iOS 17
Project: Mobile · To review → Verified
Reporter: @sara
https://rw.example/#/issue/bug-42
```

- Needs info, Cancelled and dismissal posts add the reason line. A Reject-from-Done post adds the reason as "Problem on production: …".
- Batch posts are titled "On production · 3 items" or "Released 2.4.0 · 5 items", followed by one line per item.
- The reporter is mentioned as `@telegram_username` when their `telegram_integrations` row has one, else by display name.
- Persian and English text pass through as written; titles are HTML-escaped.

### Frontend

- **Project settings → Support channel** (CTO/Admin): chat ID, topic ID, **Send test message** with an inline result, and the Enabled switch (disabled until a passing test). A help line says the bot must be added to the group, and how to read a topic ID from a message link.
- Read-only state for other roles: hidden.
- Check both themes.

## Testing Decisions

Telegram is recorded, not sent (01 harness). Time is frozen and advanced in tests.

- `test_ac_94_*`: with an enabled channel, a support report → one post to the configured chat and topic, naming the project, key and reporter.
- `test_ac_95_*`: To review → In review → Verified within 60 s → one post "To review → Verified". The same moves 2 minutes apart → two posts.
- A move there and back within 60 s → no post.
- `test_ac_81_*` (with 19): On production for three support items → one batch post listing three keys. A ship with four Verified support items → one post.
- `test_ac_96_*`: channel disabled, or no channel → no post; subscriber DMs still sent.
- `test_ac_97_*`: the recorded client raises → the status change still commits, the row is `failed` after the retries, and nothing is raised to the caller.
- `test_ac_98_*`: an internal note on the item never appears in any post payload, Reject or Needs info included.
- Internal (non-support) items never produce posts.
- Enabling without a passing test → 409; changing `chat_id` clears the test.
- Policy: a Developer can't read or change the channel (403).

## Out of Scope

- Two-way use: replying in the group does not comment on the item.
- Daily digests and reminders.
- Channels for internal items.

## Changes to Later Specs

- **00-README → Notifications:** add the Support channel outbox as the one named exception to "nothing sends Telegram directly".
- **CONTEXT.md:** add **Support channel** and **Channel post**.

## Prompt

```
Implement docs/phase-2/21-support-channel.md.
Read docs/phase-2/00-README.md, then 21, then PRD v3.1 §8.11, FR-70/71, BR-72.
Slices 19 and 20 are committed. Read app/telegram/ (client, sender), tasks/notifications.py
and tasks/celery_app.py before adding the outbox; reuse the token, proxy and backoff code.
Work test-first at the API seam with frozen time. Run `make test` and `make lint`, check the
settings screen in both themes, and update CONTEXT.md and the 00-README notification note.
```
