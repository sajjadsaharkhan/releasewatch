import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { issuesApi, queueApi, userApi } from '../lib/api'
import { issueSlug } from '../lib/issueSlug'
import { PRIORITY } from '../lib/constants'
import { useApp } from '../hooks/useApp'
import { useToast } from '../hooks/useToast'
import { Button, Empty, Icon, Segmented, Tabs } from '../components/ui'
import { IssueBoard, IssueBoardSkeleton } from '../components/common/IssueBoard'
import {
  DoneRangePicker, doneRangeLabel, doneRangeToApi, readDoneRange, writeDoneRange,
} from '../components/common/DoneRangePicker'
import { PinSlots, QueueItemRow, SortableQueue, groupByDay } from '../components/queue'

// My Work (slice 10; redesigned 2026-10-01 from prototype variant D): one
// person's queue across every project. Tabs filter it — All, In progress,
// Overdue, Blockers, Done — and a List | Board switch shows it as rows or as
// the project boards' columns. Pinned rows sit on top under "Pinned · n of 4".
// The owner, a CTO and an Admin can reorder, pin and change priority; the API
// refuses everyone else. `/my-work` is your own; CTO and Admin open anyone's
// at `/u/:username/work`. State lives in the URL: `?tab=`, `?view=board`, and
// the Done range (`?done=30d` or `?done_from=&done_to=`, default 7 days).

const VIEW_OPTIONS = [
  { value: 'list', label: 'List' },
  { value: 'board', label: 'Board' },
]

const TAB_FILTERS = {
  all: () => true,
  in_progress: (i) => i.status === 'in_progress',
  overdue: (i) => i.due_state === 'overdue',
  blockers: (i) => i.is_release_blocker,
}

const EMPTY_TAB = {
  in_progress: 'Nothing in progress.',
  overdue: 'Nothing overdue.',
  blockers: 'No release blockers.',
}

function errorDetail(err, fallback) {
  return err?.response?.data?.detail || fallback
}

/** `me` on /my-work; the profile's id on /u/:username/work (yourself → `me`). */
export function useQueueOwner(username, me) {
  const [state, setState] = useState({ ref: username ? null : 'me', user: username ? null : me, error: null })
  useEffect(() => {
    if (!username || username === me?.username) {
      setState({ ref: 'me', user: me, error: null })
      return
    }
    setState({ ref: null, user: null, error: null })
    userApi.getByUsername(username)
      .then((res) => setState({ ref: res.data.id, user: res.data, error: null }))
      .catch(() => setState({ ref: null, user: null, error: 'not_found' }))
  }, [username, me?.username]) // eslint-disable-line react-hooks/exhaustive-deps
  return state
}

function flatten(queue) {
  return [...queue.groups.pinned, ...queue.groups.rest].map((e) => ({
    ...e.issue, pinned: e.pinned, pin_locked: e.pin_locked, pinned_by: e.pinned_by,
  }))
}

function optimisticMove(queue, id, { beforeId, afterId }) {
  if (!queue) return queue
  const group = queue.groups.pinned.some((e) => e.issue.id === id) ? 'pinned' : 'rest'
  const list = queue.groups[group]
  const anchor = beforeId ?? afterId
  if (!list.some((e) => e.issue.id === anchor)) return queue // across the pin line — the API refuses
  const moving = list.find((e) => e.issue.id === id)
  const others = list.filter((e) => e.issue.id !== id)
  const at = others.findIndex((e) => e.issue.id === anchor) + (afterId != null ? 1 : 0)
  return { ...queue, groups: { ...queue.groups, [group]: [...others.slice(0, at), moving, ...others.slice(at)] } }
}

// ─── Data: the queue, the board (Done + the Board view), and the actions ─────

function useMyWork(ownerRef, doneRange) {
  const { toast } = useToast()
  const [queue, setQueue] = useState(null)
  const [board, setBoard] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const rangeKey = JSON.stringify(doneRange)
  const doneParams = useMemo(() => doneRangeToApi(doneRange), [rangeKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const loadQueue = useCallback(async () => {
    if (ownerRef == null) return null
    try {
      const res = await queueApi.get(ownerRef)
      setQueue(res.data)
      setError(null)
      return res.data
    } catch (err) {
      setError(err.response?.status === 403
        ? 'Only the owner, a CTO or an Admin can see this queue.'
        : errorDetail(err, 'Could not load the queue.'))
      return null
    }
  }, [ownerRef])

  const loadBoard = useCallback(async () => {
    if (ownerRef == null) return
    try {
      const res = await queueApi.board(ownerRef, doneParams)
      setBoard(res.data)
    } catch {
      setBoard({ columns: [] })
    }
  }, [ownerRef, doneParams])

  useEffect(() => { setQueue(null); loadQueue() }, [loadQueue])
  useEffect(() => { setBoard(null); loadBoard() }, [loadBoard])

  const run = async (call, fail, success) => {
    setBusy(true)
    try {
      const res = await call()
      if (res?.data?.groups) setQueue(res.data)
      if (success) toast({ title: success })
      return true
    } catch (err) {
      toast.error(errorDetail(err, fail))
      await loadQueue()
      return false
    } finally {
      setBusy(false)
      loadBoard()
    }
  }

  const actions = {
    pin: (i) => run(() => queueApi.pin(ownerRef, i.id), 'Could not pin that item.', `Pinned ${i.key}`),
    unpin: (i) => run(() => queueApi.unpin(ownerRef, i.id), 'Could not unpin that item.', `Unpinned ${i.key}`),
    move: (id, anchor) => {
      setQueue((q) => optimisticMove(q, id, anchor))
      return run(() => queueApi.move(ownerRef, { issueId: id, ...anchor }), 'Could not reorder the queue.')
    },
    setPriority: async (item, priority) => {
      if (priority === item.priority) return
      const before = flatten(queue).findIndex((i) => i.id === item.id) + 1
      const ok = await run(() => issuesApi.update(item.id, { priority }), 'Could not change the priority.')
      if (!ok) return
      const after = await loadQueue()
      if (!after) return
      const list = flatten(after)
      const now = list.findIndex((i) => i.id === item.id) + 1
      toast({
        title: `${item.key} is ${PRIORITY[priority].label} now`,
        body: list[now - 1]?.pinned ? 'It stays pinned where it is.'
          : now === before ? 'Its place in the queue is unchanged.'
            : `The default rule moved it from #${before} to #${now}.`,
      })
    },
    transition: async (issue, to) => {
      try {
        await issuesApi.transition(issue.id, { to })
      } catch (err) {
        toast.error(errorDetail(err, `Could not move ${issue.key ?? 'that item'}`))
      }
      await Promise.all([loadQueue(), loadBoard()])
    },
  }

  return { queue, board, error, busy, actions, reload: loadQueue }
}

// ─── Pieces ──────────────────────────────────────────────────────────────────

function SectionLabel({ icon, children, right }) {
  return (
    <div className="mb-2 flex items-center gap-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
      <Icon name={icon} size={12} aria-hidden="true" />{children}
      <span className="h-px flex-1 bg-border" />{right}
    </div>
  )
}

function ListSkeleton() {
  return (
    <div className="space-y-2 px-7 pt-4" aria-hidden="true">
      {[0, 1, 2, 3].map((n) => (
        <div key={n} className="flex items-center gap-3 rounded-xl border border-border px-3 py-3.5">
          <div className="h-6 w-6 animate-pulse rounded-full bg-zinc-200 dark:bg-zinc-700" />
          <div className="flex-1 space-y-2">
            <div className="h-3.5 w-2/5 animate-pulse rounded bg-zinc-200 dark:bg-zinc-700" />
            <div className="h-3 w-3/5 animate-pulse rounded bg-zinc-100 dark:bg-zinc-800" />
          </div>
          <div className="h-6 w-20 animate-pulse rounded-md bg-zinc-200 dark:bg-zinc-700" />
        </div>
      ))}
    </div>
  )
}

function QueueList({ items, queue, tab, isOwner, busy, actions, onOpen }) {
  const shown = items.filter(TAB_FILTERS[tab] ?? TAB_FILTERS.all)
  const sortable = queue.can_reorder && tab === 'all'
  const positions = new Map(items.map((i, n) => [i.id, n + 1]))
  const pinned = shown.filter((i) => i.pinned)
  const rest = shown.filter((i) => !i.pinned)
  const pin = {
    canPin: queue.can_pin, pinsUsed: queue.pins_used, pinLimit: queue.pin_limit, isOwner, busy,
    onPin: actions.pin, onUnpin: actions.unpin,
  }
  const row = (i) => (
    <QueueItemRow
      key={i.id} item={i} position={positions.get(i.id)} sortable={sortable} onOpen={onOpen}
      onPriority={queue.can_reorder ? actions.setPriority : null} pin={pin}
    />
  )

  if (shown.length === 0) {
    return (
      <p className="mx-7 mt-4 rounded-xl border border-dashed border-border px-4 py-10 text-center text-[13px] text-muted-foreground">
        {EMPTY_TAB[tab] ?? 'Nothing here.'}
      </p>
    )
  }
  return (
    <div className="px-7 pb-24 pt-4">
      {tab !== 'all' && (
        <p className="mb-3 text-[12px] text-muted-foreground">Showing a filter — switch to All to reorder.</p>
      )}
      <SortableQueue items={shown} enabled={sortable} onMove={actions.move}>
        {pinned.length > 0 && (
          <section aria-label="Pinned" data-testid="section-pinned">
            <SectionLabel icon="pin" right={<PinSlots used={queue.pins_used} limit={queue.pin_limit} />}>
              Pinned · {queue.pins_used} of {queue.pin_limit}
            </SectionLabel>
            <ol className="mb-5 space-y-2">{pinned.map(row)}</ol>
          </section>
        )}
        <section aria-label="Queue" data-testid="section-queue">
          {pinned.length > 0 && rest.length > 0 && <SectionLabel icon="list-ordered">Queue</SectionLabel>}
          <ol className="space-y-2">{rest.map(row)}</ol>
        </section>
      </SortableQueue>
    </div>
  )
}

function DoneList({ board, range, onRange, onOpen }) {
  const done = board?.columns.find((c) => c.status === 'done')?.items
  return (
    <div className="px-7 pb-24 pt-4" data-testid="done-list">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <p className="text-[12.5px] text-muted-foreground">
          {done == null ? 'Loading…' : `${done.length} item${done.length === 1 ? '' : 's'} finished · ${doneRangeLabel(range).toLowerCase()}`}
        </p>
        <DoneRangePicker value={range} onChange={onRange} className="ml-auto" />
      </div>
      {done == null ? <ListSkeleton /> : done.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border px-4 py-12 text-center">
          <Icon name="circle-check-big" size={22} className="mx-auto mb-2 text-zinc-300 dark:text-zinc-600" aria-hidden="true" />
          <p className="text-[13px] font-medium">Nothing finished in this range</p>
          <p className="mt-1 text-[12px] text-muted-foreground">Widen the range to see older work.</p>
        </div>
      ) : (
        <div className="space-y-5">
          {groupByDay(done, (i) => i.completed_at).map((g) => (
            <section key={g.label} aria-label={g.label}>
              <h3 className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {g.label} <span className="font-normal normal-case tracking-normal">· {g.rows.length}</span>
              </h3>
              <ol className="space-y-2">
                {g.rows.map((i) => <QueueItemRow key={i.id} item={i} done onOpen={onOpen} />)}
              </ol>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}

function QueueBoard({ board, tab, range, onRange, onOpen, onStatusChange }) {
  const filter = TAB_FILTERS[tab] ?? TAB_FILTERS.all
  return (
    <>
      <div className="flex items-center justify-end gap-2 px-7 pt-3 text-[12px] text-muted-foreground">
        <span>Done column shows</span>
        <DoneRangePicker value={range} onChange={onRange} />
      </div>
      {!board ? <IssueBoardSkeleton /> : (
        <div className="overflow-x-auto scrollbar-thin">
          <IssueBoard
            issues={board.columns.flatMap((c) => c.items).filter((i) => i.status === 'done' || filter(i))}
            onOpen={onOpen}
            onStatusChange={onStatusChange}
            emptyText={{ done: `Nothing finished · ${doneRangeLabel(range).toLowerCase()}` }}
          />
        </div>
      )}
    </>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function MyWorkPage() {
  const { username } = useParams()
  const { user } = useApp()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const owner = useQueueOwner(username, user)
  const isOwner = owner.ref === 'me'
  const view = searchParams.get('view') === 'board' ? 'board' : 'list'
  const rawTab = searchParams.get('tab') ?? 'all'
  const tab = view === 'board' && rawTab === 'done' ? 'all' : rawTab
  const doneRange = readDoneRange(searchParams)
  const { queue, board, error, busy, actions, reload } = useMyWork(owner.ref, doneRange)

  const setParam = (key, value, fallback) => {
    const next = new URLSearchParams(searchParams)
    if (value === fallback) next.delete(key); else next.set(key, value)
    setSearchParams(next, { replace: true })
  }
  const setDoneRange = (range) => setSearchParams(writeDoneRange(searchParams, range), { replace: true })
  const openItem = (issue) => navigate(`/issue/${issueSlug(issue)}`)
  const historyPath = isOwner ? '/my-work/history' : `/u/${username}/work/history`

  const items = useMemo(() => (queue ? flatten(queue) : []), [queue])
  const doneCount = board?.columns.find((c) => c.status === 'done')?.items.length
  const count = (key) => (queue ? items.filter(TAB_FILTERS[key]).length : undefined)

  if (owner.error) return <Empty icon="user-x" title="User not found" body={`There's no user called “${username}”.`} />

  const ownerName = owner.user?.name ?? queue?.owner?.name
  const title = isOwner ? 'My Work' : `${ownerName ?? '…'}’s work`

  return (
    <div className="h-full overflow-auto scrollbar-thin">
      <header className="px-7 pt-6">
        {!isOwner && (
          <nav aria-label="Breadcrumb" className="mb-1 text-xs text-muted-foreground">
            <Link to={`/u/${username}`} className="hover:text-foreground">{ownerName ?? username}</Link>
          </nav>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-bold">{title}</h1>
          <div className="ml-auto flex items-center gap-2">
            <Segmented value={view} onValueChange={(v) => setParam('view', v, 'list')} options={VIEW_OPTIONS} />
            <Button variant="outline" size="sm" onClick={() => navigate(historyPath)} disabled={owner.ref == null}>
              <Icon name="history" size={14} aria-hidden="true" />Queue history
            </Button>
          </div>
        </div>
        {!isOwner && queue && (
          <p className="mt-1 text-[12.5px] text-muted-foreground">
            {queue.can_reorder
              ? `You can reorder and pin this queue. ${ownerName ?? 'They'} will be notified of changes.`
              : 'View only.'}
          </p>
        )}
        <Tabs
          className="mt-3"
          value={tab}
          onValueChange={(t) => setParam('tab', t, 'all')}
          options={[
            { value: 'all', label: 'All', badge: count('all') },
            { value: 'in_progress', label: 'In progress', badge: count('in_progress') },
            { value: 'overdue', label: 'Overdue', badge: count('overdue') },
            { value: 'blockers', label: 'Blockers', badge: count('blockers') },
            ...(view === 'list' ? [{ value: 'done', label: 'Done', badge: doneCount }] : []),
          ]}
        />
      </header>

      {error ? (
        <div role="alert" className="py-16 text-center text-sm text-muted-foreground">
          {error}
          <Button variant="outline" size="sm" className="ml-3" onClick={reload}>Retry</Button>
        </div>
      ) : view === 'board' ? (
        <QueueBoard board={board} tab={tab} range={doneRange} onRange={setDoneRange} onOpen={openItem} onStatusChange={actions.transition} />
      ) : tab === 'done' ? (
        <DoneList board={board} range={doneRange} onRange={setDoneRange} onOpen={openItem} />
      ) : !queue ? (
        <ListSkeleton />
      ) : items.length === 0 ? (
        <Empty
          icon="list-todo"
          title={isOwner ? 'Nothing assigned to you' : 'Nothing assigned'}
          body="Open items assigned across every project show up here — To do, Rejected, In progress, in review and Blocked."
        />
      ) : (
        <QueueList items={items} queue={queue} tab={tab} isOwner={isOwner} busy={busy} actions={actions} onOpen={openItem} />
      )}
    </div>
  )
}
