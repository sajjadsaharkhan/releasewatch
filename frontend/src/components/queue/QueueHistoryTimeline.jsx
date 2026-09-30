import React from 'react'
import { cn } from '../../lib/cn'
import { formatDay, fullTime, relTime } from '../../lib/relTime'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'
import { IssueHoverCard } from '../common/IssueHoverCard'

// Queue history as a day-grouped timeline (FR-41): who moved, pinned or
// unpinned which item, and the position before → after (green when it went up).
// A change by anyone but the owner is tagged "changed your queue".

export const QUEUE_ACTIONS = {
  reorder: { label: 'Moved', verb: 'moved', icon: 'arrow-up-down', dot: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300' },
  pin: { label: 'Pinned', verb: 'pinned', icon: 'pin', dot: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300' },
  unpin: { label: 'Unpinned', verb: 'unpinned', icon: 'pin-off', dot: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
}

const DAY = 86400000

function dayLabel(iso) {
  const d = new Date(iso); d.setHours(0, 0, 0, 0)
  const t = new Date(); t.setHours(0, 0, 0, 0)
  const diff = Math.round((t - d) / DAY)
  return diff === 0 ? 'Today' : diff === 1 ? 'Yesterday' : formatDay(iso)
}

/** `[{label, rows}]` in order — shared with the Done tab's day groups. */
export function groupByDay(rows, dateOf) {
  const groups = []
  rows.forEach((row) => {
    const label = dayLabel(dateOf(row))
    if (groups.at(-1)?.label !== label) groups.push({ label, rows: [] })
    groups.at(-1).rows.push(row)
  })
  return groups
}

function Movement({ h }) {
  if (h.old_index == null || h.new_index == null || h.old_index === h.new_index) return null
  const up = h.new_index < h.old_index
  return (
    <span className="inline-flex items-center gap-1 font-mono text-[11px] tabular-nums text-muted-foreground" aria-label={`from position ${h.old_index} to ${h.new_index}`}>
      #{h.old_index}
      <span className={cn(
        'inline-flex h-4 w-4 items-center justify-center rounded-full',
        up ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800',
      )}>
        <Icon name={up ? 'arrow-up' : 'arrow-down'} size={10} aria-hidden="true" />
      </span>
      #{h.new_index}
    </span>
  )
}

export function QueueHistoryTimeline({ rows, ownerId }) {
  return (
    <div className="space-y-5">
      {groupByDay(rows, (h) => h.created_at).map((g) => (
        <section key={g.label}>
          <h3 className="mb-2 text-[11px] font-semibold text-muted-foreground">{g.label}</h3>
          <ol className="relative space-y-1 before:absolute before:bottom-2 before:left-[13px] before:top-2 before:w-px before:bg-border">
            {g.rows.map((h) => {
              const action = QUEUE_ACTIONS[h.action]
              // Ids may arrive as number or string (auth context vs API) — compare as text.
              const other = h.actor && ownerId != null && String(h.actor.id) !== String(ownerId)
              return (
                <li key={h.id} className="relative flex items-start gap-3 rounded-lg py-2 pr-2" data-testid="history-item">
                  <span className={cn('relative z-[1] mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-4 ring-card', action.dot)}>
                    <Icon name={action.icon} size={12} aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1 pt-0.5 text-[12.5px] leading-snug">
                    <p className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
                      <span className="inline-flex items-center gap-1 font-medium">
                        {h.actor && <Avatar user={h.actor} size={16} />}{h.actor?.name ?? 'Someone'}
                      </span>
                      <span className="text-muted-foreground">{action.verb}</span>
                      {h.issue_id && <IssueHoverCard issueId={h.issue_id} label={h.issue_key} />}
                      <Movement h={h} />
                      {other && (
                        <span className="rounded-full bg-amber-100 px-1.5 text-[10px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                          changed your queue
                        </span>
                      )}
                    </p>
                    {h.issue_title && <p className="mt-0.5 truncate text-muted-foreground">{h.issue_title}</p>}
                  </div>
                  <time className="shrink-0 pt-1 text-[11px] tabular-nums text-muted-foreground" dateTime={h.created_at} title={fullTime(h.created_at)}>
                    {relTime(h.created_at)}
                  </time>
                </li>
              )
            })}
          </ol>
        </section>
      ))}
    </div>
  )
}
