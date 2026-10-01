# 05 — Support Intake

> **Depends on:** 04 · **PRD:** FR-07–12, FR-44, FR-45, BR-33–35; §8.3; AC-01–06
> Triage decisions on these reports are built in 06. Support notifications are wired in 06.
> **v2.1:** the similar-reports panel (FR-12) moved to slice 14. It needs the search engine and exists only while Jev is enabled. This slice only reserves its place in the layout.

## Problem Statement

Support reports bugs in a Telegram group. Reports often lack the data engineers need. For an online-class problem, that means the class time, the class, and the affected user. Nothing tracks whether anyone picked a report up. Support has no way to see what has already been reported, so the same problem gets reported many times.

## Solution

Admins and the CTO define **support templates** per project. Each template is an ordered list of fields, some of them required. A Support user picks a project, then a template, fills the fields plus a title and an optional free description, and submits. The system validates the fields, **composes them into the item's description** as a structured block, and creates a bug with status New and source Support in that project's triage queue. Support gets a **Support reports** list of every support-sourced item. The similar-reports panel is added in 14.

## User Stories

1. As an admin or CTO, I want to create templates for a project, so that Support is asked for the right information for each kind of problem. (FR-44)
2. As an admin, I want to give a template a name, so that Support can pick the right one, such as "Online class problem" or "Payment problem".
3. As an admin, I want to add fields with a label, type (short text, long text, number, date, date-time, single select, URL), required flag, and help text, so that the form asks precisely. (§8.3)
4. As an admin, I want to define the options of a single-select field.
5. As an admin, I want to reorder a template's fields by dragging, so that the form reads naturally.
6. As an admin, I want to deactivate and reactivate a template, so that I can retire it without deleting history. (FR-44)
7. As an admin, I want editing or deactivating a template to leave existing reports unchanged, so that history is never rewritten. (FR-45, BR-35, AC-04)
8. As an admin who wants customer IDs collected, I want to add a "Customer ID" field to the relevant templates, so that the product has no hardcoded customer concept. (P2)
9. As a Support user, I want to see only projects that have at least one active template, so that I never pick a project I can't report on. (FR-08, BR-33, AC-01)
10. As a Support user, I want to pick a project, then a template, so that the form shows the right fields. (FR-07)
11. As a Support user, I want the form to show each field with its help text, so that I know what to enter.
12. As a Support user, I want to enter a required title, an optional free description, and attachments, so that I can add anything the template doesn't cover. (FR-09)
13. As a Support user, I want submission blocked with the missing required fields highlighted, so that incomplete reports never reach engineers. (AC-02)
14. As a Support user, I want type checks on number, date, date-time, URL, and select fields, so that values are usable.
15. As a Support user, I want the report to be created as a New bug in the chosen project, with source Support, so that it enters triage. (FR-10, AC-03)
16. As an engineer, I want the report's description to list each template field's label and value in template order, followed by the free description, so that I can read the report without looking anything up. (FR-10, AC-03)
17. As a Support user, if the template is deactivated while I'm filling it in, I want to be told it's no longer available with my entered values still on screen, so that I don't lose my work. (AC-05)
18. As a Support user, I want a Support reports list of every support-sourced item across all projects, with status, project, recurrence count, and last update, so that I can follow up. (FR-11)
19. As a Support user, I want to search that list by text and filter it by project and status. (FR-11)
20. As a Support user, when a project's last active template is deactivated, I want existing reports in that project to stay visible to me. (AC-06)
21. As a triage lead, I want to be notified when a support report lands in my project's queue, so that I pick it up.
22. As a triage lead, I want support reports marked with a Support source badge in the triage queue, so that I know who is waiting on the answer.

## Implementation Decisions

### Schema

- `issues.source`: `internal | support`, non-null, default `internal`. Existing rows become `internal`.
- `issues.recurrence_count`: `Integer`, non-null, default 1. It is added here so the list can show it. The count is incremented in 06 and 07.
- `support_templates`: `id, project_id FK, name, is_active, position, created_by_id, timestamps`. Unique `(project_id, name)`.
- `support_template_fields`: `id, template_id FK, position, label, field_type, is_required, help_text, options JSONB (single select only)`. Unique `(template_id, position)`.
- Field values are **not** stored as columns (BR-34). The composed description is the record. The submission's raw values are also written into the `filed` timeline event's `meta` as `{template_id, template_name, values}`. This is a forensic copy that the UI never reads, so there is no second source of truth to drift.

### Composition (pure function)

`compose_report(template_snapshot, values, free_text) -> (markdown, errors)` validates and renders. Output format:

```markdown
**Report template:** Online class problem

- **Class time:** 2026-09-21 18:00
- **Class name:** IELTS B2 — Evening
- **Customer ID:** 48213

---

<free description, verbatim, omitted with the rule above it when empty>
```

Empty optional fields are omitted. Dates are rendered as ISO. Select values are rendered as their label. Markdown in user values is escaped so field content can't break the block.

### API

- `GET /support/projects`: projects with at least one active template (`submit_support_report`).
- `GET /support/projects/{id}/templates`: active templates with fields.
- `POST /support/reports` with body `{template_id, title, values: {field_id: value}, description?, pending_attachments[]}`. It reuses the existing pre-upload attachment flow and creates a bug through `IssueService.create` with `source=support`, `status=new`, and priority null. The inactive-template case returns 409 `code: template_inactive`. Validation errors return 422, keyed by `field_id`.
- `GET /support/reports`: paginated, supporting `q`, `project_id`, and `status` (multi). It uses `visible_issues(actor)` from 04 and filters to `source=support`. Tech users can open it too.
- Admin endpoints under `/projects/{id}/templates`: CRUD, `PUT .../fields` (replaces the ordered field list), and `POST .../activate` and `.../deactivate` (`manage_templates`: CTO and Admin).
- The `filed` fan-out for `source=support` also notifies the triage lead (already covered by the `filed` matrix row). Telegram template copy: "New support report in <project>: <title>".

### Frontend

- New routes: `/support/new` (the report form) and `/support/reports` (the list). Both are in the Support nav and in the tech nav under Issues → "Support reports".
- **Form:** project select → template select → dynamic fields rendered from field type using existing `ui/` primitives (`Input`, `Textarea`, `DatePicker`, `Select`, and a date-time composed of `DatePicker` plus a time input) → title, description (`MarkdownComposer` without internal-note toggle), and attachments. Reserve the space for the similar-reports panel (beside the title on desktop, below it on narrow screens); 14 fills it. On 409 `template_inactive`, keep the form state and show an inline banner.
- **Templates admin:** a Settings → Projects → project → "Support templates" tab. It has the template list and a field editor with drag reorder (`@dnd-kit/sortable`, already a dependency).
- The triage queue and issue rows show a Support source badge.

## Testing Decisions

- API tests for every story. Named ACs: `test_ac_01_project_without_active_template_hidden`, `test_ac_02_required_field_blocks_submit`, `test_ac_03_submission_composes_description_in_template_order`, `test_ac_04_template_edit_does_not_change_existing_items`, `test_ac_05_inactive_template_rejected_on_submit`, and `test_ac_06_reports_remain_visible_after_last_template_deactivated`.
- Composition edge cases go through the API: every field type valid and invalid, empty optional fields omitted, markdown in values escaped, and a single-select value not in the options.
- A Support user gets 403 on the template admin endpoints.
- **E2E (key screen 1)** — `e2e/tests/support-report.spec.ts`:
  1. The Support user opens New report and sees only projects with active templates.
  2. They pick a project and template, submit empty, and see required fields highlighted.
  3. They fill the fields and submit. (The similar-reports step is added to this scenario in 14.)
  4. The report appears in Support reports with status New.
  5. As the triage lead (second storage state), the report appears in the triage queue with a Support badge.

  Seed: extend `seed_e2e.py` with one project that has a template of three fields (one required date-time, one select, one short text) and one project with none.

## Out of Scope

- Triage outcomes and the notifications that go back to Support (06).
- The "Report recurrence" button (07). Only the count column exists now.
- Structured filtering on template values (a deliberate limitation, PRD §15).
- Template versioning beyond "changes affect future submissions only".

## Further Notes

- There is no per-project "accept support reports" toggle. Having an active template is the toggle, as decided in product review.
