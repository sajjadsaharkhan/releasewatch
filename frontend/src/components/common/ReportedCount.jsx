import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'

/**
 * How many times a bug was reported — the original plus every recurrence and
 * merge (`recurrence_count`, slice 07). Renders nothing at 1, so a list only
 * marks the rows that stand out. One style everywhere it appears (triage
 * queue, issue rows, board cards, Support reports): the `repeat` icon and
 * `×N` in violet — the hue of recurrence entries on the timeline, distinct
 * from the red "regressed" marker and from every priority pill. The icon and
 * number carry the meaning, not the color alone; screen readers get the
 * sentence.
 */
export function ReportedCount({ count, className }) {
  if (!count || count <= 1) return null
  const label = `Reported ${count} times`
  return (
    <Tooltip content={label}>
      <span
        className={cn(
          'inline-flex items-center gap-0.5 shrink-0 text-[11px] font-semibold tabular-nums',
          'text-violet-700 dark:text-violet-300',
          className
        )}
      >
        <Icon name="repeat" size={11} strokeWidth={2.4} aria-hidden="true" />
        <span aria-hidden="true">×{count}</span>
        <span className="sr-only">{label}</span>
      </span>
    </Tooltip>
  )
}
