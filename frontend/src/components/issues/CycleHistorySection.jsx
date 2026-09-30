import React from 'react'
import { cn } from '../../lib/cn'
import { CONTAINER_KIND, CYCLE_REASON } from '../../lib/constants'
import { relTime } from '../../lib/relTime'
import { Icon } from '../ui/Icon'
import { UserHoverCard } from '../ui/UserHoverCard'

function formatDate(value) {
  if (!value) return null
  return new Date(value).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function Stamp({ label, at }) {
  if (!at) return null
  return (
    <span className="inline-flex items-baseline gap-1">
      <span className="text-muted-foreground">{label}</span>
      <time dateTime={at} title={formatDate(at)} className="font-mono tabular-nums text-foreground/80">{relTime(at)}</time>
    </span>
  )
}

function Person({ user, verb }) {
  if (!user) return null
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-muted-foreground">{verb}</span>
      <UserHoverCard user={user} size={14} />
      <span className="font-medium text-foreground">{user.name}</span>
    </span>
  )
}

/**
 * The item's cycles (08a, FR-66): when each pass started and why, where it
 * lived, who delivered it, and when it was verified. Oldest first; the current
 * cycle is last. `comments` lets a return show the comment that sent it back.
 */
export function CycleHistorySection({ cycles = [], comments = [] }) {
  if (cycles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center mb-3">
          <Icon name={CONTAINER_KIND.backlog.icon} size={18} className="text-muted-foreground" />
        </div>
        <p className="text-sm font-medium text-foreground">No cycles yet</p>
        <p className="text-xs text-muted-foreground mt-1 max-w-xs">
          A cycle starts when the item is placed in the Stream or a release. Items in the backlog have none.
        </p>
      </div>
    )
  }

  const returns = cycles.filter((c) => c.start_reason !== 'planned').length
  const byId = new Map(comments.map((c) => [c.id, c]))

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Cycles</h3>
          <p className="text-[13px] text-muted-foreground mt-1">
            One pass of work each. A return starts the next one and says where the problem was caught.
          </p>
        </div>
        <span className="shrink-0 text-[12px] text-muted-foreground tabular-nums">
          {cycles.length} {cycles.length === 1 ? 'cycle' : 'cycles'}
          {returns > 0 && ` · ${returns} ${returns === 1 ? 'return' : 'returns'}`}
        </span>
      </div>

      <ol className="relative ml-2 border-l-2 border-border space-y-5">
        {cycles.map((c, idx) => {
          const reason = CYCLE_REASON[c.start_reason] ?? CYCLE_REASON.planned
          const current = idx === cycles.length - 1
          const comment = c.start_comment_id ? byId.get(c.start_comment_id) : null
          const container = c.container_kind === 'stream' ? 'Stream' : c.release_version
          return (
            <li key={c.id} className="relative pl-6">
              <span
                aria-hidden="true"
                className={cn(
                  'absolute -left-[11px] top-0.5 h-5 w-5 rounded-full ring-4 ring-background flex items-center justify-center',
                  reason.pill,
                )}
              >
                <Icon name={reason.icon} size={11} strokeWidth={2.6} />
              </span>

              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="text-[13px] font-semibold text-foreground">Cycle {c.cycle_number}</span>
                <span className={cn('rounded px-1.5 text-[10.5px] font-semibold uppercase tracking-wide', reason.pill)}>
                  {reason.label}
                </span>
                {current && <span className="text-[11px] text-muted-foreground">current</span>}
                <span className="ml-auto inline-flex items-center gap-1 text-[12px] text-muted-foreground">
                  <Icon name={CONTAINER_KIND[c.container_kind ?? 'release']?.icon} size={12} />
                  <span className="font-mono">{container}</span>
                </span>
              </div>

              {comment?.body && (
                <blockquote className="mt-1.5 border-l-2 border-border pl-2 text-[12.5px] text-foreground/80 line-clamp-3">
                  {comment.body}
                </blockquote>
              )}

              <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[12px]">
                <Stamp label="Started" at={c.started_at} />
                {c.start_reason !== 'planned' && <Person user={c.start_by} verb="by" />}
                <Stamp label="Picked up" at={c.picked_up_at} />
                <Stamp label="Delivered" at={c.submitted_at} />
                {c.submitted_at && (c.delivered_by
                  ? <Person user={c.delivered_by} verb="delivered by" />
                  : <span className="text-muted-foreground">delivered unassigned</span>)}
                <Stamp label="Verified" at={c.verified_at} />
                <Stamp label="Closed" at={c.closed_at} />
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
