import React from 'react'
import { cn } from '../../lib/cn'
import { CYCLE_REASON, TYPE } from '../../lib/constants'
import { formatDay } from '../../lib/relTime'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'

// The small pieces of a queue row (My Work, slice 10 round 2): type, placement,
// blocker, the coloured report/cycle counts, due and rejected tags. All read
// the `WorkItemCard` API shape. See docs/design.md §3 "My Work".

const DAY = 86400000

/** The pin's own hue — a thumbtack, not a status or priority colour. */
export const PIN_ICON = 'text-yellow-600 dark:text-yellow-400'

/** "today", "5d", "3w", "4mo". */
export function ageOf(iso) {
  const days = Math.floor((Date.now() - new Date(iso)) / DAY)
  if (days < 1) return 'today'
  if (days < 14) return `${days}d`
  if (days < 60) return `${Math.floor(days / 7)}w`
  return `${Math.floor(days / 30)}mo`
}

export function TypeMark({ type, withLabel = false }) {
  const t = TYPE[type] ?? TYPE.bug
  return (
    <span className={cn(
      'inline-flex shrink-0 items-center gap-1',
      type === 'task' ? 'text-violet-600 dark:text-violet-400' : 'text-red-500 dark:text-red-400',
    )}>
      <Icon name={t.icon} size={13} aria-hidden="true" />
      {withLabel
        ? <span className="text-[11.5px] text-foreground/80">{t.label}</span>
        : <span className="sr-only">{t.label}</span>}
    </span>
  )
}

/** Where the item lives: the Stream (sky, `waves`), a release (`package` + version), or the backlog. */
export function PlacementChip({ container }) {
  if (!container) return <span className="text-[11.5px] text-muted-foreground">Backlog</span>
  const stream = container.kind === 'stream'
  return (
    <span className={cn(
      'inline-flex h-5 max-w-full items-center gap-1 rounded-md px-1.5 text-[11px] font-medium',
      stream
        ? 'bg-sky-50 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300'
        : 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
    )}>
      <Icon name={stream ? 'waves' : 'package'} size={11} aria-hidden="true" />
      <span className="truncate">{stream ? 'Stream' : `Release ${container.name}`}</span>
    </span>
  )
}

/** Release blocker: an outlined red pill with a pulsing dot (still under reduced motion). */
export function BlockerBadge({ item }) {
  if (!item.is_release_blocker) return null
  return (
    <Tooltip content="Release blocker — this release can't ship until it's fixed">
      <span className="inline-flex h-5 shrink-0 items-center gap-1.5 rounded-full border border-red-300 bg-red-50 px-2 text-[11px] font-semibold text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">
        <span className="relative flex h-1.5 w-1.5" aria-hidden="true">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-70 motion-reduce:hidden" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-red-600" />
        </span>
        Blocker
      </span>
    </Tooltip>
  )
}

function CountPill({ icon, n, one, many, className }) {
  const value = n || 0
  return (
    <span className={cn('inline-flex h-5 items-center gap-1 rounded-full px-1.5 text-[11px] font-medium tabular-nums', className)}>
      <Icon name={icon} size={11} strokeWidth={2.4} aria-hidden="true" />
      {value} {value === 1 ? one : many}
    </span>
  )
}

/** How many times it was reported — violet, stronger from 2. */
export function ReportsPill({ item }) {
  return (
    <CountPill
      icon="repeat" n={item.recurrence_count} one="report" many="reports"
      className={item.recurrence_count > 1
        ? 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300'
        : 'bg-violet-50 text-violet-600/80 dark:bg-violet-950/30 dark:text-violet-300/70'}
    />
  )
}

/** How many cycles — soft teal for a first pass, amber once it came back. */
export function CyclesPill({ item }) {
  return (
    <CountPill
      icon="refresh-cw" n={item.cycle_count} one="cycle" many="cycles"
      className={item.cycle_count > 1
        ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
        : 'bg-teal-50 text-teal-700/80 dark:bg-teal-950/30 dark:text-teal-300/70'}
    />
  )
}

export function DueTag({ item }) {
  if (!item.due_date) return null
  const over = item.due_state === 'overdue'
  const soon = item.due_state === 'soon'
  return (
    <span className={cn(
      'inline-flex items-center gap-1 text-[11.5px] tabular-nums',
      over ? 'font-semibold text-red-600 dark:text-red-400'
        : soon ? 'font-semibold text-amber-700 dark:text-amber-300' : 'text-muted-foreground',
    )}>
      <Icon name={over ? 'calendar-x' : 'calendar'} size={11} aria-hidden="true" />
      {over ? 'Overdue' : `Due ${formatDay(item.due_date)}`}
    </span>
  )
}

/** Why a Rejected item came back — the reason's short label, icon and hue. */
export function RejectedTag({ item }) {
  if (item.status !== 'rejected') return null
  const r = CYCLE_REASON[item.reject_reason] ?? CYCLE_REASON.review
  return (
    <Tooltip content={r.label}>
      <span className={cn('inline-flex h-5 shrink-0 items-center gap-1 rounded-md px-1.5 text-[11px] font-medium', r.pill)}>
        <Icon name={r.icon} size={11} aria-hidden="true" />{r.short}
      </span>
    </Tooltip>
  )
}

/** One bar per pin slot: filled for each pin, grey for what's left. */
export function PinSlots({ used, limit }) {
  return (
    <span className="inline-flex items-center gap-1" role="img" aria-label={`${used} of ${limit} pins used`}>
      {Array.from({ length: limit }, (_, i) => (
        <span key={i} className={cn('h-1.5 w-4 rounded-full', i < used ? 'bg-yellow-500' : 'bg-zinc-200 dark:bg-zinc-700')} />
      ))}
    </span>
  )
}
