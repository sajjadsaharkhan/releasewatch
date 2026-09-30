# Releasewatch — Design & Frontend Conventions

The rules the `frontend/` codebase actually follows, extracted from the code. Where a
convention is followed inconsistently, it is written down as the rule *plus* the drift, so
new code has one target to hit. See [Known drift](#14-known-drift) for the full list.

**Source of truth**

| Concern | File |
|---|---|
| Design tokens (CSS vars, both themes) | `frontend/src/styles/globals.css` |
| Token → Tailwind binding, font stacks, radius | `frontend/tailwind.config.js` |
| Semantic color scales (priority / status / role) | `frontend/src/lib/constants.js` |
| Class merging | `frontend/src/lib/cn.js` |
| Primitive components | `frontend/src/components/ui/` |
| Shell (sidebar, topbar, main) | `frontend/src/components/layout/` |
| Theme state + persistence | `frontend/src/context/AppContext.jsx` |

---

## 1. Design intent

Releasewatch is an **operator's tool**, not a document. Pages are scanned and acted on,
not read top to bottom. Three consequences run through every rule below:

1. **Density over air.** Base UI text is 12–13px, table rows are `py-2`, the topbar is
   `h-12`. More rows on screen beats more whitespace.
2. **State is encoded in form, not just words.** Priority, status, role, and health each
   have a fixed color and shape so a row's condition reads before it is read.
3. **The neutral surface stays quiet.** Color is reserved for meaning. Chrome —
   sidebar, topbar, cards, tables — is zinc-based and near-monochrome so the semantic
   pills are the only thing that shouts.

---

## 2. Theme system

Class-based dark mode. `darkMode: 'class'` in `tailwind.config.js`; `AppContext` adds or
removes `.dark` on `document.documentElement` and persists to `localStorage` under
`rw:theme`. **Default is light** — there is no `prefers-color-scheme` fallback, a new
visitor gets light regardless of OS setting.

Every color is an HSL triple in a CSS custom property, consumed through Tailwind's
`hsl(var(--token))` bindings. **Never write a raw neutral** (`bg-white`, `text-zinc-900`,
`border-gray-200`) for chrome — use the token.

| Token | Light | Dark | Used for |
|---|---|---|---|
| `--background` | `0 0% 100%` | `240 10% 3.9%` | App ground, `<main>` |
| `--foreground` | `240 10% 3.9%` | `0 0% 98%` | Body text |
| `--card` | `0 0% 100%` | `240 8% 7%` | Cards, sidebar, topbar, dialogs, toasts |
| `--card-foreground` | `240 10% 3.9%` | `0 0% 98%` | Text on cards |
| `--border` | `240 5.9% 90%` | `240 5% 19%` | All hairlines, chart grid |
| `--input` | `240 5.9% 90%` | `240 5% 19%` | Field borders, switch track (off) |
| `--primary` | `240 5.9% 10%` | `221 83% 53%` | Primary buttons, badges, active accents |
| `--primary-foreground` | `0 0% 98%` | `0 0% 100%` | Text on primary |
| `--secondary` | `240 4.8% 95.9%` | `240 5% 13%` | Secondary buttons |
| `--muted` | `240 4.8% 95.9%` | `240 5% 11%` | Search field, skeletons, row hover |
| `--muted-foreground` | `240 3.8% 46.1%` | `240 5% 64.9%` | Labels, metadata, inactive nav |
| `--accent` | `240 4.8% 95.9%` | `240 5% 15%` | Hover/active fill on nav, menu items |
| `--accent-foreground` | `240 5.9% 10%` | `0 0% 98%` | Text on accent |
| `--destructive` | `0 84.2% 60.2%` | `0 62.8% 30.6%` | Destructive buttons, field errors |
| `--ring` | `240 5.9% 10%` | `221 83% 53%` | Focus ring |
| `--radius` | `0.5rem` | `0.5rem` | Base corner radius |

**The one asymmetry to know.** `--primary` is *not* a hue in light mode — it is near-black
zinc. In dark mode it becomes blue `221 83% 53%`. So `bg-primary` renders a black button
in light and a blue button in dark, and the focus ring changes color with the theme. This
is deliberate (light mode is monochrome-chrome; dark mode needs a lift off the near-black
ground), and it means **a component that reads "blue" in dark reads "black" in light** —
never rely on `primary` to signal *blueness*. Use `tone="blue"` for that.

`--background` and `--card` are the same white in light mode; separation there comes
entirely from `--border`. In dark mode the card lifts 3.1% above the ground.

Global base rules in `globals.css`:

```css
* { @apply border-border; }                       /* every border defaults to the token */
body { @apply bg-background text-foreground font-sans antialiased; }
```

### Semantic colors bypass the tokens — on purpose

Priority, status, role, health, and charts use **raw Tailwind palette colors with explicit
`dark:` variants**, not CSS vars. They encode meaning that must stay stable across themes,
and there are more of them than the token set can hold. The formula is fixed:

```
bg-{hue}-100 text-{hue}-700   dark:bg-{hue}-900/40 dark:text-{hue}-300
```

Light: 100 background / 700 text. Dark: 900 at **40% alpha** / 300 text. The alpha is what
keeps dark pills from reading as solid blocks. Any new semantic pill uses this formula.

---

## 3. Color semantics

### Priority — `PRIORITY` in `lib/constants.js`

One shared scale for bugs and tasks (BR-08/09, docs/phase-2/03a-data-model-refactor.md).
Ordered; `order` drives sorting, `hex` is the same hue for charts. Rendered by
`<PriorityBadge>` as a pill with a leading dot.

| Key | Label | Hue | Dot | order |
|---|---|---|---|---|
| `critical` | Critical | red | `bg-red-500` | 0 |
| `high` | High | orange | `bg-orange-500` | 1 |
| `medium` | Medium | amber | `bg-amber-500` | 2 |
| `low` | Low | blue | `bg-blue-400` | 3 |

Red → orange → amber is a heat ramp; blue steps off it because *low* is not "less hot", it's
a different kind of thing. A New or Needs info bug may have no priority — it renders as a grey
"Unrated" pill. Accepting a bug requires a priority; a task starts at `medium` (BR-16). Phase 1's
Blocker became Critical plus the release-blocker flag, which has its own red "Blocker" badge.

There is no Urgent flag, marker or filter (removed in v2.2). "Do this first" is a pin in the
personal queue (slice 10).

### Type — `TYPE` in `lib/constants.js`

Bug or task (slice 03, docs/phase-2/03-tasks-and-placement.md). Fixed once an item is created
(BR-07) — never shown as an editable control. Rendered as a small leading `<Icon>` plus the
item's `key` (`BUG-123` / `TASK-124`) on `IssueTable` rows, search results, and the command
palette — see §9 for icon sizing. Board cards (`WorkItemCard`, slice 10) show the key only in their
hover details.

| Key | Label | Icon | Hue |
|---|---|---|---|
| `bug` | Bug | `bug` | red |
| `task` | Task | `check-square` | violet |

### Status — `STATUS` in `lib/constants.js`

The unified status set (docs/phase-2/02-unified-status-model.md), shared by bugs and, from
slice 03, tasks. Rendered by `<StatusBadge>`. Each carries an `icon` (lucide, kebab-case) for
non-pill use.

| Key | Label | Hue | Icon |
|---|---|---|---|
| `new` | New | zinc | `circle` |
| `needs_info` | Needs info | sky | `help-circle` |
| `todo` | To do | zinc | `circle-dashed` |
| `rejected` | Rejected | the reason's hue (see Cycles below); amber fallback | the reason's icon; `undo-2` fallback |
| `in_progress` | In Progress | indigo | `loader` |
| `to_review` | To review | amber | `clock` |
| `in_review` | In Review | amber | `eye` |
| `done` | Done | teal | `shield-check` |
| `blocked` | Blocked | orange | `circle-slash` |
| `cancelled` | Cancelled | zinc (dimmed: `text-zinc-500`) | `x-circle` |

`BOARD_STATUSES` (`todo, rejected, in_progress, to_review, in_review, done, blocked`) is the
board status set; `BOARD_COLUMNS` (`todo, in_progress, to_review, in_review, done, blocked`) is
what a board draws — Rejected cards sit in the To do column (`BOARD_COLUMN_OF`), so the board
gained one column (To review), not two (09a). To review means "the developer delivered it,
waiting for QA"; In review means "QA is checking it". `FIXED_STATUSES` is `to_review, in_review,
done`.
`TRIAGE_STATUSES` (`new, needs_info`) are bug-only and kept off boards — untriaged work never
looks committed. `OPEN_STATUSES` — not `done` and not `cancelled` — is the canonical "still
needs work" set. Use these; do not re-enumerate the lists at a call site.

An item's next statuses come from the API (`IssueResponse.allowed_transitions`, computed by the
backend's Workflow module) — the frontend never hardcodes the status list, it renders what the
API returned. Status movement is unrestricted by product decision (bugs 2026-09-22, tasks
2026-09-23): any status can move to any other status from the sidebar's status control, with no
confirmation dialog and no reason required — including out of `done` and `cancelled`. The one
exception (09a, ADR 0004): nothing enters `rejected` by a move — only **Reject** does, so the
status control never lists it. Tasks are
never offered the bug-only triage statuses (`new`, `needs_info`), so still render
`allowed_transitions` rather than the full `STATUS` list. `CANCEL_REASON` (`lib/constants.js`)
holds the optional `cancel_reason` values: a bug may give any value except `no_longer_needed`, a
task only `no_longer_needed` — `BUG_CANCEL_REASONS` / `TASK_CANCEL_REASONS` give the filtered
lists.

### Backlog categories and technical debt — `CATEGORY_COLOR`, `CATEGORY_ICONS`, `TECH_DEBT` in `lib/constants.js`

Backlog categories are per project (2026-09-28): each has a name, an icon from `CATEGORY_ICONS` (30
lucide names) and a hue from `CATEGORY_COLOR` (12: zinc, slate, stone, emerald, teal, cyan, sky,
indigo, violet, fuchsia, pink, lime — mirrored in `backend/app/db/models/backlog_category.py`). The
set is curated on purpose: free colours break dark mode and collide with the priority/status hues
(no red, orange, amber or blue). Each hue carries `swatch` (the picker dot), `icon` (icon text
colour, light/dark) and `soft` (the icon chip fill). Every project has a fixed **Default** — `inbox`,
zinc, always first.

A category renders as `<BacklogCategoryBadge category>`: a quiet pill, neutral `bg-muted` fill, the
hue only in its icon, so it never competes with the priority and status pills on the same row.
Backlog rows hide the Default badge (most items sit there; the group header already says it). The
category's full colour shows in group headers, pickers and Settings chips. `<BacklogCategoryPicker
categories value onChange>` is a radio group of chips with Default preselected — it's shown only when
the project has more than Default, and never required. `useBacklogCategories(projectId)` (react-query)
feeds every picker; Settings invalidates it after an edit.

The grouped backlog has one group per project category in the project's order (empty ones
included), then `TECH_DEBT_GROUP` — **every** debt task, whatever its category, present only while
"Show technical debt" is on, so it always matches the Technical debt page for that project.

**Settings → Backlog categories** (`components/backlog/BacklogCategoriesTab`, CTO/Admin,
`?tab=backlog&project=`): projects with their category counts → one project's list. The Default row
is locked (lock icon, "Fixed" chip). Other rows have a drag handle (pointer or keyboard), an icon chip
on its soft hue, the name and item count, and Edit/Delete icon buttons. Edit opens the row **in place**
(one at a time): Name with a 40-character counter (validated on blur, duplicates caught
case-insensitively), a Colour radio group of swatches (each named, the selected one ringed and
checked — colour is never the only cue), an Icon grid, and a live preview of the group header and the
badge. Delete asks first — "N items move to Default. Each item's timeline records the move; nobody is
notified." — with a destructive "Delete and move N".

**Technical debt** (`<TechDebtMarker item compact?>`) is stone with a **dashed** border and the
`construction` icon — "recorded, not committed". Stone sits outside every priority, status, type and
role hue. It renders nothing unless `item.is_tech_debt`. Full form ("Debt" + icon) on list rows and
the item header; `compact` (icon only, tooltip) on board cards.

On the timeline both follow the badge rule the status and priority entries use: a category change
reads "changed category [old] → [new]" (or "set category to [badge]") with `<BacklogCategoryBadge>`
built from the snapshot the entry recorded (so a rename or delete never rewrites history); a delete
reads "moved category [old] → [Default] — old was deleted";
and the flag reads "flagged as [Technical debt chip]" / "cleared the [chip]" — the cleared chip
dimmed and struck through, the way the release-blocker entries pair a phrase with their badge.

### Cycles, Rejected and the cycle badge — `CYCLE_REASON` in `lib/constants.js` (08a, 09a)

A **cycle** is one pass of work on an item; every Reject starts the next one with a reason. Since
09a ([ADR 0004](adr/0004-rejected-is-a-status.md)) work that came back has the status **Rejected**
until its developer picks it up — the cycle records where the problem was caught, the status says
what the item is waiting for. There is no Rejected column: the To do column splits into areas
(below).

| Reason | Label (sentence / Cycles tab) | Icon | Hue |
|---|---|---|---|
| `planned` | Planned | `play` | zinc |
| `review` | Rejected in review / Review | `undo-2` | amber |
| `release_qa` | Returned from release QA / Release QA | `rotate-ccw` | orange |
| `production` | Problem on production / Production | `flame` | red |

Amber → orange → red climbs with how far the problem got (item QA, release QA, production). Red is
shared with the release-blocker marker on purpose: both mean "this hurts users now".

**The To do column's areas** (`TODO_AREAS` in `lib/constants.js`, drawn by `DroppableColumn`,
chosen from a prototype 2026-09-30): when anything in the column came back, it splits into three
collapsible groups, top to bottom — **Rejected** (amber, `undo-2`: rejected in review, from To
review / In review), **Returned** (orange, `rotate-ccw`: sent back after Done, from release QA or
production), then **To do** (new work). Each group header is a button (`aria-expanded`) with a
chevron, the area icon and label, and a count chip; the hint ("Sent back from review" / "Sent
back after Done — release QA or production") is its tooltip. Collapsing is per view and not
remembered. The column header adds a summary after its count — "· 2 rejected · 1 returned". A
column with only new work stays a plain list with no group headers. **Cards don't change**: a
Rejected card looks like any To do card (plus the cycle badge it has anyway); the area says why
it's there.

`<RejectedPill item>` (`components/common`) is the Rejected status pill for lists: "Rejected" with
the reason's icon, in the reason's hue (`item.reject_reason`). It replaces `StatusBadge` for
Rejected items in `IssueTable` rows (not on board cards). It's focusable; hover or focus opens a
popover card after 250 ms with the full label and the reason comment, fetched once on demand
(`GET /issues/{id}/timeline/{reject_comment_id}`, react-query). Screen readers get
"Rejected — <full label>".

`<CycleBadge item compact?>` (`components/common`) shows from `cycle_number ≥ 2`, on every status:
`refresh-cw` + the number in zinc, tooltip and screen-reader text "Cycle 2". It sits after the
title on `IssueTable` rows (next to `TechDebtMarker`), beside the key on board cards (`compact`),
and in the sidebar's cycle metrics header. It is how a developer still sees that picked-up work
came back — Rejected only lasts until they move it to In progress. The spec named `repeat`, but
that is `ReportedCount`'s icon on the same cards, so the badge uses `refresh-cw` (↻, as the ADR
writes it).

The reason is an ordinary public comment. On the timeline a move into Rejected — a Reject or a
merge into a Done item — reads like every other status change ("changed status [In Review] →
[Rejected]"), marked by an amber `undo-2` dot instead of the grey status dot; the comment renders
as any other.

The item page's **Cycles** tab (`CycleHistorySection`, bugs and tasks) lists every cycle oldest
first on a rail — a reason dot, "Cycle N", the reason pill, the container (Stream `waves` or release
`package` + version), the reason comment as a quote, and relative stamps: Started (and by whom, for
returns), Picked up, Delivered (first To review or In review — delivered by the assignee at that
moment), Verified, Closed. Empty state: "No cycles yet" — backlog items have none.

**Reject** (`RejectDialog`) is one action on To review, In review and Done items, shown when
`reject` is in `allowed_actions` (Support never sees it). It has two names: **Reject** (`undo-2`)
on To review / In review, **Return** (`rotate-ccw`) on a Done item — it's already out, so it comes
back, matching the board's Returned area. The dialog's title, text and confirm follow the name;
the comment is required and the destructive confirm stays disabled until it has text. The server
decides where it was caught. The sidebar's quick actions follow the flow: To do / Rejected → **Start work**,
In progress → **Send to review** (To review), To review → **Start review** (In review), In review
→ **Mark as done**, plus **Reject** / **Return** where allowed.

### Work item cards and My Work — `WorkItemCard`, `PRIORITY.icon` (slice 10)

One card everywhere (P3): the Stream board, release boards, and My Work's Kanban all render
`WorkItemCard` (`components/common`) inside `DraggableIssueCard`; My Work's list renders the same
component as a row (`layout="row"`). It reads the slim `WorkItemCard` API shape and the full
`IssueResponse` alike.

**By default** a card shows three things: the title (two lines), the project chip (a 2px-radius
square in the project's colour + name, muted), and the **priority glyph** — `PRIORITY[p].icon` in
`PRIORITY[p].text`: Critical `chevrons-up` red, High `chevron-up` orange, Medium `equal` amber,
Low `chevron-down` blue, unrated `minus` zinc; tooltip and screen-reader text "High priority". No
key, no labels, no avatar.

**Markers**, right-aligned before the glyph, appear only when they matter, in this order:

| Marker | When | Look |
|---|---|---|
| Pin | pinned in the owner's queue | `pin` in primary; `lock` when a CTO/Admin pin is locked |
| Reject reason | status Rejected | the `CYCLE_REASON` icon in its pill hue (review amber, release QA orange, production red) |
| `CycleBadge` | `cycle_number ≥ 2` | as in Cycles above |
| `ReportedCount` | `recurrence_count > 1` | violet `repeat ×N` |
| Due | due within 2 days, or overdue | amber `calendar-clock` + "today" / "tomorrow" / "in 2d"; red `calendar-x` "Overdue" |
| `TechDebtMarker` | technical-debt task | compact stone chip |

Each marker has an icon and a tooltip, so none relies on colour alone. `due_state` comes from the
server on queue/board payloads; for `IssueResponse` the card derives it with the same 2-day rule.

**Hover details** open after 400 ms of hover, or on keyboard focus of the card's button, as a
portaled 320px card (the §7 overlay rules, `Escape` closes, hidden while dragging): key + status,
title, then one icon row per fact — pin (and who may unpin), where it came back from with the
Reject comment (fetched lazily, react-query `['timeline-event', id, commentId]`), cycle, reports,
technical debt, full due date, project · container (Stream / release / Backlog), reporter, and age.

**My Work** (`/my-work`, `MyWorkPage`; CTO/Admin also at `/u/:username/work`, linked from the
profile's **Work queue** button). Header: `text-xl font-bold` title ("My Work" or "Name’s work" with
a breadcrumb), "N open · p/4 pinned", then **Reported by me** (own queue only, `/issues?reporter=`),
**History**, and a List / Kanban `Segmented` remembered per user in `localStorage`
(`rw:my-work-view:<id>`, UI preference only). Someone else's queue says the owner will be notified.

- **List:** three sections, each a heading with icon and count chip over a bordered, divided
  `<ol>` — **In progress** (`loader`, read-only), **Pinned** (`pin`, "p of 4 pins · always on
  top"), **Queue** (`list-ordered`, with the default-rule hint). A row: grip handle (a real button,
  `@dnd-kit/sortable` with pointer and keyboard sensors — Space, arrows, Space), the absolute queue
  position (muted, tabular), the row card, a `StatusBadge` (md+), and the pin toggle (`pin` /
  `pin-off`, `aria-pressed`). A locked pin viewed by its owner shows a disabled `lock` toggle whose
  tooltip names who pinned it; a full queue disables Pin with "This queue already has 4 pins —
  unpin one first." Reorders are optimistic, then replaced by the server's order; a drop across the
  pin boundary shows the server's explanation as a toast. Empty sections are a dashed one-liner.
- **Kanban:** the same six columns as project boards (`IssueBoard`, To do areas included); cards
  follow queue order, dragging across columns changes status, and there is no reorder within a
  column (that happens in the list, so both views agree). Done shows the last 7 days.
- **History** (`Sheet`): one line per change — action icon in a muted circle, actor avatar and
  name, "pinned / unpinned / moved", the item's `IssueHoverCard` chip and title, then "#3 → #1 ·
  5m ago". Load more pages 30 at a time. Automatic changes aren't listed.

Inbox: `queue_changed` reads "<actor> pinned / unpinned / moved in your queue <title>" with
"position 3 → 1" in the meta row; `due_soon` / `overdue` have no actor — an amber `hourglass` or
red `alarm-clock` circle stands in for the avatar ("Due within 24 hours:", "Overdue:").

### Release lifecycle and Overdue — `RELEASE_STATUS` in `lib/constants.js` (slice 09)

A release's lifecycle status and its Overdue state are **two different shapes on purpose**: the
status is a filled pill, Overdue is a red *outlined* marker beside it. Overdue is never a status.

| Status | Label | Icon | Hue |
|---|---|---|---|
| `planning` | Planning | `pencil-ruler` | zinc |
| `development` | Development | `code-2` | blue |
| `qa` | QA | `flask-conical` | amber |
| `released` | Released | `rocket` | green |
| `cancelled` | Cancelled | `ban` | zinc, struck through |

`<ReleaseLifecycleBadge status size?>` (`components/releases`) renders the pill.
`<OverdueMarker release>` renders only when the API says `is_overdue`: `border-red-500/80`
outline, red text, `alarm-clock` icon, a tooltip with the passed target date, focusable.
`<ReleaseProgress release>` is a 6px teal bar (green once Released), `role="progressbar"`, with
"N of M done" and the percentage under it — Done ÷ non-cancelled items, "No items yet" when null.
Go/no-go is `<GoNogoBadge>`: Pending (zinc, `circle-dashed`), Go (green, `thumbs-up`), No-go (red,
`thumbs-down`).

**Pages.** `/projects/:slug/releases` (`ReleasesPage`) is one table — release, status + Overdue,
progress, target ship date (ship date once Released), go/no-go — with a `Segmented` filter
(All / Open / Released & cancelled) and a sort (Target date / Progress / Newest + direction), all
in the URL. `/releases` redirects to the active project's list. `/releases/:id`
(`ReleaseDetailPage`): header with the lifecycle badge as a menu of `allowed_transitions`
(`ReleaseLifecycleMenu`; Cancel asks first and says how many open items move to the backlog),
Overdue, Edit, **Ship** (`ship_release` in `allowed_actions`) and delete; tabs Board, Items,
Activity, and Analytics (CTO/Admin only). The page body is full width — no side rail: progress
and dates, `GoNogoPanel bare` (record Go / No-go with an optional note) and the open release
blockers live in a **Details** popover opened from the header (`panel-right-open` icon, 340px,
sections split by rules). The Details button carries the go/no-go badge and, when there are open
blockers, a red count, so both signals stay visible while it's closed. A Released release shows a green
"Shipped … read-only" note, and its board can't be dragged (`IssueBoard readOnly`).
`/projects/:slug/stream` (`StreamPage`) has Board and Items only, no edit/cancel/delete controls.
Both pages share `ContainerWork` (board from `GET /releases/{id}/board`, items table).

**Ship dialog** (`ShipDialog`) is built from `GET /releases/{id}/ship-preview`: the go/no-go badge
(with an inline red warning on a no-go — shipping is still allowed), "N Done items will be on
production", the not-Done counts as `StatusBadge`s, and a confirm button that says what moves
("Ship and move 4 items to the backlog"). A toast confirms the ship.

**Time range picker** (`ui/DateTimeRangePicker`, ported from llmeter): a Kibana-style filter in
one popover. **Quick select** lists relative presets (calendar icon, check on the active one), a
"Last N days" row with its own Apply, and **Custom time range ›**, which swaps the popover to a
Start / End summary (the side the next click sets is outlined), a `ui/RangeCalendar` (click the
start day, then the end day; days between are tinted, hovering previews the range, today has a
ring) and two `TimeField`s (24-hour `HH:mm`, typed freely — "930" → 09:30 — ↑/↓ step 15 minutes),
with Cancel / Apply, pre-filled from the current range. No end day means "until now". Never use
the browser's native `date` / `datetime-local` controls for this — they ignore the theme. The trigger shows "Last 7 days", or a custom range as
`2026-09-23 14:59 → 2026-09-30 14:59` in mono. Values are `{ days }` or `{ from, to }` (local
`YYYY-MM-DDTHH:mm`). The Stream board's Done column uses it through `common/DoneRangePicker`
(presets 7 / 30 / 90 days, "Done:" prefix); the range is in the URL (`?done=30d` or
`?done_from=&done_to=`) and shared by the **Board and Items** tabs — the picker sits at the right end of the
Stream page's tab row (not inside a tab), so it stays put when the tab changes; only Done items are bounded, open (and cancelled) items always show.

**Activity** (`ReleaseActivity`): oldest first on a rail (the release's story, top to bottom), one icon dot per event — **created**
(zinc `flag`, "created the release · Planning"; always the first entry), lifecycle moves named for what
they mean ("started development", "started QA — code freeze", "moved it back to development",
"released it", "cancelled the release"; blue, with from → to badges), dates and edits (zinc), item added (teal) / removed (zinc, with why:
ship, cancel, production return), go/no-go (violet), shipped (green).

**Container badge** (`common/ContainerBadge`): where an item lives, on the item page's header
line for bugs and tasks alike — a 24px rounded pill that links to the container. Stream: sky,
`waves`, "Stream". Release: `package`, mono version and a small `ReleaseLifecycleBadge`
("v2.4.1 · QA"). Backlog: dashed zinc outline, `inbox`, "Backlog" (not planned yet). The title
attribute says it in words. Reads `container_kind`, `release_version`, `release_status` and
`project_slug` from `IssueResponse`.

**Navigation.** The sidebar lists **Stream** (`waves`) above **Releases** (`tag`), both for the
active project. The topbar `ReleaseSwitcher` lists the Stream first (a link to its page), then open
releases, then closed ones under "Closed". The inbox renders release-only notices
(`release_shipped`, `release_overdue`) with a rocket or outlined alarm-clock avatar and a link to
the release.

### Role — `ROLE` in `lib/constants.js`

`support` teal · `qa` blue · `developer` violet · `pm` amber · `cto` rose · `admin` zinc.
Rendered by `<RoleBadge>`. The label for `pm` is "Project manager".

Route access keys off role, not off the badge. `lib/roles.js` holds the role-level gates
(slice 04, PRD §7.3):

- **Support** (`isSupport`) gets a minimal `Sidebar` (Inbox, Support reports, and profile —
  New report is the button on Support reports), no project/release switchers, search, New issue button, command
  palette, or `c` / ⌘K shortcuts. `<TechRoute>` in `App.jsx` sends Support from any tech-only
  screen to `homePath(role)` (`/inbox`).
  `ProfilePage` shows its engineering stats (metric cards, priority breakdown, and the
  Activity/Assigned/Reported tabs) only when both the profile owner and the viewer have a tech
  role. Support only reports, so a Support profile shows the header, the Reported card, and
  the Reported tab (plus Edit profile, Security, and Telegram on its own profile).
- `ADMIN_ROLES = ['admin', 'cto']` still gates the Reports section in `Sidebar`, the Settings
  link in `Topbar`, and `<AdminRoute>`. Inside Settings, managing users and projects is
  **Admin only** (`canManageUsersAndProjects`); a CTO sees those controls disabled with a
  tooltip rather than hidden.

**Per-item permissions never key off role in the UI.** Every `IssueResponse` carries
`allowed_actions` and `blocked_actions` (`{action, code, detail}`) from
`backend/app/policy.py`. Render item controls through `<ActionButton action item>` (or
`actionState(item, action)` for non-button controls). An allowed action is enabled. A blocked
one is disabled, with the Policy's `detail` as its tooltip. An action in neither list is
hidden, which is how Support never sees tech-only controls such as the internal-note toggle.

**Support intake (slice 05).** Support files from **New report**, a `Dialog` (`size="lg"`,
`components/support/SupportReportModal`) that mirrors New issue: the same `ProjectSwitcher`, a
"What's wrong?" template chooser (radio cards for 2+ templates, a fixed chip for one), then
Title, the template's questions, an optional description, and a compact attachments row
(`AttachmentsSection compact`). `/support/new` opens it over `/support/reports`
(`SupportReportsPage`; only Support has it in the nav, though the route works for every role).
Questions render through `TemplateFields` — a two-column grid, long text and date-and-time
span both columns — validated on blur and on submit (focus jumps to the first error).
Closing with unsaved input asks "Discard this report?". A `template_inactive` 409 keeps every
value on screen under an amber banner. Similar reports (slice 14) go in the
`data-slot="similar-reports"` slot right under the title.

CTO and Admin manage templates in **Settings → Support intake** (`SupportIntakeTab`), not
under Projects — template management and project management have different permissions.
Three linkable levels via `?project=&template=`: every project with its intake status
("Accepting reports" while a template is live) and template count → that project's template
cards (Live/Off, question count, `⋯` menu: Edit, Duplicate, Turn off/Make live) → the
editor (`TemplateEditor`): compact question rows, one expanded at a time, drag to reorder,
**Add question** adds a short-text question whose answer type is changed in the row with
the `Select`, options as chips, and a live preview rendered by the same `TemplateFields`.
The Live switch is part of the draft (one Save), new and duplicated templates start Off, and
turning off a project's last live template asks first. Projects rows show a template-count
chip that links to the project's templates. A support-sourced item shows `<SourceBadge
source>` (Support teal, headset icon) in the triage queue and `IssueTable`.

**Triage** (`pages/TriagePage.jsx`, slice 06): a queue with **New** and **Needs info** `Tabs`
(count badges), oldest first, each row showing key, `SourceBadge`, `<ReportedCount>` when reported more than once, "filed 3h ago", and the reporter. The detail pane has a
**Move to project** dropdown (disabled while the bug has a release) and
`components/triage/TriageOutcomePanel`: four outcome buttons — Accept, Needs info,
Duplicate, Reject — each opening one small form with exactly its inputs (priority chips,
assignee and release `Select`s; a required question; the same-project `DuplicatePicker`;
a reject-reason `Select`). A `duplicate_of_duplicate` refusal shows an amber inline notice
with "Use BUG-n instead". While an item is in Needs info, the item page pins the triager's
question above the tabs (`issues/NeedsInfoQuestion`, orange, `role="note"`).

**Backlog** (`pages/BacklogPage.jsx`, `/projects/:slug/backlog`, slice 08): a ranked list in one
card — never a board. Header: "N items · M untouched for over 6 months" (the stale part amber with a
`clock`), and a "Technical debt in this project" button. Toolbar: a `Segmented` Grouped / Ranked
(`?view=ranked`) and a "Show technical debt" `Switch` (`?debt=1`) with an "N hidden" count.
`components/backlog/`: `BacklogGroupHeader` (collapsible, icon + label + count, a tri-state
`Checkbox` selecting the group), `BacklogRow` (grip handle that appears on hover/focus, checkbox,
rank number in Ranked view, key, title with markers, category, priority, age with a `clock` when
stale, assignee — a dashed circle when unassigned), and `BulkMoveBar` (a floating toolbar that slides
up from the bottom of the scroller while anything is selected: "N selected", release `Select`,
"Move to release", a **Category** menu that moves the whole selection to another category group —
rank kept, the selection's shared category checked, `POST /projects/{id}/backlog/category`, all or
nothing — and "Clear Esc"). Ranking uses `@dnd-kit/sortable` with the pointer and the keyboard
(Space, arrows, Space; announcements name item keys); in Grouped view a drag stays within its group.
The move is optimistic and rolls back with `toast.error` on failure. Shift-click selects a range. A
failed bulk move (`bulk_move_failed`) marks the failing rows with a red left bar and an alert icon
whose tooltip gives the reason. Without `manage_backlog` the handles and checkboxes are disabled
with Policy's reason as the tooltip. The page follows the topbar project switcher. **Technical
debt** (`pages/TechDebtPage.jsx`, `/tech-debt`) is a full-bleed table with `MultiSelectFilterDropdown`
projects, Status (Open / Done / Cancelled / All) and Assignee filters in the URL, and a Placement
column (release version or a "Backlog" chip). New Task has a Technical debt `Switch` and, when the
project has more than Default, an optional `BacklogCategoryPicker`, and starts in the backlog;
Triage's Accept shows the same optional picker; the item sidebar has Category (the project's
categories) and (tasks) Tech debt rows. Placement everywhere — New issue, triage Accept, the
sidebar's Placement row, the bulk bar — is one `ContainerPicker` (08a).

`Select` and `Dropdown` open upward when there's no room below. `Select` and `Dropdown` are
`position: fixed` portals, so both follow their trigger when the page scrolls or resizes
and close once the trigger leaves the viewport.

`lib/markdown.js` honours backslash escapes (`\*` renders a literal `*`) and renders `---` as
a rule — the support report description relies on both.

A project whose triage lead is missing or deactivated (`needs_triage_lead`) shows
`<NeedsTriageLeadBadge>` (amber) in the project switcher and Settings → Projects. Settings also
shows an amber banner above the list while any project needs a lead.

### Badge tones — `Badge.jsx`

`default` (zinc) · `blue` · `green` · `amber` · `red` · `purple` · `zinc` (dimmer than
default) · `orange`. Use a tone only when no priority/status/role token fits.

### MetricCard tones — `MetricCard.jsx`

`default` · `blue` · `green` · `amber` · `red` · `purple`. Each maps to two classes: an
icon-chip fill and a delta-pill fill.

### Health & trend

Health dots: `bg-green-500` / `bg-amber-500` / `bg-red-500` at `h-2.5 w-2.5`
(`h-2 w-2` when small). Trend arrows: `↑` green, `↓` red, `−` zinc-400.

### Charts (Recharts)

Fills are literal hex, chrome is tokens:

```jsx
<CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
<XAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
<Tooltip contentStyle={{
  borderRadius: 8, fontSize: 12,
  border: '1px solid hsl(var(--border))',
  backgroundColor: 'hsl(var(--card))',
}} />
<Bar dataKey={dataKey} fill={color} radius={[3, 3, 0, 0]} />
```

Rules: horizontal grid only, no axis or tick lines, 11px ticks, bars rounded on top only,
default height 180px in `<ResponsiveContainer>`, tooltip inherits card + border tokens so
it survives the theme flip. Series palette in use — `#ef4444` red, `#f59e0b` amber,
`#6366f1` indigo (default), `#3b82f6` blue, `#f97316` orange, `#22c55e`/`#10b981` green,
`#8b5cf6` violet, `#14b8a6` teal, `#ec4899` pink, `#6b7280` grey. Match the series hue to
the semantic hue whenever the series *is* a priority or status.

Empty chart state is text, not a blank frame:
`<div className="h-[180px] flex items-center justify-center text-sm text-muted-foreground">`.

### User color

Avatars fall back to `user.avatar_color`, default `#6366f1`. `getContrastColor()` in
`lib/colors.js` picks `#000000`/`#ffffff` against any user- or label-chosen hex using a
0.5 luminance threshold — use it for any text placed on arbitrary user color.

---

## 4. Typography

Three families, declared in `tailwind.config.js`:

```js
sans: ['Inter', 'Vazir', 'system-ui', 'sans-serif']
mono: ['JetBrains Mono', 'Menlo', 'monospace']
```

- **Inter** — all UI. Loaded from Google Fonts in `frontend/index.html` at weights
  400/500/600/700.
- **Vazir** — Persian fallback, self-hosted from `/fonts/` via `@font-face` in
  `globals.css` at weights 100/300/400/500/700, all `font-display: swap`. It sits *after*
  Inter, so it only renders glyphs Inter lacks.
- **JetBrains Mono** — identifiers and machine text. Weights 400/500/600.

Use `font-mono` for: issue IDs (`issue-123`), release versions, keyboard shortcut `<kbd>`,
cURL/code blocks, and toast targets. Never for prose.

### Scale in use

| Class | Where |
|---|---|
| `text-3xl font-bold tracking-tight` | MetricCard value — the only display-sized type |
| `text-2xl font-bold` | Login wordmark, release version on detail |
| `text-xl font-bold` | Page `<h1>` on dashboard-style pages |
| `text-lg font-semibold` | Page `<h1>` on list-style pages |
| `text-base font-semibold` | Dialog title |
| `text-sm` | Body, nav items, buttons (md/lg), menu items |
| `text-[13px]` | Table body — the dense-table size |
| `text-xs` | Labels, metadata, badges, descriptions, sm buttons |
| `text-[11.5px]` / `text-[11px]` | Mono issue IDs, label chips |
| `text-[10.5px]` | Table column headers |

`text-xs` (377 uses) and `text-sm` (227) carry the app; everything larger is an exception.
Pick from this table rather than inventing a step.

### Weight

`font-medium` is the default for interactive and labeled text (261 uses). `font-semibold`
for card and section titles (157). `font-bold` only for page `<h1>` and metric values (41).
`font-normal` is effectively unused — plain body text inherits.

### Eyebrow labels

`text-xs font-medium text-muted-foreground uppercase tracking-wider` — used for MetricCard
labels and collapsible sidebar section headers **only**. Table headers use a tighter
variant: `text-[10.5px] uppercase tracking-wide text-muted-foreground`.

### Form labels

Always: `block text-xs font-medium text-muted-foreground mb-1.5`
(`mb-2` when the control below is a wrapping chip group). Required fields append
`<span className="text-destructive">*</span>`. Field errors render below as
`mt-1 text-xs text-destructive`.

---

## 5. Layout & spacing

### Shell — `AppShell.jsx`

```
<div className="flex h-screen bg-background">
  <Sidebar />                          {/* w-56, hidden below lg, border-r, bg-card */}
  <div className="flex flex-1 flex-col min-w-0">
    <Topbar />                          {/* h-12 shrink-0, border-b, bg-card */}
    <main className="flex-1 overflow-y-auto scrollbar-thin"><Outlet /></main>
  </div>
</div>
```

The **page never scrolls — `<main>` does.** Anything that must stay put (table headers,
dialog headers/footers) uses `sticky` or `shrink-0` inside that scroller, not `position: fixed`.
`min-w-0` on the content column is load-bearing: without it, wide tables blow out the flex row.

### Page container

```jsx
<div className="p-6 space-y-6 max-w-{N}xl mx-auto">
  <div>
    <h1 className="text-xl font-bold">Title</h1>
    <p className="text-sm text-muted-foreground mt-1">Subtitle</p>
  </div>
  {/* sections */}
</div>
```

Width is chosen by content type: `max-w-7xl` dashboards and analytics · `max-w-6xl`
releases, contributions · `max-w-5xl` team and settings (ten tabs need the width). Full-bleed (no
`max-w`) for the dense list pages — Issues, Triage, Deleted — where table width
is the point.

### Spacing scale

`gap-2` is the default (128 uses); `gap-1`/`gap-1.5` for icon-plus-label pairs; `gap-3`
for form fields and button rows; `gap-4` for card grids; `gap-6` for major sections.
Vertically, `space-y-6` between page sections, `space-y-4` within a section,
`space-y-0.5` between nav items. Lay siblings out with flex/grid + `gap` — do not stack
per-element margins.

Metric grids: `grid grid-cols-2 lg:grid-cols-4 gap-4`. MetricCard carries `min-h-[160px]`
so a row stays even when one card has no description.

### Responsive

One breakpoint does the real work: `lg` (1024px). Below it the sidebar is hidden
(`hidden lg:flex`) and `Topbar` swaps in a hamburger that opens a full-screen overlay
carrying the project and release switchers. `sm` and `md` only trim labels down to icons
("New issue" → `+`). There is no tablet-specific layout.

---

## 6. Radius, borders, elevation

| Radius | Applied to |
|---|---|
| `rounded-full` (121) | Badges, pills, avatars, dots, nav count bubbles, switch |
| `rounded-xl` (67) | Cards, dialogs, toasts, MetricCard, chart frames, Empty icon chip |
| `rounded-lg` (89) | Nav items, segmented control, search field, dropdown panels, icon chips |
| `rounded-md` (49) | Small buttons, close buttons, segmented items |
| `rounded-[var(--radius)]` | Button, Input, Select trigger — the token-bound 8px |

Cards are always `rounded-xl border border-border bg-card text-card-foreground shadow-sm`.

Elevation ladder: `shadow-sm` resting surfaces and default/destructive buttons ·
`shadow-md` tooltips · `shadow-lg` dropdowns, select panels, toasts · `shadow-2xl` dialog
panel. Separation comes from `border-border` first, shadow second — dark mode leans almost
entirely on the border.

### Z-index ladder

`z-50` dialog root, tooltip, mobile menu overlay · `z-[100]` portaled dropdowns, select
panels, toast stack. Overlays that must clear a dialog get `z-[100]`; nothing else does.

---

## 7. Components

### Primitives — `components/ui/`

| Component | API |
|---|---|
| `Button` | `variant`: `default` · `outline` · `ghost` · `destructive` · `secondary` · `link`; `size`: `sm` (h-8) · `md` (h-9) · `lg` (h-10) · `icon` (9×9) · `icon-sm` (8×8); `loading` renders a spinner and disables |
| `Badge` | `tone` (8 values) |
| `PriorityBadge` / `StatusBadge` / `RoleBadge` | take the raw key, fall back to a plain `<Badge>` on an unknown key; `PriorityBadge` renders "Unrated" for `null` |
| `Card` | `Card` · `CardHeader` · `CardTitle` · `CardDesc` · `CardBody` |
| `Input` / `Textarea` | `error` flips border and ring to destructive |
| `Select` / `SelectItem` | portaled, checkmark on selection |
| `Dropdown` | `DropdownItem` (`icon`, `destructive`) · `DropdownSep` · `DropdownLabel`; `align`, `width` |
| `Dialog` | `size`: `sm` · `md` · `lg` · `xl` · `full` |
| `Sheet` | Right-side drawer |
| `Tabs` | Underline style, optional `icon` and `badge` per option; `role="tablist"`/`tab`. Labels never wrap — a row that doesn't fit scrolls sideways and keeps the active tab in view |
| `Segmented` | Pill toggle group inside a `bg-muted` track |
| `Tooltip` | 300ms open delay (also opens on focus), `side`: top · bottom · left · right; `wrapperClassName` sizes the hover wrapper (e.g. `flex w-full`) |
| `Toast` | `ToastProvider` + `useToast()`; max 3 stacked, 4000ms default |
| `Empty` | `icon` · `title` · `body` · children slot for a CTA |
| `Avatar` / `AvatarGroup` | `size` in px; group overlaps −8px, `max` then `+N` |
| `Switch` · `Slider` · `Calendar` · `DatePicker` · `Popover` · `Icon` | — |
| `IssueHoverCard` (`components/common`) | A work item's key as a chip link — type icon in its hue + mono key (`issueId`, `label`) that shows its card on hover or focus — key, status, priority, source, title, assignee, project. Fetched on first hover. The item-side twin of `UserHoverCard`; use it wherever copy names another item |
| `UserPicker` (`components/common`) | Single-select person picker with search by full name or username (`@username` shown per row); `users`, `value` (id or null), `onChange`, `emptyLabel` (default "Unassigned"; falsy makes a choice required). Arrow keys + Enter, Escape closes. Use it wherever a list of people is long enough to scan |
| `ActionButton` / `GatedButton` (`components/common`) | `ActionButton`: `action` + `item`, see §3 Role. `GatedButton`: `allowed` + `reason`, for role-level gates. Both render a disabled `Button` inside a focusable wrapper so the tooltip still opens |

| `Checkbox` (`components/ui`) | `checked`, `indeterminate` ("mixed"), `onCheckedChange(next, event)` — the event carries `shiftKey` for ranges; clicks don't bubble, so it sits inside clickable rows |
| `TechDebtMarker` / `BacklogCategoryBadge` / `BacklogCategoryPicker` (`components/common`) | See §3 Backlog category and technical debt. The picker is a `radiogroup` of chips (arrow keys move), `required` stops a second click from clearing it |
| `ContainerPicker` (`components/common`) | Where an item lives (08a): Backlog (`inbox`), Stream (`waves`, "ships when Done"), then the project's open releases (`package`, lifecycle status as a muted hint). `projectId`, `value` (container id or null = backlog), `onChange`, `allowBacklog` (false in the bulk bar), `allowStream` (false with `allowBacklog` for a releases-only picker). Data from `useContainers(projectId)` (react-query, shared). A released or cancelled current container is still listed so the trigger can name it |
| Item placement (`IssueSidebar`, `MoveDialog` in `components/issues`) | Chosen from a prototype, 2026-09-30. **Sidebar:** in a release, a **Release** row styled like the Project row — the mono version as a text trigger (underline on hover) opening a "Move to release" dropdown of open releases with their lifecycle and "Current", confirm before moving; in the Stream or the backlog, a read-only **Placement** row showing the `ContainerBadge` pill (the same one as under the title, no extra hint), tooltip "Use Move… in the ⋯ menu"; a Done item's placement is the pill too, anywhere (it never moves). The **Category** row shows only in the backlog — it's the backlog category. **Move…** in the header's ⋯ menu (open items, `edit_item` allowed) opens `MoveDialog`: one `radiogroup` of destinations, the current one left out — Backlog ("not planned yet") and Stream ("ships when Done") first, then a separator and a **Releases · open only** group of open releases (mono version + lifecycle hint), or "No other open release in this project." Choosing Backlog reveals an optional **Backlog category** `Select` (empty = the project's Default). A release blocker leaving its release gets a one-line note. Move is disabled until a destination is chosen; the dialog closes when the PATCH succeeds |
| `RejectedPill` / `CycleBadge` / `RejectDialog` / `CycleHistorySection` | See §3 Cycles, Rejected and the cycle badge |
| `ReportedCount` (`components/common`) | `count` — `repeat` icon + `×N` in violet, tooltip and screen-reader text "Reported N times"; renders nothing at 1. The one way lists show `recurrence_count`: inline after the title in `IssueTable` and Support reports rows, beside the key on board cards and in the triage queue. Never a column — most rows would read 1. Violet matches recurrence timeline entries and stays clear of the Rejected pill's amber→red scale and the priority pills |
| `ReportRecurrenceButton` / `RecurrenceDialog` (`components/issues`) | The Report recurrence control for one bug (slice 07): `item`, `onReported(updatedItem)`, `compact` (icon-only with tooltip, for table rows). State and reason come from `report_recurrence` in the item's `allowed_actions` / `blocked_actions`; on a Done bug it's disabled with the FR-16 text and offers "New report referencing this" (Support → `/support/new?ref=<key>`, tech → New issue prefilled via `setNewIssueDraft`). Recurrence timeline entries are comment cards in violet with a `repeat` icon, no edit/delete/reactions |
Compose from these. A new one-off panel that is really a card, a dialog, or an empty state
should use the primitive rather than re-declaring the classes.

### Overlay convention

`Dropdown` and `Select` both: render into `document.body` via `createPortal`, position
`fixed` from `getBoundingClientRect()` with `top: rect.bottom + 4`, clamp to the viewport
with **12px padding** on both edges, and close on outside `mousedown` and on `Escape`.
Any new floating panel follows the same four rules — an absolutely-positioned menu inside
the scrolling `<main>` will clip.

### Loading, empty, error — all three, every time

- **Loading:** skeleton when the shape is known (`IssueTableSkeleton` mirrors the real
  table's columns and widths, `bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse`);
  spinner (`animate-spin rounded-full border-2 border-border border-t-primary`) for route
  and auth transitions; `<Loader2 className="animate-spin">` inline in the topbar.
- **Empty:** `<Empty>` for a whole view; a centered `py-12 text-center text-sm
  text-muted-foreground` line for a filtered-to-nothing table.
- **Error:** `toast.error(title, body?)` — never a bare `console.error` as the only user-visible
  outcome.

---

## 8. Motion

All keyframes live in `globals.css`. Signature easing for entrances is
`cubic-bezier(0.16, 1, 0.3, 1)`; exits use `ease-in`.

| Animation | Duration | Easing |
|---|---|---|
| `toast-slide-in` / `-out` | 250ms / 200ms | signature / ease-in |
| `sheet-slide-in` / `-out` | 300ms / 250ms | signature / ease-in |
| `dialog-in` (fade + scale 0.95 + −8px) | 200ms | signature |
| `timeline-highlight` (amber flash on deep link) | 3s | ease-out, separate light/dark keyframes |
| `reaction-pop` (0.8 → 1.15 → 1) | 180ms | ease-out |
| Switch thumb | 200ms | ease-in-out |

Everything else is `transition-colors` (Tailwind's 150ms default) on hover and focus.
Motion marks state change; it never decorates.

`prefers-reduced-motion: reduce` currently disables `reaction-pop` only — see
[Known drift](#14-known-drift).

---

## 9. Iconography

**lucide-react**, 0.453. Two access paths coexist:

```jsx
import { Search, X } from 'lucide-react'   // 69 files — direct, for static icons
<Icon name="trending-down" size={16} />    // 26 files — wrapper, for dynamic names
```

The `<Icon>` wrapper converts kebab-case to PascalCase, returns `null` on an unknown name,
and warns in dev. **Use `<Icon>` whenever the name is data** (a `STATUS` token's `icon`, a
`NavItem` prop, an `Empty` icon) — that is the only path that survives a name coming from
`constants.js`. Import directly when the icon is hard-coded in the JSX.

Sizes: `size={16}` default and in nav · `size={14}` in tabs · `h-3.5 w-3.5` inside buttons
and dense rows · `h-4 w-4` in menu items and dialog close · `size={22}` in the Empty chip.
Always `shrink-0` on an icon inside a flex row.

---

## 10. Code conventions

**Exports.** Named exports for every component *except* pages, which use `export default`
(they are lazy-loaded in `App.jsx`).

**Barrels.** `ui/`, `common/`, `layout/`, `issues/`, `project/`, `releases/`, `team/` each
have an `index.js`. Deep imports (`../components/ui/Button`) are common in existing pages
and both work — prefer the barrel for multi-import call sites.

**`cn()` always.** Every `className` that is conditional or accepts an override goes
through `cn()` from `lib/cn.js` (clsx + tailwind-merge). Components take a trailing
`className` prop and pass it **last** into `cn()` so callers can override.

**Directory rules.**

| Directory | Holds |
|---|---|
| `components/ui/` | Generic, app-agnostic primitives. No domain knowledge, no API calls. |
| `components/common/` | Cross-page, domain-aware widgets — IssueTable, MetricCard, charts, switchers |
| `components/issues/`, `project/`, `releases/`, `team/` | Feature-scoped, including that feature's modals |
| `components/layout/` | Shell only |
| `pages/` | One default-exported component per route |

**`forwardRef`** on anything that wraps a focusable element — currently `Button` and
`Input`.

**Routing.** `BrowserRouter` (path-based) from `main.jsx`. Routes are `lazy()` +
`<Suspense>` with a spinner `PageFallback`. Three guards wrap route elements:
`ProtectedRoute`, `AdminRoute` (`admin`/`cto` only), `PublicRoute`.

**Filter state lives in the URL.** `IssuesPage` reads every filter and sort from
`useSearchParams` and writes back with `{ replace: true }`, omitting defaults so a clean
view has a clean URL. New list views do the same — filters must survive a refresh and be
shareable. When deriving a fetch payload from search params, depend on
`searchParams.toString()` (a stable primitive), never on a freshly-built object — that is
the documented infinite-loop trap in `IssuesPage`.

**`localStorage` keys are `rw:`-prefixed** — `rw:theme`, `rw:activeProjectId`,
`rw:activeReleaseId`, `rw:token`, `rw:refresh_token`.

**Global state** is `AppContext` (theme, active project/release, auth, modal open flags,
inbox unread count) reached via `useApp()`. Server state is `@tanstack/react-query`
(`retry: 1`, `refetchOnWindowFocus: false`). Do not put fetched lists in `AppContext`
beyond the shell-level projects/releases it already owns.

**Keyboard.** Global handlers in `App.jsx`: `⌘K`/`Ctrl+K` opens the command palette, `c`
opens New Issue (suppressed while focus is in an `input`, `textarea`, or `select`), `Esc`
closes both. Any new global shortcut needs the same input-focus guard.

---

## 11. Copy rules

- **Times** come from `lib/relTime.js` — `relTime()` for anything in a list
  ("just now", "2m ago", "3h ago", "5d ago", "2w ago", then "Jan 5"); `fullTime()` for the
  tooltip on that relative string; `formatDuration(hours)` for spans ("45m", "3h", "2d 4h").
  Never hand-roll a date format.
- **Item identity** is the key (`BUG-123` / `TASK-124`, from `IssueResponse.key` —
  `issueKey()` in `lib/issueSlug.js` for payloads that predate it) in `font-mono
  text-muted-foreground`, preceded by the type icon. Links keep using
  `/issue/<type>-<number>`; old `issue-<n>` links still resolve.
- **Sentence case** for buttons, labels, and menu items — "New issue", "Sign out",
  "Create project". Not Title Case.
- **Real ellipsis** `…`, not three dots: "Search issues…", "Loading dashboard…".
- **Em dash `—`** for a missing value in a metric or field; lowercase italic
  `unassigned` for an empty assignee.
- **Buttons name the action**, and confirmation copy matches it.
- Errors say what failed in plain terms: "Failed to load dashboard", "No issues match your
  filters." No apologies.

---

## 12. Accessibility

Rules currently held:

- Focus ring is `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`
  (`ring-1` on text inputs and the Select trigger). It is theme-aware via `--ring`.
  Every new interactive element gets one.
- Disabled state is `disabled:pointer-events-none disabled:opacity-50` (inputs use
  `disabled:cursor-not-allowed`).
- Icon-only buttons carry `aria-label` ("Close", "Dismiss").
- `Switch` is a real `role="switch"` + `aria-checked` button. Toggle buttons use
  `aria-pressed`. The toast stack is `aria-live="polite"`. Decorative glyphs are
  `aria-hidden`.
- `Escape` closes every overlay — Dialog, Dropdown, Select, command palette.
- Contrast on user-chosen colors goes through `getContrastColor()`.

See [Known drift](#14-known-drift) for the gaps.

---

## 13. Scrollbars

`.scrollbar-thin` (defined in `globals.css`) on every scroll container: 6px, transparent
track, `--border` thumb that brightens to `--muted-foreground` on hover, plus Firefox
`scrollbar-width`/`scrollbar-color`. Applied to `<main>`, the sidebar nav, dialog bodies,
and select panels.

---

## 14. Known drift

Real inconsistencies in the current code. Fix opportunistically; do not propagate.

1. **Page `<h1>` size splits two ways** — `text-xl font-bold` (Dashboard, Inbox, Releases,
   Team, Settings, Contributions, Regressions) vs `text-lg font-semibold text-foreground`
   (Issues, Triage, Deleted Issues). My Work (slice 10) uses `text-xl font-bold`. It tracks the dashboard/list split, so it
   is defensible, but it is not written down anywhere in code. Treat `text-xl font-bold`
   as the default and the `text-lg` variant as the dense-list exception.
2. **`src/styles/fonts.css` is dead.** Nothing imports it; its `@font-face` blocks are
   duplicated verbatim at the top of `globals.css` (which does the woff2/woff/ttf triple,
   where `fonts.css` stops at woff). Delete it or make `globals.css` `@import` it — right
   now editing the wrong one is a silent no-op.
3. **`CLAUDE.md` says hash-based routing.** `main.jsx` uses `BrowserRouter`. The only hash
   left is `window.location.hash = '/login'` in `AppContext.logout()`, which is a stale
   full-page-reload escape hatch inside a path-routed app.
4. **`CLAUDE.md` lists a `design-prototype/` directory** that no longer exists, and a
   `hooks/useTweaks.js` + `components/dev/TweaksPanel` that are not in `src/`.
5. **`Dialog` has no `role="dialog"`, no `aria-modal`, no focus trap, and no
   focus restore.** It closes on `Escape` and on backdrop click only. This is the largest
   a11y gap in the codebase.
6. **`IssueTable` rows are clickable `<tr onClick>`** with no `tabIndex`, key handler, or
   `role="button"` — the rows are unreachable by keyboard.
7. **`prefers-reduced-motion` covers `reaction-pop` only.** The toast, sheet, dialog, and
   3-second timeline-highlight animations all ignore it.
8. **`Icon.jsx` reads `process.env.NODE_ENV`** in a Vite app; the idiomatic guard is
   `import.meta.env.DEV`.
9. **`kebabToPascal` is duplicated** in `ui/Icon.jsx` and `ui/Tabs.jsx`.
10. **`Sidebar` imports `cn`, `ProjectSwitcher`, `activeProjectId` and `switchProject`
    and uses none of them** — leftovers from when the project switcher lived in the
    sidebar rather than the topbar. Lint noise, not a design issue.
