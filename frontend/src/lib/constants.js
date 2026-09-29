// Priority (BR-08/09, docs/phase-2/03a-data-model-refactor.md) — one shared
// scale for bugs and tasks, highest first. `order` drives sorting; `hex` is
// the same hue for charts. A New or Needs info bug may have no priority
// (rendered "Unrated"); a task starts at medium (BR-16).
export const PRIORITY = {
  critical: {
    label: 'Critical',
    pill: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    dot: 'bg-red-500',
    hex: '#ef4444',
    order: 0,
  },
  high: {
    label: 'High',
    pill: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
    dot: 'bg-orange-500',
    hex: '#f97316',
    order: 1,
  },
  medium: {
    label: 'Medium',
    pill: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    dot: 'bg-amber-500',
    hex: '#f59e0b',
    order: 2,
  },
  low: {
    label: 'Low',
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

// Release lifecycle (PRD v3 §8.7). The Stream has no status. "Blocked" is not
// a status — it's a release in QA with a no-go decision.
export const RELEASE_STATUS = {
  planning:    { label: 'Planning',    tone: 'zinc',  description: 'Scope is being decided' },
  development: { label: 'Development', tone: 'blue',  description: 'Work is in progress' },
  qa:          { label: 'QA',          tone: 'amber', description: 'Code freeze — release-level QA' },
  released:    { label: 'Released',    tone: 'green', description: 'Shipped to production' },
  cancelled:   { label: 'Cancelled',   tone: 'zinc',  description: 'Will not ship' },
}
export const RELEASE_STATUSES = Object.keys(RELEASE_STATUS)
// Releases that still take items — Released and Cancelled are closed (`release_closed`).
export const OPEN_RELEASE_STATUSES = ['planning', 'development', 'qa']
export const isOpenRelease = (release) => OPEN_RELEASE_STATUSES.includes(release?.status)

// Cycles (08a, docs/phase-2/cycle-model.md §3): why a pass of work started.
// Every return sends the item to To do; the reason says where it was caught.
// `short` is the returned marker's word; `label` the sentence form.
export const CYCLE_REASON = {
  planned: {
    label: 'Planned', short: 'Planned', icon: 'play',
    pill: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
  },
  review: {
    label: 'Rejected in review', short: 'Rejected', icon: 'undo-2',
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
// Board statuses: todo, in_progress, in_review, done, blocked.
// Triage statuses (bug-only, kept off boards): new, needs_info.
// No terminal status: any status can move to any other (tasks: never new/needs_info).
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
  in_progress: {
    label: 'In Progress',
    pill: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
    icon: 'loader',
  },
  in_review: {
    label: 'In Review',
    pill: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
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

export const BOARD_STATUSES = ['todo', 'in_progress', 'in_review', 'done', 'blocked']
export const TRIAGE_STATUSES = ['new', 'needs_info']

// "Fixed" — in_review or done (docs/phase-2/02-unified-status-model.md). Use
// this everywhere a "has this been fixed" count is computed; do not
// re-enumerate the pair at a call site.
export const FIXED_STATUSES = ['in_review', 'done']

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
export const OPEN_STATUSES = ['new', 'needs_info', 'todo', 'in_progress', 'in_review', 'blocked']

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
  pm: {
    label: 'Project manager',
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
