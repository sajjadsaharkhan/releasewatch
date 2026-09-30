import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'
import { RELEASE_STATUS } from '../../lib/constants'
import { formatDay } from '../../lib/relTime'

// The release lifecycle (FR-50) as a filled pill: icon + label in the status hue.
export function ReleaseLifecycleBadge({ status, size = 'md', className }) {
  const token = RELEASE_STATUS[status]
  if (!token) return null
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full font-medium whitespace-nowrap',
        size === 'sm' ? 'px-1.5 py-px text-[11px]' : 'px-2 py-0.5 text-xs',
        token.pill,
        className,
      )}
      title={token.description}
    >
      <Icon name={token.icon} size={size === 'sm' ? 11 : 12} aria-hidden />
      {token.label}
    </span>
  )
}

// BR-48 — never a status: a red *outlined* marker beside the lifecycle badge,
// shown only when the API says `is_overdue`.
export function OverdueMarker({ release, size = 'md', className }) {
  if (!release?.is_overdue) return null
  const target = formatDay(release.target_date)
  return (
    <Tooltip content={target ? `Target ship date ${target} has passed` : 'Target ship date has passed'}>
      <span
        tabIndex={0}
        className={cn(
          'inline-flex items-center gap-1 rounded-full border font-semibold whitespace-nowrap',
          'border-red-500/80 text-red-600 dark:border-red-500/70 dark:text-red-400',
          size === 'sm' ? 'px-1.5 py-px text-[11px]' : 'px-2 py-0.5 text-xs',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          className,
        )}
      >
        <Icon name="alarm-clock" size={size === 'sm' ? 11 : 12} aria-hidden />
        Overdue
      </span>
    </Tooltip>
  )
}

// BR-47 — Done ÷ non-cancelled items. `progress` is null when nothing counts.
export function ReleaseProgress({ release, showCounts = true, className }) {
  const counts = release?.counts ?? {}
  const done = counts.done ?? 0
  const total = Object.values(counts).reduce((a, b) => a + b, 0) - (counts.cancelled ?? 0)
  const pct = release?.progress == null ? null : Math.round(release.progress * 100)
  return (
    <div className={cn('min-w-0', className)}>
      <div
        role="progressbar"
        aria-label="Release progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct ?? undefined}
        aria-valuetext={pct == null ? 'No items yet' : `${pct}% — ${done} of ${total} done`}
        className="h-1.5 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden"
      >
        <div
          className={cn(
            'h-full rounded-full transition-[width] duration-300',
            release?.status === 'released' ? 'bg-green-500' : 'bg-teal-500',
          )}
          style={{ width: `${pct ?? 0}%` }}
        />
      </div>
      {showCounts && (
        <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground tabular-nums">
          <span>{pct == null ? 'No items yet' : `${done} of ${total} done`}</span>
          {pct != null && <span className="font-medium text-foreground">{pct}%</span>}
        </div>
      )}
    </div>
  )
}
