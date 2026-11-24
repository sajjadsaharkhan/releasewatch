import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { Requesters } from '../issues/ReturnRequest'
import { relTime, fullTime } from '../../lib/relTime'

// Pending return requests at the top of the Triage page's New tab (slice 20, FR-69). A fixed
// item came back, so they read as urgent: a red-outlined card with a solid red icon tile, the
// facts in a footer strip, and a "waiting" chip that goes from amber to solid red.

/** After this many hours a request has waited too long and its chip turns solid red. */
export const RETURN_REQUEST_HOT_HOURS = 4

/** How long a request has waited, and whether that is now "hot". */
export function waited(requestedAt, now = Date.now()) {
  const h = (now - new Date(requestedAt).getTime()) / 3600_000
  const text = h < 1 ? 'waiting <1h' : h < 24 ? `waiting ${Math.round(h)}h` : `waiting ${Math.round(h / 24)}d`
  return { text, hot: h >= RETURN_REQUEST_HOT_HOURS }
}

const whereOf = (issue) => (issue.container_kind === 'stream' ? 'Stream' : issue.release_version)

function ReturnRequestRow({ row, selected, onSelect }) {
  const { issue } = row
  const w = waited(row.requested_at)
  const reports = `${row.entry_count} ${row.entry_count === 1 ? 'report' : 'reports'}`
  return (
    <button
      onClick={onSelect}
      aria-current={selected ? 'true' : undefined}
      data-testid="return-request-row"
      className={cn(
        'w-full overflow-hidden text-left rounded-lg border bg-card shadow-sm transition-shadow hover:shadow-md',
        'border-red-300 dark:border-red-800/70',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        selected && 'ring-2 ring-red-400 dark:ring-red-500',
      )}
    >
      <span className="flex gap-3 px-3.5 pt-3">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-red-500 text-white">
          <Icon name="rotate-ccw" size={16} aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="mb-0.5 flex items-center gap-2">
            <span className="font-mono text-[11px] text-muted-foreground">{issue.key}</span>
            <span className="rounded-full bg-red-100 px-1.5 py-0.5 text-[10.5px] font-semibold leading-none text-red-800 dark:bg-red-900/50 dark:text-red-200">
              Problem is back
            </span>
            {issue.project_name && <span className="ml-auto truncate text-[11px] text-muted-foreground">{issue.project_name}</span>}
          </span>
          <span className="block text-[13.5px] font-semibold leading-snug text-foreground">{issue.title}</span>
          {row.first_comment?.body && (
            <span className="mt-1 block line-clamp-2 text-[12.5px] text-muted-foreground">{row.first_comment.body}</span>
          )}
        </span>
      </span>
      <span className="mt-2.5 flex items-center gap-1.5 border-t border-red-200/70 bg-red-50/60 px-3.5 py-1.5 text-[11.5px] text-muted-foreground dark:border-red-900/50 dark:bg-red-950/20">
        <Requesters users={row.requesters} />
        <span>·</span><span>{reports}</span>
        <span>·</span>
        <span title={issue.done_at ? fullTime(issue.done_at) : undefined}>
          Done {issue.done_at ? relTime(issue.done_at) : ''} in {whereOf(issue)}
        </span>
        <span
          data-testid="return-request-waiting"
          title={fullTime(row.requested_at)}
          className={cn(
            'ml-auto rounded-full px-1.5 py-0.5 text-[10.5px] font-semibold leading-none',
            w.hot ? 'bg-red-600 text-white' : 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200',
          )}
        >
          {w.text}
        </span>
      </span>
    </button>
  )
}

/** The returns that lead the New tab: a group header and one card per request. */
export function ReturnRequestRows({ rows, selectedId, onSelect }) {
  if (rows.length === 0) return null
  return (
    <section aria-label="Return requests" data-testid="return-requests-queue" className="border-b border-border pb-3">
      <h2 className="flex items-center gap-1.5 px-7 pt-3 text-[11px] font-bold text-red-700 dark:text-red-300">
        <Icon name="rotate-ccw" size={13} aria-hidden="true" />
        <span className="uppercase tracking-wider">Came back from production · {rows.length}</span>
      </h2>
      <ul className="space-y-2.5 px-5 pt-3">
        {rows.map((r) => (
          <li key={r.id}><ReturnRequestRow row={r} selected={selectedId === r.id} onSelect={() => onSelect(r.id)} /></li>
        ))}
      </ul>
    </section>
  )
}
