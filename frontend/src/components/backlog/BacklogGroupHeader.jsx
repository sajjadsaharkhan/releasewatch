import React from 'react'
import { ChevronRight } from 'lucide-react'
import { cn } from '../../lib/cn'
import { TECH_DEBT, categoryColor } from '../../lib/constants'
import { Checkbox, Icon } from '../ui'

/**
 * A collapsible group header in the grouped backlog (FR-25): the group's icon
 * on its soft hue, label and count, with a chevron. A category group takes its
 * icon and hue from the project's category; the Technical debt group has no
 * category. The checkbox selects every item in the group — "mixed" while only
 * some are. It lines up with BacklogRow's position column.
 */
export function groupMeta(group) {
  if (group.category) {
    const hue = categoryColor(group.category.color)
    return {
      label: group.category.name,
      icon: group.category.icon,
      iconClass: hue.icon,
      softClass: hue.soft,
      isDefault: group.category.is_default,
    }
  }
  return {
    label: TECH_DEBT.label,
    icon: TECH_DEBT.icon,
    iconClass: TECH_DEBT.iconClass,
    softClass: 'bg-stone-100 dark:bg-stone-900/40',
    isDefault: false,
  }
}

export function BacklogGroupHeader({
  group, open, onToggle, count, selectedCount, onSelectAll, canManage,
}) {
  const meta = groupMeta(group)
  const panelId = `backlog-group-${group.key}`
  return (
    <div className="flex items-center gap-3 border-b border-border bg-muted/40 px-3 py-1.5">
      <span className="w-5 shrink-0" />
      <span className="flex w-7 shrink-0 justify-center">
        {canManage && count > 0 && (
          <Checkbox
            checked={selectedCount > 0 && selectedCount === count}
            indeterminate={selectedCount > 0 && selectedCount < count}
            onCheckedChange={(next) => onSelectAll(next)}
            aria-label={`Select every item in ${meta.label}`}
          />
        )}
      </span>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex flex-1 items-center gap-2 rounded-md py-0.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className={cn('flex h-6 w-6 shrink-0 items-center justify-center rounded-md', meta.softClass)}>
          <Icon name={meta.icon} size={13} className={meta.iconClass} aria-hidden="true" />
        </span>
        <span className="text-[12.5px] font-semibold">{meta.label}</span>
        <span className={cn('text-[11.5px] tabular-nums text-muted-foreground', count === 0 && 'opacity-60')}>{count}</span>
        <span className="h-px flex-1 bg-border" />
        <ChevronRight
          className={cn(
            'h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-150 motion-reduce:transition-none',
            open && 'rotate-90',
          )}
          aria-hidden="true"
        />
      </button>
    </div>
  )
}
