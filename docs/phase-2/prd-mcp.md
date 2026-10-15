# Releasewatch Phase 2 — MCP Server

> **Product:** Releasewatch
> **Phase:** 2 — addition
> **Status:** Draft for review (v3)
> **Owner:** CTO
> **Parent document:** [Phase 2 PRD v3](prd-v2.md). Rule numbers without a letter prefix (FR-04, BR-30…) refer to it. Search rules (`S`): [Search & Ranking Engine](prd-search-engine.md). Cycles: [cycle-model.md](cycle-model.md), [ADR 0004](../adr/0004-rejected-is-a-status.md).
> **Companion document:** [Agent Writing Standard](agent-writing-standard.md)

---

## Table of Contents

0. [Changes](#0-changes)
1. [Overview](#1-overview)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Principles](#3-principles)
4. [Capabilities](#4-capabilities)
5. [Functional Requirements](#5-functional-requirements)
6. [Business Rules](#6-business-rules)
7. [Acceptance Criteria](#7-acceptance-criteria)
8. [Notifications](#8-notifications)
9. [Changes to Other Documents](#9-changes-to-other-documents)
10. [Deliberate Limitations](#10-deliberate-limitations)
11. [Open Points for Review](#11-open-points-for-review)
12. [Glossary](#12-glossary)
- [Appendix A — Technical design](#appendix-a--technical-design)

---

## 0. Changes

### v3

| Area | v2 | v3 |
|---|---|---|
| Tools | Capability list without names | **18 named tools, 3 prompts, 2 resources** (§4) |
| Returned work | Returned marker (FR-63) | **Rejected** status and the cycle badge, as built (ADR 0004) |
| Duplicate candidates | Same project | **Every project the user can see**, as the tech create form does today |
| Timeline in Get item | Full timeline | Comments, notes, and significant events by default; full timeline on request |
| Writing | Report sections as guidance in `/rw-report` | **[Agent Writing Standard](agent-writing-standard.md)**: English in ASD-STE100 by default, templates, evidence rules, length limits, attachment rules; four checks enforced by the server |
| Report language | Language of the conversation | **English (ASD-STE100)**. Another language only when the developer explicitly asks |
| Attachments | Upload and read, mechanism open | Upload through presigned URLs (unchanged principle). Images are read through the server, as a deliberate exception |
| Technical design | — | **Appendix A**: tokens, origin columns, last-writer rule, transport |

---

## 1. Overview

Developers work with AI coding agents. Today those agents know nothing about Releasewatch. The developer copies an item's description, reproduction steps, cURL, screenshots, and QA's reject comment into the agent by hand. Problems the developer notices in the codebase outside the current task are rarely recorded, because collecting the context and evidence for each one is tedious.

Releasewatch exposes an **MCP server**. It turns the developer's agent into an assistant for Releasewatch work that the developer could do but that is heavy or tedious:

1. **Read the full context of work**: the queue, an item with its fields, timeline, cycles, images, and attachments.
2. **Search history** before touching an area.
3. **Report what it finds**: gather evidence from the codebase and from tools such as Sentry or Kibana, and file a complete bug or technical-debt task, after checking for duplicates with the developer.
4. **Document existing items**: notes, attachments, missing reproduction data, recurrences, and PR links.

The developer stays in charge. The agent never changes the state of work: every status change, placement, triage decision, release action, and queue change is made by a person in the Releasewatch UI.

---

## 2. Goals & Non-Goals

### Goals

1. An agent gets the full context of an item from Releasewatch, including images and attachments, with no copy-pasting.
2. Problems found while coding are recorded as complete, evidence-based reports, and enter through the same doors as any other work: triage for bugs, the backlog for technical debt.
3. Duplicates are caught before they are filed, with the developer deciding.
4. Agent reports have a consistent, short, evidence-first shape.
5. Everyone can tell which content an agent produced, and on whose behalf.
6. Connecting an agent takes one copy from the profile page.

### Non-Goals

- **Changing the state of work** through MCP: status, container, triage outcome, release actions, queue order, pins.
- **Unattended agents** (CI jobs, scheduled agents, background agents). Every MCP session has a person present.
- **Planning**: breaking a spec into tasks. Agents file only bugs and technical debt.
- **Support users.** MCP is for the tech team only.
- **Labels** through MCP.
- **Limits** on how much an agent can file.
- **Customizable** prompts, writing standard, or list of supported clients.

---

## 3. Principles

**M1 — The agent documents; people decide.** The agent creates items, notes, attachments, field values, and recurrences. It never changes status, container, triage outcome, release state, or a queue.

**M2 — One identity, one accountable person.** The agent acts as the user who connected it, with exactly that user's visibility and capabilities, minus what M1 excludes. The user is accountable for everything their agent produces. MCP never grants anything the user cannot do in the UI.

**M3 — Agent content is marked, permanently.** Everything created through MCP is marked as agent content when it is created, and the mark never changes (P5). It shows as an **Agent** badge next to the user's name.

**M4 — Same doors.** An agent-filed bug enters triage. An agent-filed task enters the backlog. Agent work gets no shortcut into a container.

**M5 — The developer confirms.** Whenever the agent finds a possible duplicate, or would set an assignee, a priority, or a recurrence, or would file anything, it shows the developer first. The product ships this behavior in its prompts and tool descriptions.

**M6 — Evidence first, briefly.** An agent report states what was observed, where, and when, with the source. Guesses are marked as guesses. The [Agent Writing Standard](agent-writing-standard.md) defines the shape.

---

## 4. Capabilities

### 4.1 Tools

| Tool | Kind | Purpose |
|---|---|---|
| `rw_context` | Read | Who the user is, the projects they can see, whether Jev is enabled |
| `rw_my_queue` | Read | The user's personal queue in queue order |
| `rw_get_item` | Read | Full context of one item |
| `rw_get_attachment` | Read | One attachment: images inline, other files by download link |
| `rw_search` | Read | The search page of the engine |
| `rw_find_similar` | Read | Duplicate candidates for a draft |
| `rw_triage_queue` | Read | A project's triage queue with possible duplicates |
| `rw_board` | Read | The Stream or a release: header and items by status |
| `rw_tech_debt` | Read | Technical-debt tasks |
| `rw_upload_prepare` | Write | Start an upload; returns an upload URL |
| `rw_file_bug` | Write | File a bug into triage, with the duplicate check |
| `rw_file_tech_debt` | Write | File a technical-debt task into the backlog, with the duplicate check |
| `rw_add_note` | Write | Add an internal note |
| `rw_attach` | Write | Attach an uploaded file to an item |
| `rw_fill_field` | Write | Fill an empty reproduction steps, cURL, or environment field |
| `rw_report_recurrence` | Write | Report a recurrence |
| `rw_update_own` | Write | Edit content the agent owns |
| `rw_delete_own` | Write | Delete a note or attachment the agent owns |

### 4.2 Prompts

`/rw-next`, `/rw-work <key>`, `/rw-report` (FR-M33–FR-M35).

### 4.3 Resources

`rw://item/{key}` (an item's context as Markdown) and `rw://standards/writing` (the [Agent Writing Standard](agent-writing-standard.md)).

### 4.4 Not offered

Status change, Reject, verify, triage outcomes, merge, project move, placement, assignee or priority change after filing, labels, flags, pins, queue order, release actions, item deletion.

---

## 5. Functional Requirements

### 5.1 Read

**FR-M01** **`rw_context`** returns the user's name and role, the projects they can see (key and name), and whether Jev is enabled.

**FR-M02** **`rw_my_queue`** returns the user's personal queue in queue order (FR-36): the In progress group, then pinned items, then the rest. Each entry has key, type, title, project, status (including **Rejected**), priority, pin, cycle number, and due date.

**FR-M03** **`rw_get_item`** (`key`, `full_timeline`) returns one item:
- every field the user can see, including the full cURL command with its headers;
- the container and its kind (Stream or Release);
- the timeline. By default: public comments, internal notes, and the events filed, triaged, rejected, recurrence, status changes, and cycle starts. With `full_timeline`, every event. Each entry has author, time, and whether an agent made it;
- the cycles, and for a Rejected item, the reject comment;
- the attachments, with name, type, size, author, and whether an agent added it;
- for each note, field, attachment, title, and description: whether this user's agent may still edit it (BR-M07).

**FR-M04** **`rw_get_attachment`** (`key`, `attachment_id`) returns an image of 5 MB or less as an image, so the agent can see it. It returns any other attachment as a short-lived download link.

**FR-M05** **`rw_search`** (`query`, `project`, `type`, `status`) runs the search-page query of the engine (FR-S02–FR-S04), including Jev reranking when Jev is enabled. With a project, it searches that project; without one, every project the user can see (FR-S01). Results under the relevance threshold are returned separately as less relevant. Queries are not logged (BR-S20).

**FR-M06** **`rw_find_similar`** (`type`, `title`, `description`) returns duplicate candidates (§5.5).

**FR-M07** **`rw_triage_queue`** (`project`) returns the project's New and Needs info bugs (FR-17), with possible duplicates and their merge effects (FR-S13) while Jev is enabled.

**FR-M08** **`rw_board`** (`project`, `release`) returns, without a release, the project's Stream: items by status, Done limited to the last 7 days (FR-47). With a release, it returns the release header (lifecycle status, dates, progress, Overdue, go/no-go decision, open release blockers) and its items by status.

**FR-M09** **`rw_tech_debt`** (`project`, `status`, `assignee`) returns technical-debt tasks with those filters (FR-27).

### 5.2 Uploads

**FR-M10** **`rw_upload_prepare`** (`file_name`, `mime_type`, `size`) returns an `upload_id` and a short-lived upload URL. The agent uploads the file to that URL. An upload is used by `rw_file_bug`, `rw_file_tech_debt`, or `rw_attach`. An unused upload expires after one hour.

### 5.3 Filing

**FR-M11** **`rw_file_bug`** takes: project (required), title (required), description, reproduction steps, cURL, environment, `upload_ids`, assignee, and `file_anyway`. The bug is created in **New**, with **no container**, source **Internal**, no priority, and marked as agent content. It enters the project's triage queue and notifies the triage lead (FR-04, §13).

**FR-M12** **`rw_file_tech_debt`** takes: project (required), title (required), description, priority, `upload_ids`, assignee, and `file_anyway`. The task is created in **To do**, in the **backlog**, with category **Default**, the **technical debt** flag set, priority **Medium** unless given, and marked as agent content.

**FR-M13** A filing first runs the duplicate check (§5.5). When candidates exist and `file_anyway` is not set, nothing is filed and the call returns the candidates. With `file_anyway`, the item is filed. When no candidates exist, the item is filed directly.

**FR-M14** An assignee is set only when the developer explicitly asked for one, for themselves or a named person. A priority on a technical-debt task is set only after the developer confirmed the agent's proposal.

**FR-M15** When the problem belongs to a **Done** item, the agent files a **new bug** and refers to the Done item in the description, as free text ("Same problem as TASK-118, which is Done"). Triage merges it, and the Done item comes back with a new cycle (BR-49, ADR 0004).

### 5.4 Existing items

**FR-M16** **`rw_add_note`** (`key`, `body`) adds an **internal note**, marked as agent content. Markdown is supported. A PR link is recorded this way, in a new note.

**FR-M17** **`rw_attach`** (`key`, `upload_id`) adds an item-level attachment, marked as agent content. On a support-sourced bug, Support sees it.

**FR-M18** **`rw_fill_field`** (`key`, `field`, `value`) sets reproduction steps, cURL, or environment on a bug, only while that field is empty and the bug is not Done or Cancelled. Each fill adds a timeline event marked as agent content.

**FR-M19** **`rw_report_recurrence`** (`key`, `comment`) records a recurrence on an open or Cancelled bug (FR-13–FR-15), marked as agent content. The agent uses it only when the developer explicitly confirmed that the problem is the same. It is not available on Done items (FR-16, BR-23).

**FR-M20** No tool changes a description of an item the agent did not file. New information goes into a note.

### 5.5 Duplicate check

**FR-M21** Candidates are items of any type, in every project the user can see, that are not Cancelled. This matches the tech create form (FR-S08 as built).

**FR-M22** With Jev enabled, the check returns the candidates Jev judges **same problem** or **related**, with the verdict.

**FR-M23** With Jev disabled or unavailable, the check returns the top local (stage 1) candidates above the minimum similarity (FR-S04), with no verdict. The agent judges them itself (BR-M17).

**FR-M24** When candidates are returned, the agent reads them (`rw_get_item`), and if one describes the same problem, asks the developer: file anyway, or document the existing item (note, attachments, missing fields, and recurrence where allowed). A Done candidate leads to FR-M15.

### 5.6 Own content

**FR-M25** **`rw_update_own`** (`key`, `target`, `value`) edits:
- a note the agent wrote;
- a field the agent filled, while the bug is not Done or Cancelled;
- the title or description of an item the agent filed, while the bug is **New** or the task is in the **backlog**.

**FR-M26** **`rw_delete_own`** (`key`, `target`) deletes a note or an attachment the agent created.

**FR-M27** Both apply the last-writer rule (BR-M07). Agent edits show the **edited** marker that a person's edits show. Deletion follows the UI's behavior.

**FR-M28** In the UI, agent content is the owner's own content. The owner may do with it everything they may do with their own notes, attachments, fields, and items. (As built, the author or uploader may edit and delete their own comments and attachments.)

### 5.7 Origin

**FR-M29** Agent content shows an **Agent** badge next to the owner's name: items (page header, triage queue rows, backlog rows, Technical debt rows, card hover), notes, attachments, field-fill events, and recurrences in the timeline. The badge shows nothing else: no client, device, model, or token name.

**FR-M30** The triage queue, the backlog, and the Technical debt page can be filtered by origin: All, Agent, People.

### 5.8 Writing

**FR-M31** Every item, note, and recurrence comment written by an agent follows the [Agent Writing Standard](agent-writing-standard.md). The default language is English in ASD-STE100. The agent writes in another language only when the developer explicitly asks, for that piece of content.

**FR-M32** The server enforces the checks of the standard that need no judgment (Standard §9): title length, description size, note size, and that every `upload_id` of a filing exists. Everything else is guidance.

### 5.9 Prompts and resources

**FR-M33** **`/rw-next`** loads the user's next item: the first In progress item, or else the first item of the queue. It loads the full context, including images. It does not change the item's status; it reminds the developer to move it in the UI.

**FR-M34** **`/rw-work <key>`** loads the full context of one item, and for a Rejected item, starts from the reject comment. When the developer opens a PR, the agent adds a note with the PR link (Standard §5.4).

**FR-M35** **`/rw-report`** runs the reporting workflow:
1. Load the writing standard.
2. Gather evidence from the codebase, the conversation, and the tools the developer has (Sentry, Kibana, CI).
3. Decide with the developer whether this is a bug or technical debt.
4. Draft the report by the standard, and show it to the developer.
5. Run the filing without `file_anyway`. If candidates come back, read them and ask the developer (FR-M24).
6. For technical debt, propose a priority; set it only if the developer confirms.
7. Upload attachments where the standard requires them, then file.

**FR-M36** **`rw://item/{key}`** returns the default context of `rw_get_item` as Markdown, for clients that let the developer reference a resource directly. **`rw://standards/writing`** returns the writing standard.

**FR-M37** Prompts, resources, and tool descriptions are part of the product and the same for every installation.

### 5.10 MCP page (profile)

**FR-M38** Every tech user has an **MCP** page in their profile. Support users do not.

**FR-M39** The page shows whether MCP is enabled, the MCP **base URL**, and the user's tokens: name, created, expires, last used, status (active, expired, revoked), and **Revoke**.

**FR-M40** **Create token**: a name (required) and a lifetime: 30 days, **90 days (default)**, or 1 year. There is no option without expiry.

**FR-M41** After creation, the token value is shown **once**, with a ready-to-copy configuration for **Claude Code, Codex, and ZCode** that contains the base URL and the token. For a client that does not support MCP prompts or resources, the guide says so. After the page is closed, the value cannot be shown again.

**FR-M42** An expired token cannot be renewed. The user creates a new one.

**FR-M43** While MCP is disabled, the page says it is disabled by the administrator, and token creation is unavailable. Existing tokens are listed and can be revoked.

### 5.11 Administration

**FR-M44** Settings → **MCP** (Admin) has an **Enabled** switch and a list of every user's tokens (user, name, created, expires, last used, status) with **Revoke**.

**FR-M45** While MCP is disabled, every MCP request is refused with "MCP is disabled by the administrator". Tokens are not changed, and work again when MCP is enabled, unless they expired.

---

## 6. Business Rules

### Boundaries

**BR-M01** MCP offers no operation that changes an item's status, container, project, flags, or labels; that changes priority or assignee after filing; that records a triage outcome, a Reject, or a merge; that acts on a release; or that reorders, pins, or unpins a queue.

**BR-M02** An MCP token is accepted only by the MCP server, and a UI session is never accepted by the MCP server.

**BR-M03** Every MCP request is authorized as the token's owner. Visibility follows the PRD (BR-30, BR-S06), exactly as in the UI.

**BR-M04** Only tech users can hold tokens.

### Origin and ownership

**BR-M05** Items, timeline entries, and attachments created through MCP are marked as agent content when they are created. The mark never changes.

**BR-M06** Every comment created through MCP is an internal note.

**BR-M07** **Last writer.** The agent may edit or delete a piece of content (a note, an attachment, a field value, an item's title or description) only while its last writer is the same user through MCP, with any of the user's tokens. Once a person changes it in the UI, the agent cannot touch it.

### Filing

**BR-M08** An agent-filed bug always enters triage in New, with no container and no priority.

**BR-M09** An agent-filed task is always a technical-debt task in the backlog, category Default.

**BR-M10** Neither starts a cycle (BR-62).

**BR-M11** An agent-filed item has an assignee only when the developer explicitly asked for one. It then enters the assignee's queue by the default rule (FR-39).

**BR-M12** There is no limit on how much an agent can file. Cleanup relies on the origin filter.

### Existing items

**BR-M13** The agent fills reproduction steps, cURL, or environment only when the field is empty and the bug is not Done or Cancelled.

**BR-M14** The agent changes the title or description only of an item it filed, only while that bug is New or that task is in the backlog.

**BR-M15** A recurrence through MCP follows BR-22 and BR-23 unchanged, including its notifications and its effect on queue order (FR-37).

### Duplicate check

**BR-M16** Every filing runs the duplicate check over every non-cancelled item the user can see. A filing with candidates completes only with `file_anyway`.

**BR-M17** **Exception to BR-S03, for MCP only:** with Jev disabled, local candidates are returned without a same-problem judgment. The agent judges them and the developer confirms. Elsewhere, BR-S03 is unchanged.

### Writing

**BR-M18** Agent text is English in ASD-STE100 unless the developer explicitly asked for another language.

**BR-M19** Title: 15–90 characters. Description: 12,000 characters or fewer. Note: 3,000 characters or fewer. A filing refers only to existing, unused uploads of the same user.

### Tokens

**BR-M20** Every token expires after 30 days, 90 days, or 1 year. There is no token without expiry and no renewal.

**BR-M21** A token's value is shown once, at creation, and is never stored in readable form.

**BR-M22** A token is rejected when it is expired, revoked, or owned by a deactivated user, or while MCP is disabled.

**BR-M23** The owner and Admin can revoke a token. Revocation takes effect on the next request.

**BR-M24** Tokens are never deleted, so agent content always points to the token that created it.

---

## 7. Acceptance Criteria

### Boundaries

**AC-M01** Given an MCP client, then no tool changes an item's status, container, labels, or queue position, and none records a triage outcome, a Reject, or a release action.

**AC-M02** Given an MCP token, when it is sent to the UI's API, then it is refused; given a UI session token, when it is sent to the MCP server, then it is refused.

**AC-M03** Given a Developer's token, when the agent requests an item the Developer cannot see, then it is refused as not found.

**AC-M04** Given a Support user, then the profile has no MCP page and token creation is refused.

### Reading

**AC-M05** Given a bug with a 2 MB screenshot, when the agent gets the attachment, then it receives the image; given a 40 MB video, then it receives a download link.

**AC-M06** Given a Rejected item, when the agent gets it, then the response contains the reject comment and the cycle's start reason.

**AC-M07** Given an item with 40 system events and 3 comments, when the agent gets it without `full_timeline`, then the 3 comments and only the significant events are returned; with `full_timeline`, every event is returned.

**AC-M08** Given `rw_search` without a project, then results come from every project the user can see.

### Filing

**AC-M09** Given no duplicate candidates, when the agent files a bug in project P, then a bug exists in New with no container, source Internal, no priority, the Agent badge, it is in P's triage queue, and P's triage lead is notified.

**AC-M10** Given no duplicate candidates, when the agent files a technical-debt task, then it is To do in the backlog, category Default, flag set, priority Medium, Agent badge, with no cycle and no assignee.

**AC-M11** Given duplicate candidates, when the agent files without `file_anyway`, then nothing is filed and the candidates are returned; with `file_anyway`, the item is filed.

**AC-M12** Given a same-problem item in another project the user can see, when the agent files, then that item is returned as a candidate.

**AC-M13** Given Jev is disabled, when the agent files and similar items exist, then local candidates are returned without verdicts.

**AC-M14** Given a Cancelled item that matches the draft, then it is never returned as a candidate.

**AC-M15** Given the agent files with two `upload_ids`, then the item has both attachments with the Agent badge.

**AC-M16** Given an `upload_id` of another user, or one already used, when the agent files with it, then the filing is refused.

### Writing checks

**AC-M17** Given a title of 120 characters, when the agent files, then the filing is refused with `title_length`.

**AC-M18** Given a description of 15,000 characters, when the agent files, then the filing is refused with `description_too_long` and the hint to use attachments.

**AC-M19** Given a note of 4,000 characters, when the agent adds it, then it is refused with `note_too_long`.

### Existing items

**AC-M20** Given the agent adds a note, then it is an internal note with the Agent badge, and Support never sees it.

**AC-M21** Given the agent attaches a file to a support-sourced bug, then Support sees it, with the Agent badge.

**AC-M22** Given a bug in To do with empty reproduction steps, when the agent fills them, then they are set and the timeline shows a fill event with the Agent badge.

**AC-M23** Given a bug whose cURL is set, when the agent tries to fill cURL, then it is refused with `field_not_empty`.

**AC-M24** Given a Done bug, when the agent tries to fill a field or report a recurrence, then it is refused.

**AC-M25** Given an open bug with recurrence count 2, when the agent reports a recurrence, then the count is 3 and the comment has the Agent badge.

**AC-M26** Given an item the agent did not file, when the agent tries to change its description, then it is refused.

### Own content

**AC-M27** Given a note the agent wrote, when the agent edits it, then it shows the edited marker.

**AC-M28** Given a note the agent wrote and the owner then edited in the UI, when the agent tries to edit or delete it, then it is refused with `not_owner`.

**AC-M29** Given a note written by another user's agent, when this user's agent tries to edit it, then it is refused.

**AC-M30** Given a bug the agent filed, when it is New, then the agent can edit its title; after triage accepts it, the agent cannot.

**AC-M31** Given a technical-debt task the agent filed, when a PM places it in the Stream, then the agent can no longer edit its title or description.

**AC-M32** Given content created with token A, when the agent uses token B of the same user, then it can edit that content.

**AC-M33** Given a cURL value the agent filled, when a person changes cURL in the UI, then the agent can no longer change it.

### Origin

**AC-M34** Given an item filed through MCP, when its labels are removed, then the Agent badge is still shown.

**AC-M35** Given the backlog filtered to origin Agent with "Show technical debt" on, then only items filed through MCP are listed.

### Tokens and administration

**AC-M36** Given a user creates a token, then the value and the configurations for Claude Code, Codex, and ZCode are shown once, and the user receives a Telegram notification.

**AC-M37** Given the create-token form, then the lifetimes are 30 days, 90 days, and 1 year, with 90 days preselected.

**AC-M38** Given a token expiring in 7 days, then its owner receives one Telegram notification.

**AC-M39** Given an expired, revoked, or deactivated user's token, then requests are refused.

**AC-M40** Given Admin disables MCP, then every request is refused with "MCP is disabled by the administrator", and token creation is unavailable; given it is enabled again, then valid tokens work.

---

## 8. Notifications

Telegram, to the token's owner only:

| Event | Content |
|---|---|
| Token created | Token name and expiry. "If this wasn't you, revoke it" |
| Token expires in 7 days | Token name and expiry date |

Agent-filed items, notes, and recurrences send the notifications their UI equivalents send (§13 of the PRD), with no additions.

---

## 9. Changes to Other Documents

### Phase 2 PRD v3

- §7.3 permission matrix: add **Use MCP (personal tokens)** — every tech role ✓, Support —.
- §8.2: items, timeline entries, and attachments carry an **agent** mark.
- FR-42: the Agent marker appears in card hover, not on the card face (P3).
- FR-17, FR-23, FR-27: add the origin filter.
- New profile page: MCP. New Admin settings: MCP.
- §13: add the two token notifications.
- Timeline: changes to cURL and to every environment field are recorded as events (Appendix A.5). Today only the named environment is.

### Search & Ranking Engine

- BR-S03: add the MCP exception (BR-M17).
- §4 Behavior by consumer: add **MCP filing** — Jev on: same and related verdicts across visible projects; Jev off: local candidates without verdicts.

---

## 10. Deliberate Limitations

| Limitation | Reason |
|---|---|
| The agent never starts, delivers, rejects, or closes work | A status change is a claim about the work, made by a person (M1) |
| "The developer confirmed" is enforced by prompts and tool descriptions, not by the system | Every session is attended. `file_anyway` is the only confirmation the system enforces |
| Most of the writing standard is guidance | Sentence length, voice, and evidence quality need judgment. The server checks only sizes and uploads |
| A recurrence through MCP can move the item in its assignee's queue | Recurrence count is a tie-breaker of the default order (FR-37). It is a data change, confirmed by the developer |
| Agent-filed tasks are always technical debt and hidden from the default backlog | Planning is a non-goal. The origin filter and the Technical debt page show them |
| With Jev off, duplicate judgment is the agent's | The agent can judge, and the developer confirms (BR-M17) |
| Images are read through the server | The agent must see them. It is the one exception to "the API never handles file bytes" |
| Agent attachments on support-sourced bugs are visible to Support | They are logs and screenshots; nothing sensitive is expected |
| cURL is returned with its headers | Tokens in captured requests are temporary |
| No filing limit | The origin filter makes cleanup cheap |
| No token renewal and no token without expiry | Expiry exists to rotate token values; a new token is one copy |
| Prompts, the writing standard, and the client list are fixed | They change with product releases |

---

## 11. Open Points for Review

1. **Significant timeline events** (FR-M03) are proposed as: filed, triaged, rejected, recurrence, status changes, and cycle starts. Priority, label, assignment, and due-date changes are left to `full_timeline`.
2. **Image size limit** for inline reading is proposed at 5 MB.
3. **Note size limit** is proposed at 3,000 characters, which is above the standard's 300-word maximum to leave room for an Evidence table.

---

## 12. Glossary

| Term | Meaning |
|---|---|
| Agent | A developer's AI coding assistant connected to Releasewatch through MCP |
| Agent content | An item, timeline entry, or attachment created through MCP. Marked permanently |
| Agent badge | The marker next to the owner's name on agent content |
| Owner | The user a token belongs to; accountable for everything created with it |
| Last writer | Whoever last created or changed a piece of content; decides whether the agent may still edit it |
| Duplicate check | The similarity check every MCP filing runs before creating an item |
| `file_anyway` | The explicit confirmation that files an item despite duplicate candidates |
| MCP token | A named, expiring personal credential that connects an agent |
| Writing standard | The rules for agent text: [agent-writing-standard.md](agent-writing-standard.md) |

---

## Appendix A — Technical design

For the implementing session. It follows the conventions of the codebase as of `0c4dc08`.

### A.1 Components

```
┌──────────────────── api (FastAPI) ────────────────────┐
│ /api/v1/*  ── get_current_user (JWT) ───────┐         │
│                                             ▼         │
│                                         services ── policy.py
│                                             ▲         │
│ /mcp       ── get_mcp_principal ────────────┘         │
│               (rwm_ token → user + token,             │
│                sets the agent context)                │
└───────────────────────────────────────────────────────┘
```

- The MCP server runs **in the same FastAPI app**, mounted at `/mcp`, with the MCP Python SDK over **streamable HTTP**, stateless. It is another thin adapter beside the routes: tools validate input and call services. No business logic lives in it.
- It calls **services**, never the REST routes. The REST API exposes every status operation; MCP exposes only the tools of §4.
- `get_mcp_principal` reads `Authorization: Bearer rwm_…`, checks the kill switch (`system_settings`, category `mcp`, `{enabled}`, cached in Redis for 30 s), resolves the token, checks that the owner is active and a tech role, and sets the agent context (A.4). `get_current_user` rejects anything that is not a JWT, so an `rwm_` token never reaches `/api/v1` (BR-M02).

### A.2 Tokens

```
mcp_tokens
  id                  serial PK
  user_id             int FK users NOT NULL           index
  name                varchar(64) NOT NULL
  token_hash          char(64) NOT NULL UNIQUE        -- sha256 of the value
  token_prefix        varchar(12) NOT NULL            -- "rwm_a1b2c3d4", for the list
  created_at          timestamptz NOT NULL
  expires_at          timestamptz NOT NULL
  last_used_at        timestamptz
  revoked_at          timestamptz
  revoked_by_id       int FK users
  expiry_notified_at  timestamptz
```

- Value: `rwm_` + 32 random bytes, base62. Stored as sha256 only. bcrypt is not needed for a random high-entropy secret and would cost on every tool call.
- Status is derived (`revoked_at`, `expires_at`), never stored.
- `last_used_at` is written at most once a minute per token (Redis key with a 60 s TTL).
- Rows are never deleted (BR-M24).
- Celery beat, daily: tokens with `expires_at` within 7 days and no `expiry_notified_at` get the Telegram notice, then the column is set.

### A.3 Origin columns

```
issues.via_mcp_token_id             int NULL FK mcp_tokens(id) ON DELETE RESTRICT
issue_timeline.via_mcp_token_id     int NULL FK mcp_tokens(id) ON DELETE RESTRICT
issue_attachments.via_mcp_token_id  int NULL FK mcp_tokens(id) ON DELETE RESTRICT

CREATE INDEX ix_issues_agent ON issues (project_id) WHERE via_mcp_token_id IS NOT NULL;
```

- **Agent content = `via_mcp_token_id IS NOT NULL`.** One column gives the badge and the audit trail ("what did this token create?"). The API exposes only `via_agent: bool`; the token is never shown in the UI (FR-M29).
- `issue_timeline` covers comments, notes, the filed event, recurrences, and field changes. `issue_recurrences` needs no column: it links to its timeline entry.
- `issues` carries its own column, although it could be derived from the `filed` event, because the origin filter and the badge on every list row should not join the timeline.
- Immutability is by construction: no schema accepts the column, only the writers of A.4 set it, and a test asserts it. No database trigger.

### A.4 Agent context

A request-scoped `contextvars.ContextVar` `agent_token_id` (default `None`), set only by `get_mcp_principal`. Three writers read it:

| Writer | Today | Change |
|---|---|---|
| `TimelineService.create_event` | The only place that creates `IssueTimeline` rows | Stamps `via_mcp_token_id` |
| `IssueService.create` | The only place that creates `Issue` rows (Support goes through it) | Stamps `via_mcp_token_id` |
| Attachment creation | Four places: `issue_service.create`, `merge_service`, two endpoints in `api/v1/attachments.py` | Merged into one `attachment_service.add`, which stamps it |

`TimelineService.edit_comment` adds `meta.edited_via_mcp_token_id` next to the existing `meta.edited_by` and `meta.edited_at`.

Side effects of the same agent action (for example the `subscribed` event on filing) are stamped too, which is correct: they happened through the agent. Celery tasks and the Telegram bot never set the context, so they write `NULL`.

An explicit `origin` parameter through every service was considered and rejected: it changes more than 20 call sites for the same result.

### A.5 Last writer

No ownership columns. The timeline already records the actor of every change; with `via_mcp_token_id` it also records whether an agent made it. A pure module `app/agent_ownership.py` (like `workflow.py`: plain values in, a verdict out) decides from the latest relevant record:

| Piece | Latest relevant record |
|---|---|
| Title | Latest `title_changed`, else `filed` |
| Description | Latest `description_changed`, else `filed` |
| Reproduction steps | Latest `steps_changed`, else `filed` |
| Environment | Latest `environment_changed`, else `filed` |
| cURL | Latest `curl_changed` (**new**), else `filed` |
| Note | `meta.edited_by` + `meta.edited_via_mcp_token_id`, else `actor_id` + `via_mcp_token_id` |
| Attachment | `uploaded_by_id` + `via_mcp_token_id` |

The agent may write when the record's actor is the user and its `via_mcp_token_id` is a token of the user (BR-M07).

**Required change, independent of MCP:** `IssueService.update` today sets `curl_command`, `environment_browser`, `environment_os`, `environment_build_hash`, and `environment_staging_url` with no timeline event. Add `TimelineEventType.curl_changed`, and make `environment_changed` cover every environment field with `meta.fields` listing what changed. Without this, the last writer of those fields is unknown, and their changes leave no history (P5).

### A.6 Attachments

- **Upload:** `rw_upload_prepare` uses the existing presign logic and stores a pending upload in Redis under `upload_id` (user, S3 key, file name, MIME type, size; TTL 1 hour). The agent uploads with its own shell. `rw_file_*` and `rw_attach` consume the upload through `attachment_service.add`, which deletes the Redis key and enqueues the existing `validate_attachment` task. Large files use the existing multipart path. The API still never receives upload bytes.
- **Read:** an image of 5 MB or less is fetched from S3 by the server and returned as MCP image content. This is the one deliberate exception to "the API server never handles file bytes" (CLAUDE.md). Every other file is a presigned download link.

### A.7 Tool to service mapping

| Tool | Service |
|---|---|
| `rw_context` | `policy`, `jev_settings.is_enabled`, project visibility |
| `rw_my_queue` | `queue_service.queue` |
| `rw_get_item` | issue read + `timeline_service.list_timeline` + cycles + `agent_ownership` |
| `rw_get_attachment` | `s3_service` |
| `rw_search` | `search.retrieval.search(mode="page")` |
| `rw_find_similar` | `search.similar.suggest(context="tech")`; Jev off: `retrieval.same_problem_candidates` |
| `rw_triage_queue` | triage list + `search.duplicate_hints` |
| `rw_board` | `release_service.board` / `counts` / `progress` / `is_overdue` |
| `rw_tech_debt` | `backlog_service.tech_debt_clause` |
| `rw_upload_prepare` | `s3_service.generate_presigned_upload` + Redis |
| `rw_file_bug`, `rw_file_tech_debt` | duplicate check, then `issue_service.create` |
| `rw_add_note` | `timeline_service.create_event(comment, is_internal=True)` |
| `rw_attach` | `attachment_service.add` |
| `rw_fill_field` | `issue_service.update` after the emptiness and status checks |
| `rw_report_recurrence` | `recurrence_service.report` |
| `rw_update_own` | `timeline_service.edit_comment` / `issue_service.update`, after `agent_ownership` |
| `rw_delete_own` | the existing comment and attachment delete paths, after `agent_ownership` |

### A.8 Errors

Tool errors carry a stable code and a one-sentence message the agent can relay:

`mcp_disabled`, `token_invalid`, `not_found`, `duplicates_found` (with candidates), `title_length`, `description_too_long`, `note_too_long`, `unknown_upload`, `field_not_empty`, `item_closed`, `not_owner`, `recurrence_not_allowed`, `not_tech`.

### A.9 Tests

Following the existing harness (`docs/phase-2/01-test-harness.md`): HTTP tests against real Postgres, driving `/mcp` with an in-process MCP client.
- Every tool once on the happy path, and every error code once.
- One test that walks every tool and asserts that each row it writes has `via_mcp_token_id`, and that no tool changes `issues.status`, `release_id`, `labels`, or a queue entry.
- Token lifecycle: expiry, revocation, deactivated owner, kill switch, JWT on `/mcp`, `rwm_` on `/api/v1`.
- `agent_ownership` as a pure unit table.
