# 16 — MCP Read Tools

> **Depends on:** 15 · **PRD:** [prd-mcp.md](prd-mcp.md) FR-M02–FR-M09, FR-M21–FR-M23, FR-M36 (`rw://item/{key}`), BR-M03, BR-M16, BR-M17, AC-M03, AC-M05–M08, AC-M12–M14; Appendix A.6 (read), A.7, A.8 · **Engine doc:** [prd-search-engine.md](prd-search-engine.md) FR-S01–S04, FR-S08, BR-S03, BR-S06, BR-S20

## Problem Statement

A connected agent can only say who the user is. To help with work it must read it: the developer's queue, an item with its description, reproduction steps, cURL, environment, comments, internal notes, the reject comment, and the screenshots attached to it. Today the developer copies all of this into the agent by hand, and cannot copy images at all. The agent also cannot look at the history of an area, the triage queue, a release, or the technical-debt list before it starts.

## Solution

Eight read tools and one resource, all acting with exactly the token owner's visibility:
- `rw_my_queue` — the personal queue in queue order.
- `rw_get_item` — one item's full context: fields, container, cycles, the reject comment of a Rejected item, attachments, and a timeline that shows comments, notes, and significant events by default, or every event on request.
- `rw_get_attachment` — an image of 5 MB or less as an image the agent can see; any other file as a short-lived download link.
- `rw_search` — the search page of the engine, in one project or across every visible project.
- `rw_find_similar` — duplicate candidates for a draft, across every visible project: Jev verdicts when Jev is on, local candidates without verdicts when it is off.
- `rw_triage_queue` — a project's New and Needs info bugs with possible duplicates.
- `rw_board` — the project's Stream, or one release with its header.
- `rw_tech_debt` — technical-debt tasks with filters.
- Resource `rw://item/{key}` — the default `rw_get_item` context as Markdown.

## User Stories

### Queue and items
1. As a developer, I want my agent to read my queue in the same order I see it (In progress first, then pinned, then the rest), so that "what next" means the same thing to both of us. (FR-M02)
2. As a developer, I want each queue entry to show key, type, title, project, status (including Rejected), priority, pin, cycle number, and due date. (FR-M02)
3. As a developer, I want my agent to read an item by its key (`BUG-42`, `TASK-118`), case-insensitive, so that I can paste what I see in the UI. (FR-M03)
4. As a developer, I want every field I can see, including the full cURL command with headers and the reproduction steps, so that my agent can reproduce the problem. (FR-M03)
5. As a developer, I want the item's container and its kind (Stream or Release). (FR-M03)
6. As a developer, I want comments, internal notes, and the significant events by default, so that the agent's context is not filled with label and due-date changes. (FR-M03, AC-M07)
7. As a developer, I want the full timeline when I ask for it. (FR-M03, AC-M07)
8. As a developer, I want each timeline entry to say who made it, when, and whether an agent made it. (FR-M03)
9. As a developer working on a Rejected item, I want the reject comment and the cycle's start reason, so that my agent starts from what QA found. (FR-M03, AC-M06)
10. As a developer, I want the item's cycles, so that my agent knows how many times the work came back and from where. (FR-M03)
11. As a developer, I want the list of attachments with name, type, size, author, and whether an agent added them. (FR-M03)
12. As a developer, I want my agent to see screenshots of 5 MB or less as images, so that it understands visual bugs. (FR-M04, AC-M05)
13. As a developer, I want larger files and non-images as a download link my agent can fetch with its shell. (FR-M04, AC-M05)
14. As a developer, I want an item I cannot see to be "not found" for my agent too. (BR-M03, AC-M03)
15. As a developer using Claude Code, I want to reference `rw://item/BUG-42` directly in my prompt, so that the context arrives without a tool call. (FR-M36)

### History and duplicates
16. As a developer, I want my agent to search like the search page, including Persian, English, and mixed text, so that it finds earlier work in an area. (FR-M05)
17. As a developer, I want the search limited to one project when I name one, and across every project I can see when I don't. (FR-M05, AC-M08)
18. As a developer, I want less relevant results returned separately, so that the agent weighs them less. (FR-M05)
19. As a developer, I want cancelled items found by search and marked as cancelled, so that "Cannot reproduce" history is visible. (FR-S06)
20. As a developer, I want my agent to check a draft for duplicates across every project I can see, so that the same problem filed under a neighbouring project is found. (FR-M21, AC-M12)
21. As a developer, I want same-problem and related verdicts when Jev is on. (FR-M22)
22. As a developer, I want local candidates without verdicts when Jev is off, so that my agent can still judge them itself. (FR-M23, BR-M17, AC-M13)
23. As a developer, I want cancelled items never returned as duplicate candidates. (AC-M14)
24. As anyone, I want MCP search queries not logged, as for the search page. (BR-S20)

### Triage, releases, technical debt
25. As a triage lead, I want my agent to read the triage queue with possible duplicates and what a merge would do, so that it can prepare my decisions. (FR-M07)
26. As a PM, I want my agent to read a release: lifecycle status, dates, progress, Overdue, go/no-go decision, open release blockers, and items by status. (FR-M08)
27. As a developer, I want my agent to read the project's Stream with Done limited to the last 7 days. (FR-M08)
28. As a developer, I want my agent to list technical-debt tasks by project, status, and assignee, so that it can check what is already recorded. (FR-M09)

## Implementation Decisions

### Tools

All tools are registered on the MCP server from slice 15 and call existing services. Inputs use display keys, project keys, and release versions; ids never appear in inputs except `attachment_id`.

| Tool | Input | Service |
|---|---|---|
| `rw_my_queue` | — | `QueueService.queue` for the token owner |
| `rw_get_item` | `key`, `full_timeline=false` | item read with the web app's visibility rule, `TimelineService.list_timeline` (all pages), cycles |
| `rw_get_attachment` | `key`, `attachment_id` | `S3Service` |
| `rw_search` | `query`, `project?`, `type?[]`, `status?[]` | engine `search(..., mode="page")`; `project` absent → scope all |
| `rw_find_similar` | `type`, `title`, `description?` | `similar.suggest(context="tech")`; Jev off or failed → `retrieval.same_problem_candidates` with the tech filters |
| `rw_triage_queue` | `project` | the triage-queue read + `duplicate_hints` |
| `rw_board` | `project`, `release?` | `ReleaseService.board` / `counts` / `progress` / `is_overdue`; no release → the project's Stream |
| `rw_tech_debt` | `project?`, `status?[]`, `assignee?` | the Technical debt page query |

- **Key resolution:** one helper resolves `BUG-42`, `TASK-118`, and `issue-42` (case-insensitive) as the `/issue/:slug` route does, then applies visibility; an unknown or invisible key gives `not_found`.
- **Output format:** each tool returns structured content (JSON) plus a short Markdown rendering in the text content, so that clients that show only text still read well. The Markdown is generated from the same structure.

### Significant timeline events

The default timeline of `rw_get_item` includes comments (public and internal, per visibility), and these event types: filed, triaged, status changed, recurrence, duplicate linked, and the events that record a cycle start or a Reject. Declare this set **once**, next to `TimelineEventType`, as a named set; nothing else re-derives it. `full_timeline=true` returns every event. Pagination of the timeline is internal: the tool always returns the whole (filtered) timeline.

### Agent marks on read

Every timeline entry and attachment in the response carries `via_agent`. Until slice 17 adds the columns, it is always `false`; the field exists now so that the output shape does not change later. Per-piece `you_can_edit` is added by slice 18, not here.

### Attachments on read

- An attachment whose MIME type is `image/*` and whose size is 5 MB or less is fetched from S3 through `S3Service` and returned as MCP image content. This is the one deliberate exception to "the API server never handles file bytes" (PRD Appendix A.6); state it in `CLAUDE.md` under Architecture principles.
- Every other attachment returns `{download_url, expires_at, file_name, mime_type, size}` with a presigned download URL.
- `S3Service` gains one read method (get object bytes with a size cap). Nothing else in the app uses it.

### Duplicate candidates with Jev off

`rw_find_similar` returns `{jev_used: bool, items: [{issue, verdict?, confidence?}]}`. With Jev off or failing, it returns the stage-1 candidates above the minimum similarity (`T_FLOOR`), at most `SIMILAR_LIMIT`, with no verdict. This is the MCP-only exception to BR-S03; the web panels stay hidden with Jev off. Document the exception in the engine doc's §4 table and in `CONTEXT.md`.

### Resource

`rw://item/{key}` returns the Markdown rendering of `rw_get_item` with `full_timeline=false`. It is a resource template; it lists nothing.

### Errors

`not_found`, `mcp_disabled`, `token_invalid`, plus `attachment_not_found`. A release version that does not exist in the project gives `not_found`.

## Testing Decisions

- Seam: `/mcp` through the in-process MCP client from slice 15 (`mcp_client_for`). Assert on tool outputs only, never on service calls.
- **New fake: FakeS3** in the test fakes, next to the Jev and embedding fakes. An in-memory object store patched into `S3Service` for put, get, presign upload, and presign download. Tests seed an object with bytes and a MIME type, then read it through the tool. Existing attachment tests keep their presign recorder.
- Prior art: the search tests of 12 (stage 1 with the fake embedding endpoint), the suggestion tests of 14 (fake Jev with scripted verdicts, Jev disabled), the queue tests of 10, the release board tests of 09.
- Tests named after the criteria: `test_ac_m03_*`, `test_ac_m05_image_inline`, `test_ac_m05_large_file_link`, `test_ac_m06_*`, `test_ac_m07_*`, `test_ac_m08_*`, `test_ac_m12_*`, `test_ac_m13_*`, `test_ac_m14_*`.
- Also: a Support-visibility case cannot occur (Support holds no token), but a Developer's `rw_get_item` on an item matched only through an internal note works, since internal notes are visible to tech roles; `rw_search` with Jev on returns `less_relevant` separately; `rw_board` without a release returns the Stream and limits Done to 7 days with a fixed `now`.

## Out of Scope

- Every write tool, uploads, agent marks in storage, and badges in the UI (slice 17).
- `you_can_edit`, prompts, and the writing-standard resource (slice 18).
- Any UI change.
- Image resizing or format conversion.

## Further Notes

- Add to `CONTEXT.md`: **significant timeline event** (the default set of `rw_get_item`), and the Jev-off exception for MCP duplicate candidates.
