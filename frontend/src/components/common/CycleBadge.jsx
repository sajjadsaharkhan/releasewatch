import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'

/**
 * The cycle badge (09a): the item is past its first pass of work — it was
 * rejected at least once in its current placement. Shown on every status from
 * cycle 2, so a developer who has picked rejected work up still sees it came
 * back. Zinc, `refresh-cw` + the cycle number (`repeat` is ReportedCount's).
 * Renders nothing before cycle 2 or in the backlog.
 */
export function CycleBadge({ item, compact = false, className }) {
  const n = item?.cycle_number
  if (!n || n < 2) return null
  const label = `Cycle ${n}`
  return (
    <Tooltip content={label}>
      <span
        className={cn(
          'inline-flex items-center gap-0.5 shrink-0 font-semibold tabular-nums',
          'text-zinc-500 dark:text-zinc-400',
          compact ? 'text-[10.5px]' : 'text-[11px]',
          className,
        )}
      >
        <Icon name="refresh-cw" size={11} strokeWidth={2.4} aria-hidden="true" />
        <span aria-hidden="true">{n}</span>
        <span className="sr-only">{label}</span>
      </span>
    </Tooltip>
  )
}
