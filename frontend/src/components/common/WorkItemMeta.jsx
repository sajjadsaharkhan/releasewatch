import React from 'react'
import { cn } from '../../lib/cn'
import { RELEASE_STATUS } from '../../lib/constants'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'

// The extra facts on a board card (variant B, chosen 2026-10-02): where the item
// lives, whether it blocks a release, its labels and its assignee.

const BLOCKER_TIP = "Release blocker — this release can't ship until it's fixed"

export function BlockerPill({ className }) {
  return (
    <Tooltip content={BLOCKER_TIP}>
      <span className={cn('inline-flex h-[18px] shrink-0 items-center gap-1 rounded-full border border-red-300 bg-red-50 px-1.5 text-[10.5px] font-semibold text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300', className)}>
        <span className="h-1.5 w-1.5 rounded-full bg-red-600" aria-hidden="true" />
        Blocker
      </span>
    </Tooltip>
  )
}

/** Stream: sky + waves. Release: package + mono version, a status dot. Backlog: nothing (not on a board). */
export function PlacementChip({ placement, className }) {
  if (!placement) return null
  if (placement.kind === 'stream') {
    return (
      <Tooltip content="In the Stream — ships on its own when Done">
        <span className={cn('inline-flex h-5 min-w-0 items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-1.5 text-[11px] font-medium text-sky-700 dark:border-sky-800/60 dark:bg-sky-950/40 dark:text-sky-300', className)}>
          <Icon name="waves" size={11} aria-hidden="true" />
          Stream
        </span>
      </Tooltip>
    )
  }
  const status = RELEASE_STATUS[placement.status]
  return (
    <Tooltip content={`Release ${placement.name}${status ? ` — ${status.label}` : ''}`}>
      <span className={cn('inline-flex h-5 min-w-0 max-w-full items-center gap-1 rounded-full border border-border bg-card px-1.5 text-[11px] font-medium text-foreground', className)}>
        <Icon name="package" size={11} className="shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="truncate font-mono">{placement.name}</span>
        {status && (
          <Icon name={status.icon} size={10} className="shrink-0 text-muted-foreground" aria-hidden="true" />
        )}
      </span>
    </Tooltip>
  )
}

/** Up to `max` labels as coloured dot + name on one line; the rest fold into "+N". */
export function InlineLabels({ labels, max = 3, className }) {
  if (!labels.length) return null
  return (
    <div className={cn('flex min-w-0 items-center gap-2 overflow-hidden text-[10.5px] text-muted-foreground', className)}>
      {labels.slice(0, max).map((l) => (
        <span key={l.name} className="inline-flex min-w-0 shrink-0 items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: l.color }} aria-hidden="true" />{l.name}
        </span>
      ))}
      {labels.length > max && <span className="shrink-0">+{labels.length - max}</span>}
    </div>
  )
}

export function Assignee({ user, size = 18 }) {
  if (!user) {
    return (
      <Tooltip content="Unassigned">
        <span className="inline-flex shrink-0 items-center justify-center rounded-full border border-dashed border-zinc-300 text-zinc-400 dark:border-zinc-600" style={{ width: size, height: size }}>
          <Icon name="user" size={size - 8} aria-hidden="true" />
          <span className="sr-only">Unassigned</span>
        </span>
      </Tooltip>
    )
  }
  return <Tooltip content={`Assigned to ${user.name}`}><span className="inline-flex"><Avatar user={user} size={size} /></span></Tooltip>
}
