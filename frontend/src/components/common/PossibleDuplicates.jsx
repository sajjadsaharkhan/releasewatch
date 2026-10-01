import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'

/**
 * "Possible duplicate" — a New bug with stored duplicate hints (slice 14,
 * FR-S12, AC-S10). Renders nothing at 0, the way ReportedCount does. Amber:
 * something to check before accepting, not a verdict. The icon and number
 * carry the meaning; screen readers get the sentence.
 */
export function PossibleDuplicates({ count, className }) {
  if (!count || count <= 0) return null
  const label = count === 1
    ? 'Possible duplicate — check before accepting'
    : `Possible duplicates (${count}) — check before accepting`
  return (
    <Tooltip content={label}>
      <span
        className={cn(
          'inline-flex items-center gap-0.5 shrink-0 text-[11px] font-semibold tabular-nums',
          'text-amber-700 dark:text-amber-300',
          className
        )}
      >
        <Icon name="copy" size={11} strokeWidth={2.4} aria-hidden="true" />
        <span aria-hidden="true">×{count}</span>
        <span className="sr-only">{label}</span>
      </span>
    </Tooltip>
  )
}
