import React from 'react'
import { cn } from '../../lib/cn'
import { categoryColor } from '../../lib/constants'
import { Icon } from '../ui/Icon'

/**
 * A backlog category (`{name, icon, color}` — the item's `backlog_category`, a
 * picker entry, or a timeline snapshot) as a quiet pill: neutral fill, the hue
 * lives in the icon, so it sits beside priority and status pills without
 * shouting (2026-09-28). Renders nothing without a category.
 */
export function BacklogCategoryBadge({ category, className }) {
  if (!category) return null
  return (
    <span
      className={cn(
        'inline-flex max-w-[180px] shrink-0 items-center gap-1 rounded-full bg-muted px-2 h-5 text-[11px] font-medium text-foreground/80',
        className
      )}
    >
      <Icon
        name={category.icon}
        size={11}
        aria-hidden="true"
        className={cn('shrink-0', categoryColor(category.color).icon)}
      />
      <span className="truncate">{category.name}</span>
    </span>
  )
}
