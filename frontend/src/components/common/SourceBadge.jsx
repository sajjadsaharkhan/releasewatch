import React from 'react'
import { cn } from '../../lib/cn'
import { ROLE } from '../../lib/constants'
import { Icon } from '../ui/Icon'

// Marks a support-sourced item (slice 05) in the triage queue and issue rows, so
// the team knows Support is waiting on the answer. Uses the Support role's teal —
// the item came from a Support user. Renders nothing for internal items.
export function SourceBadge({ source, className }) {
  if (source !== 'support') return null
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium shrink-0',
        ROLE.support.pill,
        className
      )}
      title="Reported by Support"
    >
      <Icon name="headset" size={11} aria-hidden />
      Support
    </span>
  )
}
