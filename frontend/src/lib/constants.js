// Priority (BR-08/09, docs/phase-2/03a-data-model-refactor.md) — one shared
// scale for bugs and tasks, highest first. `order` drives sorting; `hex` is
// the same hue for charts. A New or Needs info bug may have no priority
// (rendered "Unrated"); a task starts at medium (BR-16). `icon` + `text` are the
// compact priority glyph on WorkItemCard (slice 10).
export const PRIORITY = {
  critical: {
    label: 'Critical',
    icon: 'chevrons-up',
    text: 'text-red-600 dark:text-red-400',
    pill: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    dot: 'bg-red-500',
    hex: '#ef4444',
    order: 0,
  },
  high: {
    label: 'High',
    icon: 'chevron-up',
    text: 'text-orange-600 dark:text-orange-400',
    pill: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
    dot: 'bg-orange-500',
    hex: '#f97316',
    order: 1,
  },
  medium: {
    label: 'Medium',
    icon: 'equal',
    text: 'text-amber-600 dark:text-amber-400',
    pill: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    dot: 'bg-amber-500',
    hex: '#f59e0b',
    order: 2,
  },
  low: {
    label: 'Low',
    icon: 'chevron-down',
    text: 'text-blue-600 dark:text-blue-400',
    pill: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    dot: 'bg-blue-400',
    hex: '#3b82f6',
    order: 3,
  },
}

export const PRIORITIES = Object.keys(PRIORITY)

// A new task's priority (BR-16).
export const TASK_DEFAULT_PRIORITY = 'medium'

// docs/phase-2/03-tasks-and-placement.md — type icon + key prefix on every
// row/card, search result, and command palette entry (§3 in docs/design.md).
// No pill here: the type renders icon-only (TypeIcon), never as a filled badge.
export const TYPE = {
  bug: { label: 'Bug', icon: 'bug' },
  task: { label: 'Task', icon: 'check-square' },
}

// Bug-only surfaces (BR-08): environment, reproduction steps, cURL, release
// blocker, regression. A missing type is a bug, same as the backend default.
export const isBug = (item) => (item?.type ?? 'bug') === 'bug'

// "bug" / "task" — the noun for UI copy about one item.
export const itemNoun = (item) => (isBug(item) ? 'bug' : 'task')

// Containers (08a, PRD v3 §8.1): every project has one Stream (always open,
// each item ships on its own when Done) and any number of Releases. An item's
// `release_id` points at either; null is the backlog.
export const CONTAINER_KIND = {
  stream: { label: 'Stream', icon: 'waves' },
  release: { label: 'Release', icon: 'package' },
  backlog: { label: 'Backlog', icon: 'inbox' },
}

// Release lifecycle (PRD v3 §8.7, FR-50). The Stream has no status. "Blocked" is
// not a status — it's a release in QA with a no-go decision. `pill` is the
// filled lifecycle badge (<ReleaseLifecycleBadge>); Overdue is never a status —
// it's the separate red *outlined* <OverdueMarker> (slice 09).
export const RELEASE_STATUS = {
  planning: {
    label: 'Planning', tone: 'zinc', icon: 'pencil-ruler', description: 'Scope is being decided',
    pill: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
  },
  development: {
    label: 'Development', tone: 'blue', icon: 'code-2', description: 'Work is in progress',
    pill: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  },
  qa: {
    label: 'QA', tone: 'amber', icon: 'flask-conical', description: 'Code freeze — release-level QA',
    pill: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  },
  released: {
    label: 'Released', tone: 'green', icon: 'rocket', description: 'Shipped to production',
    pill: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
  },
  cancelled: {
    label: 'Cancelled', tone: 'zinc', icon: 'ban', description: 'Will not ship',
    pill: 'bg-zinc-100 text-zinc-500 line-through decoration-zinc-400/60 dark:bg-zinc-800 dark:text-zinc-500',
  },
}
// How a manual lifecycle move reads as a menu item (FR-50). Released is Ship's.
export const RELEASE_TRANSITION_LABEL = {
  development: { planning: 'Start development', qa: 'Back to development' },
  qa: { development: 'Start QA (code freeze)' },
  cancelled: { '*': 'Cancel release' },
}
export const releaseTransitionLabel = (from, to) =>
  RELEASE_TRANSITION_LABEL[to]?.[from] ?? RELEASE_TRANSITION_LABEL[to]?.['*'] ?? RELEASE_STATUS[to]?.label ?? to
export const RELEASE_STATUSES = Object.keys(RELEASE_STATUS)
// Releases that still take items — Released and Cancelled are closed (`release_closed`).
export const OPEN_RELEASE_STATUSES = ['planning', 'development', 'qa']
export const isOpenRelease = (release) => OPEN_RELEASE_STATUSES.includes(release?.status)

// Cycles (08a, docs/phase-2/cycle-model.md §3): why a pass of work started.
// Every Reject (09a) lands the item in Rejected; the reason says where it was
// caught and colors the Rejected pill. `short` is the Cycles tab's word; `label`
// the sentence form.
export const CYCLE_REASON = {
  planned: {
    label: 'Planned', short: 'Planned', icon: 'play',
    pill: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
  },
  review: {
    label: 'Rejected in review', short: 'Review', icon: 'undo-2',
    pill: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  },
  release_qa: {
    label: 'Returned from release QA', short: 'Release QA', icon: 'rotate-ccw',
    pill: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300',
  },
  production: {
    label: 'Problem on production', short: 'Production', icon: 'flame',
    pill: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  },
}

// docs/phase-2/02-unified-status-model.md — shared by bugs and (slice 03) tasks.
// Board statuses: todo, rejected, in_progress, to_review, in_review, done, blocked.
// Triage statuses (bug-only, kept off boards): new, needs_info.
// No terminal status: any status can move to any other (tasks: never new/needs_info),
// except that only Reject enters `rejected` (09a) — it's never in allowed_transitions.
// A Rejected item's pill takes its reason's hue (`RejectedPill`); `pill` here is
// the fallback for places that only know the status.
export const STATUS = {
  new: {
    label: 'New',
    pill: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
    icon: 'circle',
  },
  needs_info: {
    label: 'Needs info',
    pill: 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300',
    icon: 'help-circle',
  },
  todo: {
    label: 'To do',
    pill: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
    icon: 'circle-dashed',
  },
  rejected: {
    label: 'Rejected',
    pill: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
    icon: 'undo-2',
  },
  in_progress: {
    label: 'In Progress',
    pill: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
    icon: 'loader',
  },
  to_review: {
    label: 'To review',
    pill: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300',
    icon: 'clock',
  },
  in_review: {
    label: 'In Review',
    pill: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
    icon: 'eye',
  },
  done: {
    label: 'Done',
    pill: 'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300',
    icon: 'shield-check',
  },
  blocked: {
    label: 'Blocked',
    pill: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
    icon: 'circle-slash',
  },
  cancelled: {
    label: 'Cancelled',
    pill: 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500',
    icon: 'x-circle',
  },
}

export const BOARD_STATUSES = ['todo', 'rejected', 'in_progress', 'to_review', 'in_review', 'done', 'blocked']
// The board's columns (09a): Rejected cards sit in the To do column
// (`BOARD_COLUMN_OF`) — the board gains one column, To review, not two.
export const BOARD_COLUMNS = ['todo', 'in_progress', 'to_review', 'in_review', 'done', 'blocked']
export const BOARD_COLUMN_OF = { rejected: 'todo' }

// The To do column's areas, top to bottom (09a): work rejected in review,
// work returned after Done (release QA or production), then new work. Each is
// a collapsible group; the column only shows groups when something came back.
export const TODO_AREAS = [
  { key: 'rejected', label: 'Rejected', icon: 'undo-2', hint: 'Sent back from review',
    text: 'text-amber-700 dark:text-amber-300',
    match: (i) => i.status === 'rejected' && (i.reject_reason ?? 'review') === 'review' },
  { key: 'returned', label: 'Returned', icon: 'rotate-ccw', hint: 'Sent back after Done — release QA or production',
    text: 'text-orange-700 dark:text-orange-300',
    match: (i) => i.status === 'rejected' && (i.reject_reason === 'release_qa' || i.reject_reason === 'production') },
  { key: 'todo', label: 'To do', icon: 'circle-dashed', hint: 'New work',
    text: 'text-zinc-600 dark:text-zinc-300',
    match: (i) => i.status !== 'rejected' },
]
export const TRIAGE_STATUSES = ['new', 'needs_info']

// "Fixed" — delivered: to_review, in_review or done (09a). Use this everywhere
// a "has this been fixed" count is computed; do not re-enumerate the set at a
// call site.
export const FIXED_STATUSES = ['to_review', 'in_review', 'done']

// Cancel reasons (BR-13), optional for both types. Bugs: any of these except
// `no_longer_needed`. Tasks: `no_longer_needed` only.
export const CANCEL_REASON = {
  user_error: 'User error',
  expected_behavior: 'Expected behavior',
  cannot_reproduce: 'Cannot reproduce',
  duplicate: 'Duplicate',
  wont_fix: "Won't fix",
  no_longer_needed: 'No longer needed',
}

export const BUG_CANCEL_REASONS = Object.keys(CANCEL_REASON).filter((r) => r !== 'no_longer_needed')
export const TASK_CANCEL_REASONS = ['no_longer_needed']

// Statuses that still need work — not done and not cancelled.
export const OPEN_STATUSES = ['new', 'needs_info', 'todo', 'rejected', 'in_progress', 'to_review', 'in_review', 'blocked']

// Backlog categories (2026-09-28) are per project, managed in Settings → Backlog
// categories (CTO/Admin). Each has a name, an icon from CATEGORY_ICONS and a hue
// from CATEGORY_COLOR — both curated and mirrored in
// backend/app/db/models/backlog_category.py. Every project has a fixed Default
// (inbox, zinc), always first. Class strings are written out in full so
// Tailwind keeps them.
export const CATEGORY_ICONS = [
  'inbox', 'sparkles', 'trending-up', 'telescope', 'rocket', 'lightbulb',
  'wrench', 'gauge', 'shield-check', 'lock', 'palette', 'layout-grid',
  'smartphone', 'globe', 'database', 'server', 'zap', 'heart',
  'star', 'flag', 'target', 'puzzle', 'book-open', 'users',
  'message-square', 'bell', 'bar-chart-3', 'bug-off', 'accessibility', 'search',
]

export const CATEGORY_COLOR = {
  zinc:    { label: 'Grey',    swatch: 'bg-zinc-500',    icon: 'text-zinc-500 dark:text-zinc-400',       soft: 'bg-zinc-100 dark:bg-zinc-800' },
  slate:   { label: 'Slate',   swatch: 'bg-slate-500',   icon: 'text-slate-600 dark:text-slate-400',     soft: 'bg-slate-100 dark:bg-slate-900/40' },
  stone:   { label: 'Stone',   swatch: 'bg-stone-500',   icon: 'text-stone-600 dark:text-stone-400',     soft: 'bg-stone-100 dark:bg-stone-900/40' },
  emerald: { label: 'Emerald', swatch: 'bg-emerald-500', icon: 'text-emerald-600 dark:text-emerald-400', soft: 'bg-emerald-100 dark:bg-emerald-900/40' },
  teal:    { label: 'Teal',    swatch: 'bg-teal-500',    icon: 'text-teal-600 dark:text-teal-400',       soft: 'bg-teal-100 dark:bg-teal-900/40' },
  cyan:    { label: 'Cyan',    swatch: 'bg-cyan-500',    icon: 'text-cyan-600 dark:text-cyan-400',       soft: 'bg-cyan-100 dark:bg-cyan-900/40' },
  sky:     { label: 'Sky',     swatch: 'bg-sky-500',     icon: 'text-sky-600 dark:text-sky-400',         soft: 'bg-sky-100 dark:bg-sky-900/40' },
  indigo:  { label: 'Indigo',  swatch: 'bg-indigo-500',  icon: 'text-indigo-600 dark:text-indigo-400',   soft: 'bg-indigo-100 dark:bg-indigo-900/40' },
  violet:  { label: 'Violet',  swatch: 'bg-violet-500',  icon: 'text-violet-600 dark:text-violet-400',   soft: 'bg-violet-100 dark:bg-violet-900/40' },
  fuchsia: { label: 'Fuchsia', swatch: 'bg-fuchsia-500', icon: 'text-fuchsia-600 dark:text-fuchsia-400', soft: 'bg-fuchsia-100 dark:bg-fuchsia-900/40' },
  pink:    { label: 'Pink',    swatch: 'bg-pink-500',    icon: 'text-pink-600 dark:text-pink-400',       soft: 'bg-pink-100 dark:bg-pink-900/40' },
  lime:    { label: 'Lime',    swatch: 'bg-lime-500',    icon: 'text-lime-600 dark:text-lime-400',       soft: 'bg-lime-100 dark:bg-lime-900/40' },
}
export const CATEGORY_COLORS = Object.keys(CATEGORY_COLOR)
export const categoryColor = (hue) => CATEGORY_COLOR[hue] ?? CATEGORY_COLOR.zinc
export const CATEGORY_NAME_MAX = 40
export const CATEGORY_LIMIT = 20

// The grouped backlog's last group — every technical-debt task, whatever its category.
export const TECH_DEBT_GROUP = 'tech_debt'

// Technical debt marker (slice 08, BR-36/37) — stone with a dashed border:
// "recorded, not committed". Stays clear of every priority/status/type hue.
export const TECH_DEBT = {
  label: 'Technical debt',
  short: 'Debt',
  icon: 'construction',
  chip: 'border border-dashed border-stone-400/70 text-stone-600 bg-stone-50 dark:border-stone-500/60 dark:text-stone-300 dark:bg-stone-900/40',
  iconClass: 'text-stone-500 dark:text-stone-400',
}

// Mirrors UserRole (backend/app/db/models/user.py). Tech roles = everyone but support
// (lib/roles.js); per-item permissions come from the API's allowed_actions, not from here.
export const ROLE = {
  support: {
    label: 'Support',
    pill: 'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300',
  },
  qa: {
    label: 'QA',
    pill: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  },
  developer: {
    label: 'Developer',
    pill: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
  },
  product_manager: {
    label: 'Product Manager',
    pill: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  },
  cto: {
    label: 'CTO',
    pill: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300',
  },
  admin: {
    label: 'Admin',
    pill: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
  },
}
