import React from 'react'
import { ChevronDown, Tag, Check, Circle, Ship, XCircle, File } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dropdown, DropdownItem, DropdownLabel } from '../ui/Dropdown'
import { Badge } from '../ui/Badge'

function getBadgeTone(status) {
  switch (status) {
    case 'active': return 'blue'
    case 'released': return 'green'
    case 'blocked': return 'red'
    case 'archived': return 'zinc'
    default: return 'default'
  }
}

function getStatusIcon(status) {
  switch (status) {
    case 'released':
      return <Ship className="h-3 w-3 text-green-600 dark:text-green-400" />
    case 'blocked':
      return <XCircle className="h-3 w-3 text-red-600 dark:text-red-400" />
    case 'active':
      return <Circle className="h-3 w-3 text-blue-600 dark:text-blue-400 fill-blue-600" />
    case 'archived':
    default:
      return <Circle className="h-3 w-3 text-zinc-600 dark:text-zinc-400" />
  }
}

function getStatusLabel(status) {
  switch (status) {
    case 'active': return 'Active'
    case 'released': return 'Released'
    case 'blocked': return 'Blocked'
    case 'archived': return 'Archived'
    default: return status
  }
}

// `allowNone` (03, BR-26): lets the caller represent "no release" as a real,
// selectable state — a bug filed with no release is a hotfix, not an error.
// Without it, the switcher always shows *some* release (falling back to the
// first one), matching every pre-03 call site (Topbar, etc).
export function ReleaseSwitcher({
  releases = [], activeReleaseId, onChange, compact = false, width = null, allowNone = false,
}) {
  const active = releases.find((r) => r.id === activeReleaseId) ?? (allowNone ? null : releases[0])

  if (!active && !allowNone) {
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
            compact ? 'h-8' : 'w-full',
            !active && 'text-muted-foreground'
          )}
        >
          <Tag className="h-3.5 w-3.5 shrink-0" />
          <span className={cn('font-mono truncate', compact ? 'max-w-[100px]' : 'flex-1 text-left')}>
            {active ? active.version : 'No release'}
          </span>
          {active && (
            <div className="flex items-center">
              {getStatusIcon(active.status)}
            </div>
          )}
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        </button>
      }
    >
      {({ close }) => (
        <>
          <DropdownLabel>{allowNone ? 'Release' : 'Active release'}</DropdownLabel>
          {allowNone && (
            <DropdownItem
              onClick={() => {
                onChange?.(null)
                close()
              }}
            >
              <span className="flex items-center gap-2 flex-1">
                {!active ? (
                  <Check className="h-4 w-4 shrink-0" />
                ) : (
                  <Circle className="h-4 w-4 shrink-0 opacity-70" />
                )}
                <span className="text-muted-foreground">No release (hotfix)</span>
              </span>
            </DropdownItem>
          )}
          {releases.map((r) => (
            <DropdownItem
              key={r.id}
              onClick={() => {
                onChange?.(r.id)
                close()
              }}
            >
              <span className="flex items-center gap-2 flex-1">
                {r.id === activeReleaseId ? (
                  <Check className="h-4 w-4 shrink-0" />
                ) : (
                  <Circle className="h-4 w-4 shrink-0 opacity-70" />
                )}
                <span className="font-mono">{r.version}</span>
                <Badge tone={getBadgeTone(r.status)}>{getStatusLabel(r.status)}</Badge>
              </span>
            </DropdownItem>
          ))}
        </>
      )}
    </Dropdown>
  )
}
