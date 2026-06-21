export const SEVERITY = {
  blocker: {
    label: 'Blocker',
    pill: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    dot: 'bg-red-500',
    order: 0,
  },
  critical: {
    label: 'Critical',
    pill: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    dot: 'bg-orange-500',
    order: 1,
  },
  major: {
    label: 'Major',
    pill: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    dot: 'bg-amber-500',
    order: 2,
  },
  minor: {
    label: 'Minor',
    pill: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    dot: 'bg-blue-400',
    order: 3,
  },
  enhancement: {
    label: 'Enhancement',
    pill: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
    dot: 'bg-purple-400',
    order: 4,
  },
}

export const STATUS = {
  new: {
    label: 'New',
    pill: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
    icon: 'circle',
  },
  triaged: {
    label: 'Triaged',
    pill: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400',
    icon: 'tag',
  },
  in_progress: {
    label: 'In Progress',
    pill: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
    icon: 'loader',
  },
  fixed: {
    label: 'Fixed',
    pill: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    icon: 'check-circle',
  },
  verified: {
    label: 'Verified',
    pill: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
    icon: 'shield-check',
  },
  closed: {
    label: 'Closed',
    pill: 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500',
    icon: 'x-circle',
  },
  regression: {
    label: 'Regression',
    pill: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    icon: 'trending-down',
  },
}

export const ROLE = {
  qa: {
    label: 'QA',
    pill: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  },
  developer: {
    label: 'Developer',
    pill: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  },
  triage_lead: {
    label: 'Triage Lead',
    pill: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  },
  cto: {
    label: 'CTO',
    pill: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400',
  },
  admin: {
    label: 'Admin',
    pill: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
  },
}
