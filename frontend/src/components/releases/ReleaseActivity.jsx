import React from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { Empty } from '../ui/Empty'
import { formatDay, relTime } from '../../lib/relTime'
import { ReleaseLifecycleBadge } from './ReleaseMarkers'
import { GoNogoBadge } from './GoNogoPanel'

// The release Activity tab (FR-51): lifecycle, dates, items added or removed,
// go/no-go, ship, edits — oldest first (created at the top), one rail row per event.
const EVENT = {
  created: { icon: 'flag', dot: 'bg-zinc-500' },
  status_changed: { icon: 'git-commit-horizontal', dot: 'bg-blue-500' },
  dates_changed: { icon: 'calendar-clock', dot: 'bg-zinc-400' },
  item_added: { icon: 'package-plus', dot: 'bg-teal-500' },
  item_removed: { icon: 'package-minus', dot: 'bg-zinc-400' },
  go_nogo: { icon: 'gavel', dot: 'bg-violet-500' },
  shipped: { icon: 'rocket', dot: 'bg-green-500' },
  edited: { icon: 'pencil', dot: 'bg-zinc-400' },
}

const FIELD = {
  target_date: 'Target ship date', code_freeze_date: 'Code freeze',
  version: 'Name', description: 'Description', staging_url: 'Staging URL',
}
const REMOVE_REASON = {
  ship: 'moved to the backlog by the ship',
  cancel: 'moved to the backlog when the release was cancelled',
  production_return: 'returned from production — now in the Stream',
}

const day = (v) => formatDay(v) ?? 'none'

function ItemRef({ meta }) {
  return (
    <Link
      to={`/issue/${(meta.key || `issue-${meta.issue_number}`).toLowerCase()}`}
      className="font-mono text-[12px] text-foreground hover:underline"
    >
      {meta.key || `#${meta.issue_number}`}
    </Link>
  )
}

// A lifecycle move named for what it means (FR-50), with the badges it moved between.
const MOVE = {
  'planning>development': 'started development',
  'development>qa': 'started QA — code freeze',
  'qa>development': 'moved it back to development',
  'qa>released': 'released it',
}

function describe(e) {
  const m = e.meta || {}
  switch (e.event_type) {
    case 'created':
      return <>created the release <ReleaseLifecycleBadge status={m.status ?? 'planning'} size="sm" /></>
    case 'status_changed': {
      const phrase = m.to === 'cancelled' ? 'cancelled the release' : MOVE[`${m.from}>${m.to}`] ?? 'moved it'
      return <>{phrase} <ReleaseLifecycleBadge status={m.from} size="sm" /> → <ReleaseLifecycleBadge status={m.to} size="sm" /></>
    }
    case 'dates_changed':
    case 'edited':
      return (
        <>changed {Object.entries(m.changes || {}).map(([f, c], i) => (
          <span key={f}>
            {i > 0 && ', '}
            <b className="font-medium">{FIELD[f] ?? f}</b>
            {f.endsWith('date') && <> from {day(c.from)} to {day(c.to)}</>}
          </span>
        ))}</>
      )
    case 'item_added':
      return <>added <ItemRef meta={m} /> <span className="text-muted-foreground truncate">{m.title}</span></>
    case 'item_removed':
      return (
        <>removed <ItemRef meta={m} /> <span className="text-muted-foreground truncate">{m.title}</span>
          {m.reason && <span className="text-muted-foreground"> — {REMOVE_REASON[m.reason] ?? m.reason}</span>}</>
      )
    case 'go_nogo':
      return <>recorded <GoNogoBadge status={m.decision} />{m.note && <span className="text-muted-foreground"> “{m.note}”</span>}</>
    case 'shipped':
      return (
        <>shipped it{m.moved > 0
          ? <span className="text-muted-foreground"> — {m.moved} unfinished item{m.moved === 1 ? '' : 's'} moved to the backlog</span>
          : <span className="text-muted-foreground"> — every item was Done</span>}</>
      )
    default:
      return e.event_type
  }
}

export function ReleaseActivity({ events, loading, error, onRetry }) {
  if (loading) {
    return (
      <ul className="space-y-3 py-2" aria-busy="true">
        {[0, 1, 2, 3].map((i) => (
          <li key={i} className="flex items-center gap-3">
            <div className="h-6 w-6 rounded-full bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
            <div className="h-3 w-2/3 rounded bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
          </li>
        ))}
      </ul>
    )
  }
  if (error) {
    return (
      <div role="alert" className="py-10 text-center text-sm text-muted-foreground">
        {error} <button className="ml-1 underline" onClick={onRetry}>Retry</button>
      </div>
    )
  }
  if (!events?.length) {
    return <Empty icon="history" title="No activity yet" body="Lifecycle changes, dates, items and decisions show up here." />
  }
  return (
    <ol className="relative py-2">
      <span aria-hidden className="absolute left-3 top-4 bottom-4 w-px bg-border" />
      {events.map((e) => {
        const t = EVENT[e.event_type] ?? EVENT.edited
        return (
          <li key={e.id} className="relative flex items-start gap-3 py-2 text-[13px]">
            <span className={cn('relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ring-4 ring-background text-white', t.dot)}>
              <Icon name={t.icon} size={12} aria-hidden />
            </span>
            <div className="min-w-0 flex-1 flex flex-wrap items-center gap-x-1.5 gap-y-1 leading-6">
              <span className="font-medium">{e.actor?.name ?? 'Releasewatch'}</span>
              {describe(e)}
            </div>
            <time dateTime={e.created_at} title={new Date(e.created_at).toLocaleString()} className="shrink-0 text-[11px] text-muted-foreground leading-6">
              {relTime(e.created_at)}
            </time>
          </li>
        )
      })}
    </ol>
  )
}
