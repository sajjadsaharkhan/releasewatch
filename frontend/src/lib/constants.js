export const SEVERITY = {
  blocker: {
    label: 'Blocker',
    pill: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    dot: 'bg-red-500',
    order: 0,
  },
  critical: {
    label: 'Critical',
    pill: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
    dot: 'bg-orange-500',
    order: 1,
  },
  major: {
    label: 'Major',
    pill: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    dot: 'bg-amber-500',
    order: 2,
  },
  minor: {
    label: 'Minor',
    pill: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    dot: 'bg-blue-400',
    order: 3,
  },
}

// docs/phase-2/02-unified-status-model.md — shared by bugs and (slice 03) tasks.
// Board statuses: todo, in_progress, in_review, done, blocked.
// Triage statuses (bug-only, kept off boards): new, needs_info.
// Terminal: cancelled (and done, except via the regression/merge-regression actions).
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

// Cancel reasons — required when transitioning a bug to cancelled (BR-13).
export const CANCEL_REASON = {
  user_error: 'User error',
  expected_behavior: 'Expected behavior',
  cannot_reproduce: 'Cannot reproduce',
  duplicate: 'Duplicate',
  wont_fix: "Won't fix",
  no_longer_needed: 'No longer needed',
}

// Statuses that still need work — not done and not cancelled.
export const OPEN_STATUSES = ['new', 'needs_info', 'todo', 'in_progress', 'in_review', 'blocked']

export const ROLE = {
  qa: {
    label: 'QA',
    pill: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  },
  developer: {
    label: 'Developer',
    pill: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
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
