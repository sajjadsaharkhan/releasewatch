import React from 'react'
import { Checkbox } from '../ui/Checkbox'
import { cn } from '../../lib/cn'

/**
 * The On production select control on a Verified Stream card: a round check at
 * the top-right, shown on hover. Once any card is picked every card shows it,
 * and a click anywhere on a card toggles it (WorkItemCard).
 */
export function SelectAffordance({ picked, anyPicked, onToggle, label }) {
  return (
    <Checkbox
      checked={picked}
      onCheckedChange={(_, e) => onToggle(e.shiftKey)}
      aria-label={label}
      className={cn(
        'absolute -right-2 -top-2 z-10 h-[22px] w-[22px] rounded-full border-2 shadow-md',
        'transition-[opacity,transform,background-color,border-color] duration-200 ease-out',
        picked || anyPicked
          ? 'scale-100 opacity-100'
          : 'scale-75 opacity-0 focus-visible:scale-100 focus-visible:opacity-100 group-hover/card:scale-100 group-hover/card:opacity-100',
      )}
    />
  )
}
