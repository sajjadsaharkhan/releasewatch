import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui'
import { groupMeta } from './BacklogGroupHeader'

/** The rail's "Show" filters. They hide rows, so dragging to rank is off while one is on. */
export const BACKLOG_FILTERS = {
  all: { label: 'All', icon: 'list', test: () => true },
  high: { label: 'High priority', icon: 'chevrons-up', test: (i) => i.priority === 'critical' || i.priority === 'high' },
  stale: { label: 'Stale', icon: 'clock', test: (i, stale) => stale.has(i.id) },
  unassigned: { label: 'Unassigned', icon: 'user-x', test: (i) => !i.assignee_user },
}

function RailItem({ on, onClick, icon, iconClass, label, n }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[12.5px] transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        on ? 'bg-accent font-medium text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      <Icon name={icon} size={14} className={iconClass} aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span className="text-[11.5px] tabular-nums">{n}</span>
    </button>
  )
}

function RailLabel({ children }) {
  return (
    <p className="mb-1 mt-4 px-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground first:mt-0">
      {children}
    </p>
  )
}

/**
 * Left rail (prototype N3): pick one category and one "Show" filter. Both live
 * in the URL (`?category=`, `?show=`). Counts come from the loaded list.
 */
export function BacklogRail({ groups, total, counts, filter, onFilter, category, onCategory }) {
  return (
    <aside aria-label="Backlog filters" className="shrink-0 md:w-52">
      <RailLabel>Category</RailLabel>
      <RailItem on={category === 'all'} onClick={() => onCategory('all')} icon="layers" label="All categories" n={total} />
      {groups.map((g) => {
        const m = groupMeta(g)
        return (
          <RailItem
            key={g.key}
            on={category === g.key}
            onClick={() => onCategory(g.key)}
            icon={m.icon}
            iconClass={m.iconClass}
            label={m.label}
            n={g.count}
          />
        )
      })}
      <RailLabel>Show</RailLabel>
      {Object.entries(BACKLOG_FILTERS).map(([k, f]) => (
        <RailItem
          key={k}
          on={filter === k}
          onClick={() => onFilter(k)}
          icon={f.icon}
          label={f.label}
          n={k === 'all' ? total : counts[k]}
        />
      ))}
    </aside>
  )
}
