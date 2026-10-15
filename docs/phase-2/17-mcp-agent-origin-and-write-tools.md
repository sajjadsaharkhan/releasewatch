# 17 — Agent Origin and MCP Write Tools

> **Depends on:** 16 · **PRD:** [prd-mcp.md](prd-mcp.md) M1, M3, M4, FR-M10–FR-M24, FR-M29, FR-M30, FR-M32, BR-M01, BR-M05, BR-M06, BR-M08–M13, BR-M15, BR-M16, BR-M19, AC-M01, AC-M09–M11, AC-M15–M26, AC-M34, AC-M35; Appendix A.3–A.6, A.8 · **Writing:** [agent-writing-standard.md](agent-writing-standard.md) §9 · **Parent PRD:** [v3](prd-v2.md) FR-04, FR-13–16, FR-17, FR-23, FR-27, FR-42, BR-22, BR-23, BR-62

## Problem Statement

An agent can now read work, but it cannot record what it finds. When a developer's agent spots a bug or a piece of technical debt outside the current task, the developer must write the report by hand, so it is usually not written. The agent also cannot add the PR link, a log, or missing reproduction data to the item it works on. And when an agent does produce content, nothing in Releasewatch can tell it apart from content a person wrote.

There is a related gap in the timeline today: changes to cURL and to four of the five environment fields are saved with no timeline event, so their history is lost.

## Solution

- Every item, timeline entry, and attachment created through MCP records the token that created it. The mark is set once and never changes. The web app shows an **Agent** badge next to the owner's name on that content, and the triage queue, backlog, and Technical debt page can filter by origin.
- The agent can upload files through presigned URLs, file a **bug** (into triage) or a **technical-debt task** (into the backlog), add an **internal note**, **attach** a file, **fill** an empty reproduction steps, cURL, or environment field, and **report a recurrence**.
- Every filing first checks for duplicates across every visible project. When candidates exist, nothing is filed unless the agent passes `file_anyway`.
- The server enforces the size checks of the writing standard.
- cURL and every environment field now leave a timeline event when they change, from the UI or from an agent.
- No tool changes status, container, triage outcome, release state, labels, flags, or a queue.

## User Stories

### Filing
1. As a developer, I want my agent to file a bug with title, description, reproduction steps, cURL, environment, and attachments, so that a problem it found is recorded with its evidence. (FR-M11)
2. As a triage lead, I want an agent-filed bug to arrive in New, with no container, source Internal, and no priority, in my triage queue, and to be notified as for any bug. (FR-M11, BR-M08, AC-M09)
3. As a developer, I want my agent to file a technical-debt task that lands in the backlog as To do, category Default, flag set, priority Medium unless I confirmed another, with no cycle. (FR-M12, BR-M09, BR-M10, AC-M10)
4. As a developer, I want an agent-filed item to have no assignee unless I asked for one, so that nobody's queue changes without my say. (FR-M14, BR-M11)
5. As a developer, I want an assignee I asked for to put the item in that person's queue by the default rule, as in the UI. (BR-M11)
6. As a developer, I want every filing to check for duplicates first, across every project I can see, so that my agent does not create a second copy. (FR-M13, BR-M16, AC-M12)
7. As a developer, I want a filing with candidates to file nothing and return the candidates, so that I decide. (FR-M13, AC-M11)
8. As a developer, I want `file_anyway` to file the item after I have seen the candidates. (FR-M13, AC-M11)
9. As a developer, I want the duplicate check to work with Jev off, with local candidates and no verdicts. (FR-M23, BR-M17)
10. As a developer, I want a problem in a Done item to become a new bug that refers to it, so that triage sends the Done item back. (FR-M15)

### Uploads and attachments
11. As a developer, I want my agent to upload a log, screenshot, or script through a presigned URL with its own shell, so that the API never receives the bytes. (FR-M10)
12. As a developer, I want an unused upload to expire after an hour. (FR-M10)
13. As a developer, I want to pass upload ids when filing, so that the new item has its attachments from the start. (AC-M15)
14. As a developer, I want an upload id of another user, or one already used, refused. (AC-M16)
15. As a developer, I want my agent to attach an uploaded file to an existing item. (FR-M17)
16. As a Support user, I want to see attachments an agent added to my report, marked as agent content. (FR-M17, AC-M21)

### Existing items
17. As a developer, I want my agent to add an internal note, for example with the PR link, so that the item records what was done. (FR-M16)
18. As a Support user, I never want to see an agent's note. (BR-M06, AC-M20)
19. As a developer, I want my agent to fill reproduction steps, cURL, or environment only when the field is empty and the bug is not Done or Cancelled. (FR-M18, BR-M13, AC-M22–M24)
20. As a developer, I want each fill recorded on the timeline with the Agent badge. (FR-M18, AC-M22)
21. As a developer, I want my agent to report a recurrence on an open or Cancelled bug when I confirm it is the same problem, with the same effects as from the UI. (FR-M19, BR-M15, AC-M25)
22. As a developer, I want a recurrence on a Done item refused. (FR-M19, AC-M24)
23. As anyone, I want no tool to change the description of an item the agent did not file. (FR-M20, AC-M26)

### Writing checks
24. As a triage lead, I want agent titles between 15 and 90 characters. (BR-M19, AC-M17)
25. As a triage lead, I want agent descriptions of 12,000 characters or fewer, with the hint to move detail to attachments. (BR-M19, AC-M18)
26. As a developer, I want agent notes of 3,000 characters or fewer. (BR-M19, AC-M19)

### Origin
27. As anyone on the tech team, I want an Agent badge next to the owner's name on agent-filed items, agent notes, agent attachments, field fills, and recurrences, so that I know where content came from. (FR-M29)
28. As anyone, I want the badge to show nothing else: no client, device, model, or token name. (FR-M29)
29. As anyone, I want the badge on card hover, not on the card face, so that cards stay quiet. (FR-M29, PRD FR-42)
30. As anyone, I want the badge kept when labels are removed or the item is edited, because it is not a label. (BR-M05, AC-M34)
31. As a triage lead, I want to filter my triage queue by origin (All, Agent, People). (FR-M30)
32. As a PM, I want to filter the backlog and the Technical debt page by origin, so that I can review or clean up agent work. (FR-M30, AC-M35)
33. As an Admin, I want every agent row to point to the token that created it, so that a leaked token's output can be found. (BR-M24)
34. As anyone, I want a change to cURL or to any environment field recorded on the timeline, from the UI or an agent. (PRD Appendix A.5)

### Boundaries
35. As a developer, I want no tool that changes status, container, triage outcome, release state, labels, flags, assignee or priority after filing, or a queue. (BR-M01, AC-M01)

## Implementation Decisions

### Schema

One Alembic revision with a working downgrade:

```
issues.via_mcp_token_id             int NULL FK mcp_tokens(id) ON DELETE RESTRICT
issue_timeline.via_mcp_token_id     int NULL FK mcp_tokens(id) ON DELETE RESTRICT
issue_attachments.via_mcp_token_id  int NULL FK mcp_tokens(id) ON DELETE RESTRICT
partial index on issues (project_id) WHERE via_mcp_token_id IS NOT NULL
```

- Agent content = `via_mcp_token_id IS NOT NULL`. Responses expose only `via_agent: bool`, never the token.
- No request schema accepts the column. There is no database trigger; immutability is a property of the writers below and is covered by a test.
- `issue_recurrences` needs no column: its timeline entry carries the mark.

### Agent context

- A request-scoped context variable holds the current token id, default none. Only the MCP auth dependency sets it. Celery tasks and the Telegram bot never set it.
- Three writers read it and stamp `via_mcp_token_id`:
  - `TimelineService.create_event` — already the only creator of timeline rows.
  - `IssueService.create` — already the only creator of items (Support goes through it).
  - **`AttachmentService.add`** — new. Today attachments are created in four places (item creation, merge, and two attachment endpoints). Move all four onto this one service method; it also enqueues the existing attachment validation. Behavior of the four callers does not change.
- Side effects of the same agent action (for example the `subscribed` event on filing) are stamped too. That is correct: they happened through the agent.

### Timeline events for cURL and environment

- New `TimelineEventType.curl_changed`, with `meta: {}` (the value can be long and is on the item).
- `environment_changed` now covers all five environment fields (`environment_name`, `environment_browser`, `environment_os`, `environment_build_hash`, `environment_staging_url`), with `meta.fields` listing the changed field names and `from`/`to` per field. The existing `environment_changed` inbox trigger keeps firing only when `environment_name` changes, so notifications do not change.
- `IssueService.update` emits these instead of setting the five passthrough fields silently. This applies to the UI as well as to agents. The frontend timeline renders both events.

### Uploads

- `rw_upload_prepare(file_name, mime_type, size)` uses the existing presign logic (single part; multipart above the existing threshold) and stores a pending upload in Redis under a random `upload_id`: owner, S3 key, file name, MIME type, size, attachment type inferred from MIME type. TTL one hour.
- An upload is consumed by `rw_file_bug`, `rw_file_tech_debt`, or `rw_attach`, only by its owner, only once (`unknown_upload` otherwise). Consumption deletes the Redis key and calls `AttachmentService.add`.
- File names follow the writing standard (A4), but the server does not enforce names.

### Filing tools

`rw_file_bug(project, title, description?, reproduction_steps?, curl?, environment?, upload_ids?, assignee?, file_anyway=false)`
`rw_file_tech_debt(project, title, description?, priority?, upload_ids?, assignee?, file_anyway=false)`

1. Validate the writing checks: title 15–90 characters (`title_length`), description 12,000 characters or fewer (`description_too_long`, message: "Move logs, scripts, and long results to attachments."), every upload id valid (`unknown_upload`).
2. Run the duplicate check with the same function as `rw_find_similar` (slice 16): every visible project, any type, not Cancelled. If it returns items and `file_anyway` is false, return `duplicates_found` with the candidates and file nothing.
3. Create through `IssueService.create` with fixed placement: a bug with no container, source Internal, no priority; a task in the backlog, category Default, `is_tech_debt = true`, priority as given or Medium. The tools accept no other placement, status, label, or flag.
4. Attach the uploads.

`reproduction_steps` uses the item's existing shape: an ordered list of `{description, expected_result, actual_result}`. `environment` is `{name?, browser?, os?, build_hash?, staging_url?}`; `name` must be a known environment name.

`assignee` is a username of an assignable user; the existing `ensure_assignable` rule applies.

### Tools on existing items

| Tool | Rule | Service |
|---|---|---|
| `rw_add_note(key, body)` | Always internal. 3,000 characters or fewer (`note_too_long`). | `TimelineService.create_event(comment, is_internal=True)` and the existing comment side effects (mentions, search indexing) |
| `rw_attach(key, upload_id)` | Item-level. | `AttachmentService.add` |
| `rw_fill_field(key, field, value)` | `field ∈ {reproduction_steps, curl, environment}`. Bugs only. The item must not be Done or Cancelled (`item_closed`). The field must be empty (`field_not_empty`); for `environment`, every sub-field given must be empty. | `IssueService.update` |
| `rw_report_recurrence(key, comment)` | Open or Cancelled bugs. Done → `recurrence_not_allowed`. | `RecurrenceService.report` unchanged |

No tool accepts a description for an existing item.

### Read tools after this slice

`via_agent` in `rw_get_item`, `rw_triage_queue`, and `rw_tech_debt` now reflects the columns (it was always false in slice 16).

### Web app

- `IssueResponse`, the timeline event response, and the attachment response gain `via_agent`.
- List endpoints for the triage queue, the backlog, and the Technical debt page accept `origin ∈ {agent, people}`; absent means all.
- UI: an **Agent** badge next to the author name on the item header, timeline entries, and attachments; in triage, backlog, and Technical debt rows; and in card hover (never on the card face). An **Origin** filter (All / Agent / People) on the three pages. Follow `docs/design.md`; add the badge to its component inventory.
- No UI action changes `via_agent`.

### Errors

As PRD Appendix A.8: `duplicates_found`, `title_length`, `description_too_long`, `note_too_long`, `unknown_upload`, `field_not_empty`, `item_closed`, `recurrence_not_allowed`, `not_found`, `not_assignable`.

## Testing Decisions

- Seams: `/mcp` through the in-process MCP client for every tool; `/api/v1` for `via_agent` in responses and the origin filters; FakeS3 (slice 16) to stand in for the agent's upload (the test writes the object at the presigned key).
- **Boundary test** (`test_ac_m01_*`): list the server's tools and assert the exact set of 16 names (9 read, 7 write; slice 18 adds two). For each write tool, call it on a fixture item and assert, through `/api/v1`, that status, container, labels, flags, assignee, priority, and the owner's queue are unchanged except where the tool's rule says otherwise (assignee and priority at filing).
- **Mark test:** after each write tool, every new timeline entry, attachment, and item visible through `/api/v1` has `via_agent = true`, and the same actions through `/api/v1` give `via_agent = false`.
- Prior art: issue creation tests of 03/06, recurrence tests of 07, backlog and tech-debt tests of 08, attachment presign test, suggestion tests of 14 (fake Jev, Jev disabled).
- Tests named after the criteria: `test_ac_m09_*`, `test_ac_m10_*`, `test_ac_m11_*`, `test_ac_m15_*`, `test_ac_m16_*` (other user's, used twice), `test_ac_m17_*`, `test_ac_m18_*`, `test_ac_m19_*`, `test_ac_m20_*`, `test_ac_m21_*`, `test_ac_m22_*`, `test_ac_m23_*`, `test_ac_m24_*`, `test_ac_m25_*`, `test_ac_m26_*`, `test_ac_m34_*`, `test_ac_m35_*`.
- Timeline events: a cURL change through `/api/v1` adds `curl_changed`; a browser change adds `environment_changed` with `meta.fields = ["environment_browser"]` and sends no inbox notice; an `environment_name` change still sends one.
- The four attachment callers keep their existing tests green after moving onto `AttachmentService.add`.
- E2E: one scenario — an item filed through the MCP fixture shows the Agent badge on the item page, and the backlog origin filter lists it. Check both themes with Playwright MCP.

## Out of Scope

- Editing or deleting agent content, and `you_can_edit` (slice 18).
- Prompts and the writing-standard resource (slice 18).
- Enforcing writing rules that need judgment (sentence length, voice, evidence quality).
- Labels, flags, placement, status, triage, or queue operations through MCP.
- Any limit on how much an agent can file.

## Further Notes

- Add to `CONTEXT.md`: **agent content**, **Agent badge**, **origin filter**, **file anyway**, **pending upload** (with _Avoid_: AI label, bot, source — `source` already means internal/support).
- `source` (internal | support) and the agent mark are independent: an agent-filed bug is source Internal and agent content.
