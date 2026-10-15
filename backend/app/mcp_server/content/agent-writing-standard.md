# Releasewatch — Agent Writing Standard

> **Applies to:** every item, note, recurrence comment, and attachment an agent creates through the Releasewatch MCP server.
> **Status:** Draft for review
> **Parent document:** the MCP Server PRD (`docs/phase-2/prd-mcp.md` in the Releasewatch repository)
> **Delivery:** served by the MCP server as the resource `rw://standards/writing`, loaded by `/rw-report` and `/rw-work`, and summarized in the description of every write tool. Rules marked **[enforced]** are checked by the server; the others are guidance.

---

## 1. Purpose

A report written by an agent must let a person act without asking the agent again. It must be short enough to read in two minutes, and it must contain the real evidence, with its source.

---

## 2. Language: ASD-STE100

**Default:** all agent text is written in English, in **Simplified Technical English (ASD-STE100)**. The language of the conversation does not change this.

**Other languages:** the agent writes in another language (for example Persian) only when the developer explicitly asks for it, for that item, note, or comment. Without an explicit request, the agent writes English. In another language, the structural rules below still apply (L1–L6, L10–L13); L7–L9 apply to the Releasewatch terms and code identifiers, which stay in English.

The rules below are the subset of ASD-STE100 that applies to issue reports.

| # | Rule |
|---|---|
| L1 | Write one idea in one sentence. |
| L2 | Write a maximum of **20 words** in a procedural sentence (a step) and **25 words** in a descriptive sentence. |
| L3 | Write a maximum of **6 sentences** in a paragraph. |
| L4 | Use the active voice. ("The worker drops the event.", not "The event is dropped.") |
| L5 | Use the present tense for current behavior and the past tense for an event at a known time. |
| L6 | Use the imperative in steps. ("Open the group chat.") |
| L7 | Use one word for one meaning. Use the Releasewatch terms: item, bug, task, Stream, Release, backlog, triage. |
| L8 | Use simple, common words. Do not use idioms, slang, or phrasal verbs when a single verb is available ("remove", not "get rid of"). |
| L9 | Do not use an "-ing" word as a noun or adjective when a clear alternative exists. |
| L10 | Use "must" for a requirement and "can" for a possibility. Do not use "should" or "may". |
| L11 | Write numbers, units, and versions exactly. Write dates in ISO 8601 with a time zone (`2026-10-15T09:40+03:30`). |
| L12 | Put code identifiers, paths, endpoints, field names, and commands in `backticks`. |
| L13 | Write a hypothesis as a hypothesis. Start it with **Hypothesis:**. Never write a guess as a fact. |

---

## 3. Format

| # | Rule |
|---|---|
| F1 | Write Markdown only. Do not write HTML. Do not use emoji. |
| F2 | Use only the `##` headings of the template for the item type (§5). Do not add other headings. Omit a section that has no content, except the required sections. |
| F3 | Use a **table** for evidence, comparisons, and lists of three or more items with the same attributes. |
| F4 | Use **one Mermaid diagram** at most, only for a flow, a sequence, or a state change that is hard to follow in text. Use 15 nodes at most. |
| F5 | Put code, log lines, queries, and error messages in fenced code blocks with a language tag. Copy them exactly. Do not edit them. |
| F6 | Put a maximum of **20 lines** in one code block. Put longer content in an attachment (§7). |
| F7 | Refer to other items by their key (`BUG-42`, `TASK-118`). |

---

## 4. Length

| Text | Minimum | Target | Maximum |
|---|---|---|---|
| Title **[enforced]** | 15 characters | 50–70 characters | 90 characters |
| Bug description | Summary + Observed + Expected + Evidence | 150–400 words | 700 words |
| Technical-debt description | Summary + Current state + Evidence + Risk + Suggested approach | 200–500 words | 800 words |
| Description, total size **[enforced]** | — | — | 12,000 characters, including code blocks and tables |
| Note | One sentence | 30–150 words | 300 words |
| Recurrence comment | When + where + one evidence row | 30–100 words | 200 words |

Word counts exclude code blocks, tables, and diagrams. When the content is longer than the maximum, move detail to an attachment. Do not cut evidence to fit.

---

## 5. Templates

### 5.1 Title

- Bug: `<Area>: <observed problem>` — for example `Group chat: reactions are not saved in group-type chats`.
- Technical debt: `<Area>: <what is wrong>` — for example `Notification worker: retries have no upper limit`.
- Do not start with "Bug", "Fix", "Issue", or a key. Do not end with a period.

### 5.2 Bug description

The bug form has its own fields. Use them, and do not repeat their content in the description:
- Reproduction steps → the **reproduction steps** field (step, expected result, actual result).
- cURL → the **cURL** field.
- Environment → the **environment** fields.

```markdown
## Summary
<1–3 sentences: what fails, where, for whom.>

## Observed behavior
<What happens. Exact error text in a code block.>

## Expected behavior
<What must happen.>

## Evidence
| Source | Locator | Time range | What it shows |
|---|---|---|---|

## Impact
<Who and how many are affected, and how often. Numbers when known; "Unknown" when not.>

## Suspected cause
**Hypothesis:** <the cause and why the evidence points to it.>

## Code references
| Repository | Path | Lines | Commit |
|---|---|---|---|

## Related items
<Keys, one line each, with the relation: "Same area as BUG-31", "Same problem as TASK-118, which is Done".>
```

Required: Summary, Observed behavior, Expected behavior, Evidence.

**Reproduction steps.** Write one action in one step. Each step is one imperative sentence (L2, L6).
- Put each precondition in its own step, before the actions: the user to sign in as, the data to select or create.
- Do not write the environment in a step ("On staging, …"). It goes in the **environment** fields.
- Give the expected result and the actual result only on the step where the problem shows.

| # | Step | Expected result | Actual result |
|---|---|---|---|
| 1 | Sign in as a user of customer 1327. | | |
| 2 | Call `GET /api/v1/conversation/list`. | The list is returned. | The request fails with `42703`. |

Not: one step "On staging, as a customer 1327 user, call `GET /api/v1/conversation/list`."

### 5.3 Technical-debt description

```markdown
## Summary
<1–3 sentences: what is wrong and why it matters.>

## Current state
<How the code works today. Code references inline.>

## Evidence
| Source | Locator | Time range | What it shows |
|---|---|---|---|

## Risk
<What can fail, when, and what it costs. Separate observed failures from possible ones.>

## Suggested approach
<Numbered steps. A Mermaid diagram if F4 applies.>

## Code references
| Repository | Path | Lines | Commit |
|---|---|---|---|

## Related items
```

Required: Summary, Current state, Evidence, Risk, Suggested approach.

### 5.4 Notes

| Note | Content |
|---|---|
| PR link | `PR: [<PR title>](<url>)` and one sentence on what the PR changes. |
| New evidence on an existing item | One sentence that states the finding, then an Evidence table. |
| Agent correction | One sentence that states what was wrong in the earlier agent content and what is correct now. |

### 5.5 Recurrence comment

One or two sentences: when and where the problem occurred again. Then an Evidence table with one row at minimum.

---

## 6. Evidence

| # | Rule |
|---|---|
| E1 | Every claim about behavior, frequency, or impact must have an evidence row or be marked **Hypothesis:** or **Unknown**. |
| E2 | Name the source explicitly: Sentry, Elasticsearch / Kibana, Grafana, a database query, the code, a local run, a CI run, or the developer's statement. |
| E3 | Give an exact locator: a URL, a Sentry event or issue ID, a saved Kibana query or the query text, a `path:line` at a commit SHA, a CI job URL. |
| E4 | Give the time range with a time zone for every log, metric, or error source. |
| E5 | Give a link only when the agent opened it or the developer gave it. Never construct or guess a URL. When a source is not accessible to the agent, write "Not verified" in the row. |
| E6 | For a count, give the number and how it was counted ("312 events in Sentry issue `NEXT-API-1F3`, 2026-10-14T00:00–23:59+03:30"). |
| E7 | Mark the developer's statements as such: Source = "Developer statement". |

Example:

| Source | Locator | Time range | What it shows |
|---|---|---|---|
| Sentry | [NEXT-API-1F3](https://sentry.example/issues/1F3) | 2026-10-14 00:00–23:59 +03:30 | 312 `IntegrityError` events on `POST /chat/reactions` |
| Kibana | `service:chat AND level:error AND path:"/chat/reactions"` | Same | Every error has `chat.type = group` |
| Code | `chat/reactions/service.py:88` @ `a1b2c3d` | — | The insert uses the private-chat unique key |

---

## 7. Attachments

| # | Rule |
|---|---|
| A1 | Keep information in the description when it fits the limits of §3 and §4. |
| A2 | Attach a file when the content is: a screenshot or screen recording; a log of more than 20 lines; a script or query of more than 20 lines; a result set of more than 20 rows; a trace, HAR, or dump file. |
| A3 | Refer to every attachment from the description by its file name, in the Evidence table or the text. An attachment with no reference must not be uploaded. |
| A4 | Name files `<source>-<content>-<yyyymmdd>.<ext>` — for example `kibana-chat-errors-20261014.log`, `screenshot-reaction-missing-20261015.png`. |
| A5 | Cut a log to the relevant time range and the relevant lines. Write the cut in the Evidence row ("lines 1,200–1,450 of 9,000"). |
| A6 | A screenshot must show the problem. Do not attach a screenshot that only shows text that the description already has. |

---

## 8. Self-check before filing

The agent checks these points, then shows the draft to the developer before it files:

1. The title follows §5.1 and is 90 characters or fewer.
2. Every required section of the template is present.
3. Every claim has evidence, or is marked **Hypothesis:** or **Unknown** (E1).
4. Every evidence row has a source, a locator, and a time range where applicable (E2–E4).
5. No link is guessed (E5).
6. Reproduction steps, cURL, and environment are in their fields, not in the description. Each step has one action, and each precondition is its own step.
7. No sentence is longer than the limit of L2. The text uses the active voice.
8. Every attachment has a reference in the description (A3).
9. The description is within the limits of §4.

---

## 9. Server checks

The server enforces only what it can check without judgment:

| Check | Result when it fails |
|---|---|
| Title length 15–90 characters | Refused: `title_length` |
| Description 12,000 characters or fewer | Refused: `description_too_long`, with the hint to move detail to attachments |
| Note 3,000 characters or fewer | Refused: `note_too_long` |
| Every `upload_id` of a filing is used | Refused: `unknown_upload` |

Everything else is guidance in the prompts and the tool descriptions. The developer reviews every draft before it is filed (M5).
