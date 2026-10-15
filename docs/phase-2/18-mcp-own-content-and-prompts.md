# 18 — MCP Own Content, Prompts, and the Writing Standard

> **Depends on:** 17 · **PRD:** [prd-mcp.md](prd-mcp.md) M5, M6, FR-M03 (`you_can_edit`), FR-M25–FR-M28, FR-M31, FR-M33–FR-M37, BR-M07, BR-M14, BR-M18, AC-M27–M33; Appendix A.5 · **Writing:** [agent-writing-standard.md](agent-writing-standard.md)

## Problem Statement

An agent that writes will sometimes write something wrong: a note with a wrong finding, a cURL from the wrong environment, a title that misnames the area. Today it can only add more content on top. At the same time, nothing guides how an agent works with Releasewatch: every developer must explain, in their own words, how to pick the next item, how to report a problem with evidence, and when to ask before filing. Reports then differ in shape, length, and quality from one developer's agent to another.

## Solution

- The agent can **edit or delete content it owns**: its notes, the fields it filled, its attachments, and the title and description of an item it filed while that item is still New (bug) or in the backlog (task). Ownership is decided by the **last writer**: once a person changes a piece in the UI, the agent can no longer touch it. Any of the user's tokens counts as the same owner.
- `rw_get_item` tells the agent, per piece, whether it may still edit it.
- The MCP server ships three **prompts** that encode the working method: `/rw-next`, `/rw-work <key>`, and `/rw-report`.
- The [Agent Writing Standard](agent-writing-standard.md) is part of the product: served as the resource `rw://standards/writing`, loaded by the prompts, and summarized in every write tool's description. Agent text is English in ASD-STE100 unless the developer explicitly asks for another language.

## User Stories

### Own content
1. As a developer, I want my agent to correct a note it wrote, so that a wrong finding does not stay on the item. (FR-M25)
2. As a developer, I want my agent to correct a field it filled, while the bug is not Done or Cancelled. (FR-M25)
3. As a developer, I want my agent to correct the title or description of an item it filed while the bug is New or the task is in the backlog. (FR-M25, BR-M14, AC-M30, AC-M31)
4. As a triage lead, I want the agent unable to change an item once triage accepted it or a PM placed it, so that the text I decided on stays. (BR-M14, AC-M30, AC-M31)
5. As a developer, I want my agent to delete a note or an attachment it created. (FR-M26)
6. As anyone, I want an agent edit to show the same **edited** marker as a person's edit. (FR-M27, AC-M27)
7. As a developer, I want my agent unable to touch a piece after I or anyone changed it in the UI, so that a person's correction wins. (BR-M07, AC-M28, AC-M33)
8. As a developer, I want my agent unable to edit another user's agent content. (BR-M07, AC-M29)
9. As a developer with two tokens, I want either token's agent able to edit content made with the other. (BR-M07, AC-M32)
10. As a developer, I want full control in the UI over my agent's notes and attachments, as over my own. (FR-M28)
11. As a developer, I want `rw_get_item` to say for each note, field, attachment, title, and description whether my agent may still edit it, so that it does not try and fail. (FR-M03)

### Prompts
12. As a developer, I want `/rw-next` to load my next item (the first In progress item, or else the first in my queue) with its full context and images, so that I can start without searching. (FR-M33)
13. As a developer, I want `/rw-next` to remind me to move the item's status in the UI, because the agent never does. (FR-M33, M1)
14. As a developer, I want `/rw-work BUG-42` to load one item's full context, and for a Rejected item to start from the reject comment. (FR-M34)
15. As a developer, I want `/rw-work` to add the PR link as a note when I open a PR. (FR-M34)
16. As a developer, I want `/rw-report` to gather evidence from the code, the conversation, and the tools I have (Sentry, Kibana, CI), so that the report is complete. (FR-M35)
17. As a developer, I want `/rw-report` to decide with me whether it is a bug or technical debt. (FR-M35)
18. As a developer, I want `/rw-report` to show me the draft before anything is filed. (FR-M35, M5)
19. As a developer, I want `/rw-report` to read duplicate candidates and ask me whether to file anyway or document the existing item. (FR-M24, FR-M35)
20. As a developer, I want `/rw-report` to propose a priority for technical debt and set it only if I confirm. (FR-M35)
21. As a developer, I want `/rw-report` to upload screenshots, long logs, and scripts as the standard requires, and refer to them in the description. (FR-M35)

### Writing standard
22. As a triage lead, I want every agent report in one shape (fixed sections, an Evidence table with source, locator, and time range), so that I can read any of them in two minutes. (FR-M31, M6)
23. As a triage lead, I want guesses marked as **Hypothesis:**, so that I don't act on them as facts. (M6)
24. As a developer, I want agent text in English (ASD-STE100) by default, and in another language only when I explicitly ask. (FR-M31, BR-M18)
25. As a developer, I want my agent able to read the writing standard itself (`rw://standards/writing`), so that it follows the current version. (FR-M36)
26. As an Admin, I want the prompts, the standard, and the tool descriptions the same for every installation and every user. (FR-M37)

## Implementation Decisions

### Agent ownership (pure module)

A new pure module, **Agent ownership**, beside Workflow and Policy: plain values in, a verdict and a reason out, no database or HTTP access. It is the only place the last-writer rule is written.

Input per piece: the item's type, status, and whether it is in the backlog; the piece kind (note, field, attachment, title, description); the latest relevant record's actor id and token id; the requesting user id and the user's token ids. Output: allowed, or denied with `not_owner`, `item_closed`, or `item_triaged`.

The latest relevant record per piece (PRD Appendix A.5):

| Piece | Latest relevant record |
|---|---|
| Title | latest `title_changed`, else `filed` |
| Description | latest `description_changed`, else `filed` |
| Reproduction steps | latest `steps_changed`, else `filed` |
| Environment | latest `environment_changed`, else `filed` |
| cURL | latest `curl_changed` (slice 17), else `filed` |
| Note | the edit stamp in `meta` if present, else the note's actor and token |
| Attachment | uploader and token |

Rules:
- Allowed only if the record's actor is the user **and** its token id belongs to the user (any of the user's tokens, active or not).
- Fields: also only while the bug is not Done or Cancelled.
- Title and description: also only while a bug is New or a task is in the backlog, and only on an item with `via_mcp_token_id` set (an item the agent filed).

A service-side loader gathers the records for one item in one query and passes them to the module. `rw_get_item` uses the same loader to fill `you_can_edit` for every piece.

### Edit stamp on comments

`TimelineService.edit_comment` writes `meta.edited_via_mcp_token_id` (the token id or null) next to the existing `meta.edited_by` and `meta.edited_at`. A UI edit therefore writes null and takes ownership away from the agent.

### Tools

| Tool | Input | Effect |
|---|---|---|
| `rw_update_own` | `key`, `target`, `value` | `target ∈ {note:<id>, field:reproduction_steps, field:curl, field:environment, title, description}`. Checks Agent ownership, then the writing checks (note 3,000 characters, title 15–90, description 12,000), then calls `TimelineService.edit_comment` or `IssueService.update`. |
| `rw_delete_own` | `key`, `target` | `target ∈ {note:<id>, attachment:<id>}`. Checks Agent ownership, then uses the existing comment delete and attachment delete paths unchanged. |

Both refuse with `not_owner`, `item_closed`, or `item_triaged`, with the module's reason as the message.

UI permissions do not change: the author or uploader may already edit and delete their own comments and attachments, and agent content has the owner as author or uploader (FR-M28).

### Prompts

Three MCP prompts, their text kept in the backend as product content, one file per prompt, versioned with the code:

- **`rw-next`** — calls `rw_my_queue`, picks the first In progress item or else the first entry, calls `rw_get_item` and `rw_get_attachment` for its images, summarizes the task, and tells the developer to move the status in Releasewatch. For a Rejected item it opens with the reject comment.
- **`rw-work`** (argument `key`) — the same context for one item. Instructs the agent, when a PR exists, to add one note in the standard's PR format.
- **`rw-report`** — reads `rw://standards/writing`; gathers evidence; agrees on bug or technical debt with the developer; drafts by the template; shows the draft; calls `rw_file_bug` or `rw_file_tech_debt` without `file_anyway`; on `duplicates_found`, reads each candidate and asks the developer (file anyway, or document the existing item with a note, attachments, missing fields, or a recurrence); a Done candidate leads to a new bug that refers to it; proposes a priority for technical debt and sets it only if confirmed; uploads attachments the standard requires.

Every prompt states the boundaries: never change status or placement; ask before setting an assignee, a priority, or a recurrence; write English ASD-STE100 unless the developer explicitly asked for another language.

### Resources

- `rw://standards/writing` returns the Agent Writing Standard. The file moves into the repository next to the PRD (`agent-writing-standard.md`) and is the single source; the server reads it at start.
- `rw://item/{key}` from slice 16 now includes `you_can_edit`.

### Tool descriptions

Every write tool's description gets the relevant lines from the standard (§4 limits, §5 template for the item type, §6 evidence rules) and the M5 rules (ask before `file_anyway`, assignee, priority, recurrence). Keep each description under about 1,500 characters; the full standard is in the resource.

## Testing Decisions

- **Agent ownership** is tested as a pure unit table, like Workflow and Policy: one row per piece kind × (agent last / person last / other user's agent / other token of the same user) × item state.
- **Tools** are tested at `/mcp` with the in-process MCP client: `test_ac_m27_*` (edited marker visible through `/api/v1`), `test_ac_m28_*` (UI edit, then agent edit and delete refused), `test_ac_m29_*`, `test_ac_m30_*` (accept through `/api/v1`, then title edit refused), `test_ac_m31_*` (place in the Stream through `/api/v1`), `test_ac_m32_*` (two tokens), `test_ac_m33_*` (cURL changed in the UI).
- `rw_get_item` returns `you_can_edit` consistent with the tool outcomes: for each piece, an edit attempt succeeds exactly when the flag is true.
- Prompts: list the server's prompts and assert the three names and their arguments; render each prompt and assert that it names the tools it relies on and states the boundaries. Their effect on an agent is not tested in CI.
- Resource: `rw://standards/writing` returns the file's content.
- Boundary test from slice 17 updated to the exact set of 18 tool names.
- Prior art: the Workflow and Policy unit tables (02, 04), comment edit and delete tests, the MCP tests of 15–17.

## Out of Scope

- Editing an item's title or description after triage or placement.
- Undoing a recurrence.
- Version history of edits (the edited marker only, as for people).
- Configurable prompts or a configurable standard.
- Measuring report quality.

## Further Notes

- Add to `CONTEXT.md`: **Agent ownership** (the module and the last-writer rule), **last writer**, **Agent Writing Standard**, **MCP prompt** (with _Avoid_: slash command for the server side; clients may call them that).
- Add Agent ownership to the "Where rules live" table in `00-README.md`.
