import React from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dropdown, DropdownItem } from '../ui/Dropdown'

export function ProjectSwitcher({ projects = [], activeProjectId, onChange, compact = false }) {
  const active = projects.find((p) => p.id === activeProjectId) ?? projects[0]

  return (
    <Dropdown
      trigger={
        <button
          className={cn(
            'flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-sm font-medium',
            'hover:bg-accent transition-colors',
            compact ? 'h-8' : 'w-full'
          )}
        >
          {active && (
            <span
              className="h-2 w-2 rounded-full shrink-0"
              style={{ backgroundColor: active.color }}
            />
          )}
          <span className={cn('truncate', compact ? 'max-w-[120px]' : 'flex-1 text-left')}>
            {active?.name ?? 'Select project'}
          </span>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        </button>
      }
    >
      {projects.map((p) => (
        <DropdownItem
          key={p.id}
          onClick={() => onChange?.(p.id)}
        >
          <span className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: p.color }} />
            {p.name}
          </span>
        </DropdownItem>
      ))}
    </Dropdown>
  )
}
