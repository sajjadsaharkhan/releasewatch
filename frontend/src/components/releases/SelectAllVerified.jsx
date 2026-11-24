import React from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { Icon } from '../ui/Icon'
import { useWorkContext } from '../common/WorkContext'
import { cn } from '../../lib/cn'

/**
 * Verified column header (19, FR-67): one press selects every Verified item the
 * person can mark as on production; pressed again, it clears them. The On
 * production bar then takes over.
 */
export function SelectAllVerified() {
  const { selection } = useWorkContext()
  const reduce = useReducedMotion()
  if (!selection || !selection.total) return null
  const all = selection.selected.size >= selection.total
  const label = all ? 'Clear selection' : `Select all ${selection.total} Verified`
  return (
    <motion.button
      type="button"
      data-testid="select-all-verified"
      data-tour="select-all-verified"
      aria-label={label}
      title={label}
      onClick={all ? selection.clear : selection.selectAll}
      whileTap={reduce ? undefined : { scale: 0.94 }}
      transition={{ type: 'spring', stiffness: 520, damping: 32 }}
      className={cn(
        'ml-auto inline-flex h-[22px] items-center gap-1 rounded-full border px-2 text-[11px] font-medium',
        'transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        all
          ? 'border-primary bg-primary text-primary-foreground'
          : 'border-border bg-background text-muted-foreground hover:border-primary/60 hover:text-foreground',
      )}
    >
      <Icon name={all ? 'x' : 'check-check'} size={12} aria-hidden="true" />
      {all ? 'Clear' : 'Select all'}
    </motion.button>
  )
}
