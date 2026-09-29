import React from 'react'
import { Check, Minus } from 'lucide-react'
import { cn } from '../../lib/cn'

/**
 * A token-styled checkbox — `role="checkbox"` with `aria-checked` true, false,
 * or "mixed" (`indeterminate`, for a "select all" over a partial selection).
 * `onCheckedChange(next, event)` passes the event so callers can read
 * `shiftKey` for range selection. Clicks don't bubble, so it can sit inside a
 * clickable row.
 */
export function Checkbox({
  checked = false,
  indeterminate = false,
  onCheckedChange,
  disabled = false,
  className,
  ...props
}) {
  const on = checked || indeterminate
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={indeterminate ? 'mixed' : checked}
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation()
        if (!disabled) onCheckedChange?.(!checked, e)
      }}
      className={cn(
        'inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'disabled:cursor-not-allowed disabled:opacity-50',
        on
          ? 'border-primary bg-primary text-primary-foreground'
          : 'border-input bg-background hover:border-muted-foreground',
        className
      )}
      {...props}
    >
      {indeterminate
        ? <Minus className="h-3 w-3" strokeWidth={3} aria-hidden="true" />
        : checked && <Check className="h-3 w-3" strokeWidth={3} aria-hidden="true" />}
    </button>
  )
}
