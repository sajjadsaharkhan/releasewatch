import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'

// PD-1 (19): the Phase 1 report numbers predate cycles, Verified and
// "Done = on production". The notice is text only and can't be dismissed.
export function Phase1ReportNotice({ className }) {
  return (
    <div
      role="note"
      data-testid="pd1-notice"
      className={cn(
        'flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-[12.5px] text-amber-800',
        'dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300',
        className,
      )}
    >
      <Icon name="triangle-alert" size={13} className="shrink-0" aria-hidden="true" />
      These numbers are not reliable since Phase 2 and will be rebuilt (PD-1).
    </div>
  )
}
