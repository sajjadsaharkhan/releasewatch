import React from 'react'
import { ChevronDown, Check, Circle, Plus } from 'lucide-react'
import { cn } from '../../lib/cn'
import { getContrastColor } from '../../lib/colors'
import { Dropdown, DropdownItem, DropdownLabel, DropdownSep } from '../ui/Dropdown'

export function ProjectSwitcher({ projects = [], activeProjectId, onChange, compact = false, width = null, onCreateProject }) {
  const active = projects.find((p) => p.id === activeProjectId) ?? projects[0]
  const initials = active?.name?.[0] || '?'
  const contrastColor = getContrastColor(active?.color)

  return (
    <Dropdown
      width={width}
      trigger={
        <button
          className={cn(
            'flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-sm font-medium',
            'hover:bg-accent transition-colors',
            compact ? 'h-8' : 'w-full'
          )}
        >
          {active && (
            <div
              className="h-6 w-6 rounded shrink-0 flex items-center justify-center text-[11px] font-bold"
              style={{ backgroundColor: active.color, color: contrastColor }}
            >
              {initials}
            </div>
          )}
          <span className={cn('truncate', compact ? 'max-w-[120px]' : 'flex-1 text-left')}>
            {active?.name ?? 'Select project'}
          </span>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        </button>
      }
    >
      {({ close }) => (
        <>
          <DropdownLabel>Switch project</DropdownLabel>
          {projects.map((p) => (
            <DropdownItem
              key={p.id}
              onClick={() => {
                onChange?.(p.id)
                close()
              }}
            >
              <span className="flex items-center gap-2">
                {p.id === activeProjectId ? (
                  <Check className="h-4 w-4 shrink-0" />
                ) : (
                  <Circle className="h-4 w-4 shrink-0 opacity-70" />
                )}
                <div className="flex flex-col">
                  <span>{p.name}</span>
                  <span className="text-[10px] text-muted-foreground">{p.desc}</span>
                </div>
              </span>
            </DropdownItem>
          ))}
          <DropdownSep />
          <DropdownItem
            icon={Plus}
            onClick={() => {
              onCreateProject?.()
              close()
            }}
          >
            New project…
          </DropdownItem>
        </>
      )}
    </Dropdown>
  )
}
