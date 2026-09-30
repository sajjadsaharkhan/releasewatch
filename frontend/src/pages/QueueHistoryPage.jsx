import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { cn } from '../lib/cn'
import { queueApi } from '../lib/api'
import { useApp } from '../hooks/useApp'
import { Avatar, Button, DateTimeRangePicker, Empty, Icon } from '../components/ui'
import { QUEUE_ACTIONS, QueueHistoryTimeline, TypeMark } from '../components/queue'
import { useQueueOwner } from './MyWorkPage'

// Queue history (FR-41) as its own page: `/my-work/history`, or
// `/u/:username/work/history` for a CTO or Admin. Filters run on the server —
// when (presets or a custom range, default 30 days), changed by (anyone, not
// the owner, a person), action, item type, and a search over key, #id or
// title. Each filter option shows how many changes it would list (facets).

const PAGE_SIZE = 50
const DAY = 86400000

function rangeParams(range) {
  if (range.days != null) return { from: new Date(Date.now() - range.days * DAY).toISOString() }
  const iso = (v, edge) => (v.length === 10
    ? new Date(`${v}T${edge === 'to' ? '23:59:59.999' : '00:00:00'}`).toISOString()
    : new Date(v).toISOString())
  return {
    ...(range.from ? { from: iso(range.from, 'from') } : {}),
    ...(range.to ? { to: iso(range.to, 'to') } : {}),
  }
}

function Facet({ title, children }) {
  return (
    <div>
      <h2 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{title}</h2>
      <div className="space-y-0.5">{children}</div>
    </div>
  )
}

function FacetOption({ active, onClick, children, count }) {
  return (
    <button
      type="button" onClick={onClick} aria-pressed={active}
      className={cn(
        'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[12.5px] transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        active ? 'bg-primary/10 font-medium text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      <span className="flex min-w-0 flex-1 items-center gap-2">{children}</span>
      {count != null && <span className="text-[11px] tabular-nums opacity-70">{count}</span>}
    </button>
  )
}

export default function QueueHistoryPage() {
  const { username } = useParams()
  const { user } = useApp()
  const owner = useQueueOwner(username, user)
  const isOwner = owner.ref === 'me'
  const [range, setRange] = useState({ days: 30 })
  const [who, setWho] = useState('all') // all | others | <user id>
  const [action, setAction] = useState(null)
  const [type, setType] = useState(null)
  const [q, setQ] = useState('')
  const [search, setSearch] = useState('')
  const [data, setData] = useState({ items: [], total: 0, facets: null, page: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const t = setTimeout(() => setSearch(q.trim()), 250)
    return () => clearTimeout(t)
  }, [q])

  const rangeKey = JSON.stringify(range)
  const params = useMemo(() => ({
    ...rangeParams(range),
    ...(who === 'others' ? { not_owner: true } : who !== 'all' ? { actor_id: who } : {}),
    ...(action ? { action } : {}),
    ...(type ? { type } : {}),
    ...(search ? { q: search } : {}),
  }), [rangeKey, who, action, type, search]) // eslint-disable-line react-hooks/exhaustive-deps

  const load = useCallback(async (page) => {
    if (owner.ref == null) return
    setLoading(true)
    try {
      const res = await queueApi.history(owner.ref, { ...params, page, size: PAGE_SIZE })
      setData((d) => ({
        items: page === 1 ? res.data.items : [...d.items, ...res.data.items],
        total: res.data.total, facets: res.data.facets, page,
      }))
      setError(null)
    } catch (err) {
      setError(err.response?.status === 403
        ? 'Only the owner, a CTO or an Admin can see this history.'
        : err.response?.data?.detail || 'Could not load the history.')
    } finally {
      setLoading(false)
    }
  }, [owner.ref, params])

  useEffect(() => { load(1) }, [load])

  if (owner.error) return <Empty icon="user-x" title="User not found" body={`There's no user called “${username}”.`} />

  const ownerId = isOwner ? user?.id : owner.user?.id
  const backTo = isOwner ? '/my-work' : `/u/${username}/work`
  const backLabel = isOwner ? 'My Work' : `${owner.user?.name ?? username}’s work`
  const f = data.facets

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-border px-7 py-4">
        <Link
          to={backTo}
          className="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[13px] font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Icon name="arrow-left" size={14} aria-hidden="true" />{backLabel}
        </Link>
        <h1 className="text-lg font-bold">Queue history</h1>
        {f && <span className="text-[12px] tabular-nums text-muted-foreground">{data.total} of {f.total} changes</span>}
        <div className="relative ml-auto w-full max-w-xs">
          <Icon name="search" size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <input
            value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search key, #id or title…"
            aria-label="Search queue history"
            className="h-9 w-full rounded-md border border-border bg-background pl-8 pr-3 text-[12.5px] outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="space-y-5 overflow-y-auto border-b border-border px-4 py-5 scrollbar-thin md:border-b-0 md:border-r" aria-label="Filters">
          <Facet title="When">
            <DateTimeRangePicker value={range} onChange={setRange} presets={[1, 7, 30, 90]} align="start" className="w-full" />
          </Facet>
          <Facet title="Changed by">
            <FacetOption active={who === 'all'} onClick={() => setWho('all')} count={f?.total}>Anyone</FacetOption>
            <FacetOption active={who === 'others'} onClick={() => setWho('others')} count={f?.not_owner}>
              <Icon name="shield-alert" size={13} className="text-amber-600" aria-hidden="true" />Not the owner
            </FacetOption>
            {f?.actors.map(({ actor, count }) => (
              <FacetOption key={actor.id} active={who === String(actor.id)} onClick={() => setWho(String(actor.id))} count={count}>
                <Avatar user={actor} size={16} /><span className="truncate">{actor.name}</span>
              </FacetOption>
            ))}
          </Facet>
          <Facet title="Action">
            <FacetOption active={!action} onClick={() => setAction(null)} count={f?.total}>All actions</FacetOption>
            {Object.entries(QUEUE_ACTIONS).map(([k, a]) => (
              <FacetOption key={k} active={action === k} onClick={() => setAction(k)} count={f?.actions[k]}>
                <Icon name={a.icon} size={13} aria-hidden="true" />{a.label}
              </FacetOption>
            ))}
          </Facet>
          <Facet title="Item type">
            <FacetOption active={!type} onClick={() => setType(null)} count={f?.total}>Bugs & tasks</FacetOption>
            <FacetOption active={type === 'bug'} onClick={() => setType('bug')} count={f?.types.bug}><TypeMark type="bug" />Bugs</FacetOption>
            <FacetOption active={type === 'task'} onClick={() => setType('task')} count={f?.types.task}><TypeMark type="task" />Tasks</FacetOption>
          </Facet>
        </aside>

        <main className="overflow-y-auto bg-card px-8 py-6 scrollbar-thin" data-testid="queue-history" aria-busy={loading}>
          <div className="mx-auto max-w-3xl">
            {error ? (
              <p role="alert" className="py-10 text-center text-sm text-muted-foreground">
                {error}
                <Button variant="outline" size="sm" className="ml-3" onClick={() => load(1)}>Retry</Button>
              </p>
            ) : loading && data.page === 0 ? (
              <div className="space-y-3" aria-hidden="true">
                {[0, 1, 2, 3].map((n) => (
                  <div key={n} className="flex gap-3">
                    <div className="h-7 w-7 animate-pulse rounded-full bg-zinc-200 dark:bg-zinc-700" />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-3 w-2/3 animate-pulse rounded bg-zinc-200 dark:bg-zinc-700" />
                      <div className="h-3 w-1/3 animate-pulse rounded bg-zinc-100 dark:bg-zinc-800" />
                    </div>
                  </div>
                ))}
              </div>
            ) : data.items.length === 0 ? (
              <Empty icon="history" title="No queue changes" body="Nothing matches these filters. Widen the date range or clear a filter." />
            ) : (
              <>
                <QueueHistoryTimeline rows={data.items} ownerId={ownerId} />
                {data.items.length < data.total && (
                  <Button variant="outline" size="sm" className="mt-6 w-full" loading={loading} onClick={() => load(data.page + 1)}>
                    Load more
                  </Button>
                )}
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
