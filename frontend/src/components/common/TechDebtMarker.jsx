import React from 'react'
import { cn } from '../../lib/cn'
import { TECH_DEBT } from '../../lib/constants'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'

/**
 * Marks a technical-debt task (`is_tech_debt`, slice 08, BR-37) wherever it
 * shows up — backlog rows, issue rows, board cards, queues. Renders nothing
 * for other items. Stone with a dashed border ("recorded, not committed") so
 * it never reads as a priority or status. `compact` drops the word for tight
 * spots like board cards; the tooltip and screen-reader text still say it.
 */
export function TechDebtMarker({ item, compact = false, className }) {
  if (!item?.is_tech_debt) return null
  return (
    <Tooltip content={TECH_DEBT.label}>
      <span
        className={cn(
          'inline-flex shrink-0 items-center gap-1 rounded-full text-[10.5px] font-medium leading-none',
          compact ? 'h-[18px] w-[18px] justify-center' : 'h-[18px] px-1.5',
          TECH_DEBT.chip,
          className
        )}
      >
        <Icon name={TECH_DEBT.icon} size={11} aria-hidden="true" className={TECH_DEBT.iconClass} />
        {!compact && <span aria-hidden="true">{TECH_DEBT.short}</span>}
        <span className="sr-only">{TECH_DEBT.label}</span>
      </span>
    </Tooltip>
  )
}
