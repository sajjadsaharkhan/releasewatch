import React from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { cn } from '../../lib/cn'

// Press feedback on a spring; the tick draws itself in. Both are skipped under
// reduced motion — the state still changes, nothing moves.
const PRESS = { type: 'spring', stiffness: 520, damping: 32 }
const DRAW = { duration: 0.22, ease: [0.22, 1, 0.36, 1] }

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
  const reduce = useReducedMotion()
  return (
    <motion.button
      type="button"
      role="checkbox"
      aria-checked={indeterminate ? 'mixed' : checked}
      disabled={disabled}
      whileTap={disabled || reduce ? undefined : { scale: 0.88 }}
      transition={PRESS}
      onClick={(e) => {
        e.stopPropagation()
        if (!disabled) onCheckedChange?.(!checked, e)
      }}
      className={cn(
        'inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border transition-[background-color,border-color,box-shadow] duration-150',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'disabled:cursor-not-allowed disabled:opacity-50',
        on
          ? 'border-primary bg-primary text-primary-foreground'
          : 'border-input bg-background hover:border-muted-foreground',
        className
      )}
      {...props}
    >
      <svg viewBox="0 0 16 16" className="h-[75%] w-[75%]" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {indeterminate ? (
          <motion.path key="minus" d="M3.5 8h9" initial={reduce ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={DRAW} />
        ) : checked ? (
          <motion.path key="tick" d="M3 8.6l3.3 3.2L13 4.6" initial={reduce ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={DRAW} />
        ) : null}
      </svg>
    </motion.button>
  )
}
