import React from 'react'
import { Link } from 'react-router-dom'
import { Avatar } from '../ui/Avatar'
import { StatusBadge, RoleBadge } from '../ui/Badge'
import { Icon } from '../ui/Icon'
import { ContainerBadge } from '../common/ContainerBadge'
import { ReturnRequestActions } from '../issues/ReturnRequest'
import { relTime, fullTime } from '../../lib/relTime'
import { renderMarkdown } from '../../lib/markdown'

/**
 * The right-hand pane for one Pending return request (slice 20, FR-69): the Done
 * item it is about, every report that came with it, and Confirm / Dismiss.
 * Confirm sends the item back as the ordinary Reject from Done; Dismiss needs a
 * public comment and leaves it Done. `onDecided` reloads the queue.
 */
export function ReturnRequestDetail({ row, entries = [], onDecided }) {
  const item = row.issue
  const slug = `${item.key}`.toLowerCase()
  return (
    <div className="relative flex h-full min-h-0 flex-col" data-testid="return-request-detail">
      <header className="shrink-0 border-b border-border bg-card px-5 py-3">
        <div className="flex items-center gap-2 mb-1.5">
          <Link to={`/issue/${slug}`} className="font-mono text-[12px] text-muted-foreground hover:underline">
            {item.key}
          </Link>
          <StatusBadge status={item.status} />
          <ContainerBadge item={item} className="ml-auto" />
        </div>
        <h2 className="text-[15px] font-semibold leading-snug text-foreground">{item.title}</h2>
        <p className="mt-1 text-[12px] text-muted-foreground">
          {item.done_at ? <span title={fullTime(item.done_at)}>Done {relTime(item.done_at)}</span> : 'Done'}
          {item.assignee_user && <> · fixed by {item.assignee_user.name}</>}
        </p>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 space-y-3">
        <p className="text-[12.5px] text-muted-foreground">
          {row.entry_count === 1 ? '1 report' : `${row.entry_count} reports`} that the problem is back.
        </p>
        {entries.map((e) => (
          <article key={e.id} className="rounded-lg border border-border bg-card px-3.5 py-2.5">
            <div className="flex items-center gap-2 mb-1">
              <Avatar user={e.user} size={20} />
              <span className="text-[13px] font-semibold text-foreground">{e.user?.name ?? 'Unknown'}</span>
              {e.user?.role && <RoleBadge role={e.user.role} />}
              <span className="ml-auto text-[11px] text-muted-foreground" title={fullTime(e.created_at)}>
                {relTime(e.created_at)}
              </span>
            </div>
            <div dir="auto" className="text-[13.5px] leading-relaxed text-foreground/90">
              {renderMarkdown(e.body ?? '')}
            </div>
          </article>
        ))}
      </div>

      <footer className="shrink-0 border-t border-border bg-card px-5 py-3">
        <div className="flex items-start gap-2 mb-3 text-[12px] text-muted-foreground">
          <Icon name="info" size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>
            <strong className="font-medium text-foreground">Confirm</strong> rejects the item with the first report as the reason
            {item.container_kind === 'release' ? ' and moves it to the Stream' : ''}.{' '}
            <strong className="font-medium text-foreground">Dismiss</strong> keeps it Done and tells Support why.
          </span>
        </div>
        <div className="flex items-center gap-2">
          <ReturnRequestActions request={{ id: row.id }} item={item} onDecided={onDecided} />
        </div>
      </footer>
    </div>
  )
}
