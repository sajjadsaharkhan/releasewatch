import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Icon } from '../ui/Icon'
import { ChevronDown, Tag, Check, Circle, Ship, XCircle, File } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dropdown, DropdownItem, DropdownLabel } from '../ui/Dropdown'
import { Badge } from '../ui/Badge'
import { RELEASE_STATUS } from '../../lib/constants'

function getBadgeTone(status) {
  return RELEASE_STATUS[status]?.tone ?? 'default'
}

function getStatusIcon(status) {
  switch (status) {
    case 'released':
      return <Ship className="h-3 w-3 text-green-600 dark:text-green-400" />
    case 'cancelled':
      return <XCircle className="h-3 w-3 text-zinc-500 dark:text-zinc-400" />
    case 'qa':
      return <Circle className="h-3 w-3 text-amber-600 dark:text-amber-400 fill-amber-600" />
    case 'development':
      return <Circle className="h-3 w-3 text-blue-600 dark:text-blue-400 fill-blue-600" />
    case 'planning':
    default:
      return <Circle className="h-3 w-3 text-zinc-600 dark:text-zinc-400" />
  }
}

function getStatusLabel(status) {
  return RELEASE_STATUS[status]?.label ?? status
}

// The active release is always a Release — never the Stream (08a). When
// `streamHref` is given, the Stream is listed first as a link to its page
// (slice 09), then open releases, then closed ones. `allowNone` lets the caller represent "no release" as a real,
// selectable state; without it, the switcher always shows *some* release
// (falling back to the first one), matching every pre-03 call site (Topbar, etc).
export function ReleaseSwitcher({
  releases = [], activeReleaseId, onChange, compact = false, width = null, allowNone = false,
  streamHref = null, releasesHref = null,
}) {
  const navigate = useNavigate()
  const openReleases = releases.filter((r) => ['planning', 'development', 'qa'].includes(r.status))
  const closedReleases = releases.filter((r) => !openReleases.includes(r))
  const active = releases.find((r) => r.id === activeReleaseId) ?? (allowNone ? null : releases[0])

  const renderItem = (r, close) => (
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
  )

  if (!active && !allowNone && !streamHref) {
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
            {active ? active.version : allowNone ? 'No release' : 'No active release'}
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
          {streamHref && (
            <>
              <DropdownItem onClick={() => { close(); navigate(streamHref) }}>
                <span className="flex items-center gap-2 flex-1">
                  <Icon name="waves" size={16} className="shrink-0 text-sky-600 dark:text-sky-400" />
                  <span>Stream</span>
                  <span className="ml-auto text-[11px] text-muted-foreground">ships when Done</span>
                </span>
              </DropdownItem>
            </>
          )}
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
                <span className="text-muted-foreground">No release</span>
              </span>
            </DropdownItem>
          )}
          {openReleases.map((r) => renderItem(r, close))}
          {!allowNone && openReleases.length === 0 && (
            <div className="px-3 py-2 text-[12px] text-muted-foreground" role="note">
              <p className="flex items-center gap-2">
                <Circle className="h-4 w-4 shrink-0 opacity-40" />
                No active release in this project.
              </p>
              {releasesHref && (
                <button
                  type="button"
                  onClick={() => { close(); navigate(releasesHref) }}
                  className="mt-1.5 ml-6 text-[12px] font-medium text-blue-600 hover:underline dark:text-blue-400"
                >
                  Plan a release →
                </button>
              )}
            </div>
          )}
          {closedReleases.length > 0 && (
            <>
              <DropdownLabel>Closed</DropdownLabel>
              {closedReleases.map((r) => renderItem(r, close))}
            </>
          )}
        </>
      )}
    </Dropdown>
  )
}
