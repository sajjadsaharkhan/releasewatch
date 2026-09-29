import React from 'react'
import { cn } from '../../lib/cn'
import { categoryColor } from '../../lib/constants'
import { Icon } from '../ui/Icon'

/**
 * Pick one of a project's backlog categories — chips in a radio group, Default
 * first, styled like the priority chips. There's always a choice (Default when
 * nobody picks), so a chip can't be cleared. Arrow keys move between chips.
 */
export function BacklogCategoryPicker({ categories, value, onChange, className, ...props }) {
  const ids = categories.map((c) => c.id)
  const current = value ?? categories.find((c) => c.is_default)?.id

  const onKeyDown = (e) => {
    if (!['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp'].includes(e.key) || ids.length === 0) return
    e.preventDefault()
    const i = Math.max(0, ids.indexOf(current))
    const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : -1
    const next = ids[(i + step + ids.length) % ids.length]
    onChange(next)
    e.currentTarget.querySelector(`[data-value="${next}"]`)?.focus()
  }

  return (
    <div role="radiogroup" onKeyDown={onKeyDown} className={cn('flex flex-wrap gap-1', className)} {...props}>
      {categories.map((c) => {
        const selected = c.id === current
        return (
          <button
            key={c.id}
            type="button"
            role="radio"
            data-value={c.id}
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(c.id)}
            className={cn(
              'flex h-8 max-w-[200px] items-center gap-1.5 whitespace-nowrap rounded-md border px-2.5 text-[11.5px] font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              selected
                ? 'border-foreground bg-foreground text-background dark:border-background dark:bg-background dark:text-foreground'
                : 'border-border bg-background text-muted-foreground hover:bg-muted'
            )}
          >
            <Icon
              name={c.icon}
              size={12}
              aria-hidden="true"
              className={cn('shrink-0', !selected && categoryColor(c.color).icon)}
            />
            <span className="truncate">{c.name}</span>
          </button>
        )
      })}
    </div>
  )
}
