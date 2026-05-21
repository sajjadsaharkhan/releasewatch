import React from 'react'
import { ChevronDown, Tag, Check, Circle } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dropdown, DropdownItem, DropdownLabel } from '../ui/Dropdown'
import { Badge } from '../ui/Badge'

function getBadgeTone(status) {
  switch (status) {
    case 'active': return 'blue'
    case 'released': return 'green'
    case 'archived': return 'zinc'
    default: return 'default'
  }
}

export function ReleaseSwitcher({ releases = [], activeReleaseId, onChange, compact = false, width = null }) {
  const active = releases.find((r) => r.id === activeReleaseId) ?? releases[0]

  if (!active) {
    return (
      <button
        className={cn(
          'flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-sm font-medium text-muted-foreground',
          'hover:bg-accent transition-colors',
          compact ? 'h-8' : 'w-full'
        )}
        disabled
      >
        <span className="truncate">No releases</span>
      </button>
    )
  }

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
          <Tag className="h-3.5 w-3.5 shrink-0" />
          <span className={cn('font-mono truncate', compact ? 'max-w-[100px]' : 'flex-1 text-left')}>
            {active.version}
          </span>
          {active.status === 'active' && (
            <span className="h-2 w-2 rounded-full shrink-0 bg-green-500" />
          )}
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        </button>
      }
    >
      {({ close }) => (
        <>
          <DropdownLabel>Active release</DropdownLabel>
          {releases.map((r) => (
            <DropdownItem
              key={r.id}
              onClick={() => {
                onChange?.(r.id)
                close()
              }}
            >
              <span className="flex items-center gap-2">
                {r.id === activeReleaseId ? (
                  <Check className="h-4 w-4 shrink-0" />
                ) : (
                  <Circle className="h-4 w-4 shrink-0 opacity-70" />
                )}
                <span className="font-mono">{r.version}</span>
                <Badge tone={getBadgeTone(r.status)}>{r.status}</Badge>
              </span>
            </DropdownItem>
          ))}
        </>
      )}
    </Dropdown>
  )
}