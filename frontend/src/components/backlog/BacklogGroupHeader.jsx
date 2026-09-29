import React from 'react'
import { ChevronRight } from 'lucide-react'
import { cn } from '../../lib/cn'
import { TECH_DEBT, categoryColor } from '../../lib/constants'
import { Checkbox, Icon } from '../ui'

/**
 * A collapsible group header in the grouped backlog (FR-25): chevron, the
 * group's icon and label, and its count. A category group takes its icon and
 * hue from the project's category; the Technical debt group has no category.
 * The checkbox selects every item in the group — "mixed" while only some are.
 * Columns line up with BacklogRow's handle and checkbox.
 */
export function groupMeta(group) {
  if (group.category) {
    return {
      label: group.category.name,
      icon: group.category.icon,
      iconClass: categoryColor(group.category.color).icon,
      isDefault: group.category.is_default,
    }
  }
  return { label: TECH_DEBT.label, icon: TECH_DEBT.icon, iconClass: TECH_DEBT.iconClass, isDefault: false }
}

export function BacklogGroupHeader({
  group, open, onToggle, selectedCount, onSelectAll, canManage,
}) {
  const meta = groupMeta(group)
  const count = group.count
  const panelId = `backlog-group-${group.key}`
  return (
    <div className="flex h-9 items-center gap-2 border-b border-border bg-muted/40 px-2">
      <span className="w-5 shrink-0" />
      <span className="flex w-5 shrink-0 justify-center">
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
        className={cn(
          'flex flex-1 items-center gap-2 rounded-md py-1 text-left text-[12.5px] font-semibold text-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
        )}
      >
        <ChevronRight
          className={cn(
            'h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-150 motion-reduce:transition-none',
            open && 'rotate-90'
          )}
          aria-hidden="true"
        />
        <Icon name={meta.icon} size={14} className={cn('shrink-0', meta.iconClass)} aria-hidden="true" />
        <span>{meta.label}</span>
        <span
          className={cn(
            'rounded-full border border-border bg-background px-1.5 text-[10.5px] font-medium tabular-nums text-muted-foreground',
            count === 0 && 'opacity-60'
          )}
        >
          {count}
        </span>
      </button>
    </div>
  )
}
