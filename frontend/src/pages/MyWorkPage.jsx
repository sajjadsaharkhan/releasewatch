import React, { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors,
} from '@dnd-kit/core'
import {
  SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { cn } from '../lib/cn'
import { issuesApi, queueApi, userApi } from '../lib/api'
import { issueSlug } from '../lib/issueSlug'
import { relTime, fullTime } from '../lib/relTime'
import { useApp } from '../hooks/useApp'
import { useToast } from '../hooks/useToast'
import { Avatar } from '../components/ui/Avatar'
import { Button } from '../components/ui/Button'
import { Empty } from '../components/ui/Empty'
import { Icon } from '../components/ui/Icon'
import { Segmented } from '../components/ui/Segmented'
import { Sheet } from '../components/ui/Sheet'
import { Tooltip } from '../components/ui/Tooltip'
import { StatusBadge } from '../components/ui/Badge'
import { IssueHoverCard } from '../components/common/IssueHoverCard'
import { IssueBoard, IssueBoardSkeleton } from '../components/common/IssueBoard'
import { WorkItemCard } from '../components/common/WorkItemCard'

// My Work (slice 10, FR-33–FR-42): one person's queue across every project —
// In progress, then Pinned (≤ 4), then the rest in manual order — as a list or
// a Kanban. The owner, a CTO and an Admin can reorder and pin; everyone else
// never gets here (the API says 403). `/my-work` is your own; CTO and Admin
// open anyone's at `/u/:username/work`.

const VIEW_KEY = 'rw:my-work-view'

function readView(userId) {
  try { return localStorage.getItem(`${VIEW_KEY}:${userId}`) === 'kanban' ? 'kanban' : 'list' } catch { return 'list' }
}

function writeView(userId, view) {
  try { localStorage.setItem(`${VIEW_KEY}:${userId}`, view) } catch { /* private window — UI preference only */ }
}

function errorDetail(err, fallback) {
  return err?.response?.data?.detail || fallback
}

// ─── Owner ───────────────────────────────────────────────────────────────────

/** `me` on /my-work; the profile's id on /u/:username/work (yourself → `me`). */
function useOwner(username, me) {
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

// ─── List view ───────────────────────────────────────────────────────────────

function PinToggle({ entry, queue, isOwner, onPin, onUnpin, busy }) {
  const { can_pin: canPin, pins_used: used, pin_limit: limit } = queue
  if (!canPin) return <span className="w-8 shrink-0" />
  const title = entry.issue.title
  if (entry.pinned) {
    const locked = entry.pin_locked && isOwner
    const reason = locked
      ? `${entry.pinned_by?.name ?? 'A CTO or Admin'} pinned this — only a CTO or Admin can unpin it.`
      : 'Unpin'
    return (
      <Tooltip content={reason}>
        <span className="inline-flex rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" tabIndex={locked ? 0 : undefined} data-testid="pin-toggle-wrapper">
          <Button
            variant="ghost"
            size="icon-sm"
            disabled={locked || busy}
            onClick={() => onUnpin(entry)}
            aria-label={locked ? `${title} — locked pin` : `Unpin ${title}`}
            aria-pressed="true"
            className="text-primary"
            data-testid="unpin"
          >
            <Icon name={locked ? 'lock' : 'pin-off'} size={14} aria-hidden="true" />
          </Button>
        </span>
      </Tooltip>
    )
  }
  const full = used >= limit
  return (
    <Tooltip content={full ? `This queue already has ${limit} pins — unpin one first.` : 'Pin to the top'}>
      <span className="inline-flex rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" tabIndex={full ? 0 : undefined}>
        <Button
          variant="ghost"
          size="icon-sm"
          disabled={full || busy}
          onClick={() => onPin(entry)}
          aria-label={`Pin ${title}`}
          aria-pressed="false"
          className="text-muted-foreground"
          data-testid="pin"
        >
          <Icon name="pin" size={14} aria-hidden="true" />
        </Button>
      </span>
    </Tooltip>
  )
}

function QueueRow({ entry, index, sortable, onOpen, toggle }) {
  const {
    attributes, listeners, setNodeRef, transform, transition, isDragging,
  } = useSortable({ id: entry.issue.id, disabled: !sortable })
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        'flex items-center gap-2 px-3 py-2 bg-card',
        isDragging && 'relative z-10 shadow-lg ring-1 ring-border rounded-md',
      )}
      data-testid="queue-row"
      data-item-id={entry.issue.id}
    >
      {sortable ? (
        <button
          type="button"
          className="flex h-7 w-5 shrink-0 cursor-grab items-center justify-center rounded text-zinc-400 hover:text-foreground active:cursor-grabbing focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring touch-none"
          aria-label={`Reorder ${entry.issue.title}`}
          {...attributes}
          {...listeners}
        >
          <Icon name="grip-vertical" size={14} aria-hidden="true" />
        </button>
      ) : <span className="w-5 shrink-0" />}
      <span className="w-5 shrink-0 text-right text-[11px] tabular-nums text-muted-foreground">{index}</span>
      <WorkItemCard item={entry.issue} onOpen={onOpen} layout="row" dragging={isDragging} />
      <StatusBadge status={entry.issue.status} className="hidden md:inline-flex" />
      {toggle}
    </li>
  )
}

function Section({ id, title, icon, hint, count, children, empty }) {
  return (
    <section aria-labelledby={`${id}-title`} className="space-y-2" data-testid={`section-${id}`}>
      <div className="flex items-center gap-2 px-1">
        <Icon name={icon} size={14} className="text-muted-foreground" aria-hidden="true" />
        <h2 id={`${id}-title`} className="text-[13px] font-semibold">{title}</h2>
        <span className="rounded-full bg-muted px-1.5 text-[11px] tabular-nums text-muted-foreground">{count}</span>
        {hint && <span className="text-[11.5px] text-muted-foreground">{hint}</span>}
      </div>
      {count === 0 && empty
        ? <p className="rounded-lg border border-dashed border-border px-4 py-3 text-[12px] text-muted-foreground">{empty}</p>
        : <ol className="divide-y divide-border overflow-hidden rounded-lg border border-border">{children}</ol>}
    </section>
  )
}

function QueueList({ queue, ownerRef, isOwner, onChange, onOpen }) {
  const { toast } = useToast()
  const [busy, setBusy] = useState(false)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  // In progress first (FR-34); Pinned and Queue hold everything else, in queue order.
  const all = [...queue.groups.pinned, ...queue.groups.rest]
  const indexOf = new Map(all.map((e, i) => [e.issue.id, i + 1]))
  const inProgress = all.filter((e) => e.issue.status === 'in_progress')
  const pinned = queue.groups.pinned.filter((e) => e.issue.status !== 'in_progress')
  const rest = queue.groups.rest.filter((e) => e.issue.status !== 'in_progress')
  const sortable = queue.can_reorder

  const run = async (call, fallback) => {
    setBusy(true)
    try {
      const res = await call()
      onChange(res.data)
    } catch (err) {
      toast.error(errorDetail(err, fallback))
    } finally {
      setBusy(false)
    }
  }

  const handleDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return
    const pinnedIds = pinned.map((e) => e.issue.id)
    const restIds = rest.map((e) => e.issue.id)
    const from = pinnedIds.includes(active.id) ? pinnedIds : restIds
    const to = pinnedIds.includes(over.id) ? pinnedIds : restIds
    if (from !== to) {
      // Across the pin boundary — the server explains why not (queue_group_boundary).
      run(() => queueApi.move(ownerRef, { issueId: active.id, beforeId: over.id }), 'Could not move that item.')
      return
    }
    const oldIndex = from.indexOf(active.id)
    const newIndex = from.indexOf(over.id)
    const anchor = newIndex > oldIndex ? { afterId: over.id } : { beforeId: over.id }
    // Optimistic: the row lands, then the server's order replaces it.
    const moved = arrayMove(from, oldIndex, newIndex)
    const group = from === pinnedIds ? 'pinned' : 'rest'
    const byId = new Map(queue.groups[group].map((e) => [e.issue.id, e]))
    const others = queue.groups[group].filter((e) => !from.includes(e.issue.id))
    onChange({ ...queue, groups: { ...queue.groups, [group]: [...moved.map((id) => byId.get(id)), ...others] } })
    run(() => queueApi.move(ownerRef, { issueId: active.id, ...anchor }), 'Could not reorder the queue.')
  }

  const toggle = (entry) => (
    <PinToggle
      entry={entry}
      queue={queue}
      isOwner={isOwner}
      busy={busy}
      onPin={(e) => run(() => queueApi.pin(ownerRef, e.issue.id), 'Could not pin that item.')}
      onUnpin={(e) => run(() => queueApi.unpin(ownerRef, e.issue.id), 'Could not unpin that item.')}
    />
  )

  const rows = (entries, canSort) => entries.map((entry) => (
    <QueueRow
      key={entry.issue.id}
      entry={entry}
      index={indexOf.get(entry.issue.id)}
      sortable={canSort}
      onOpen={onOpen}
      toggle={toggle(entry)}
    />
  ))

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-7 py-5">
      {inProgress.length > 0 && (
        <Section id="in-progress" title="In progress" icon="loader" count={inProgress.length}>
          {rows(inProgress, false)}
        </Section>
      )}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <Section
          id="pinned"
          title="Pinned"
          icon="pin"
          count={pinned.length}
          hint={`${queue.pins_used} of ${queue.pin_limit} pins · always on top`}
          empty={queue.can_pin ? `Pin up to ${queue.pin_limit} items to keep them on top, whatever arrives.` : 'Nothing pinned.'}
        >
          <SortableContext items={pinned.map((e) => e.issue.id)} strategy={verticalListSortingStrategy}>
            {rows(pinned, sortable)}
          </SortableContext>
        </Section>
        <Section
          id="queue"
          title="Queue"
          icon="list-ordered"
          count={rest.length}
          hint={sortable ? 'Drag to reorder · new work is placed by priority, due date, reports, then age' : null}
          empty="Nothing else queued."
        >
          <SortableContext items={rest.map((e) => e.issue.id)} strategy={verticalListSortingStrategy}>
            {rows(rest, sortable)}
          </SortableContext>
        </Section>
      </DndContext>
    </div>
  )
}

function ListSkeleton() {
  const pulse = 'animate-pulse rounded bg-zinc-200 dark:bg-zinc-700'
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-7 py-5" aria-hidden="true">
      {[2, 5].map((n, s) => (
        <div key={s} className="space-y-2">
          <div className={`h-4 w-24 ${pulse}`} />
          <div className="divide-y divide-border rounded-lg border border-border">
            {Array.from({ length: n }, (_, i) => (
              <div key={i} className="flex items-center gap-3 px-3 py-3">
                <div className={`h-3 flex-1 ${pulse}`} />
                <div className={`h-3 w-20 ${pulse}`} />
                <div className={`h-3 w-4 ${pulse}`} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Kanban view ─────────────────────────────────────────────────────────────

function QueueBoard({ ownerRef, onOpen, refreshKey }) {
  const { toast } = useToast()
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    setError(null)
    return queueApi.board(ownerRef)
      .then((res) => setItems(res.data.columns.flatMap((c) => c.items)))
      .catch((err) => setError(errorDetail(err, 'Could not load the board.')))
  }, [ownerRef])

  useEffect(() => { load() }, [load, refreshKey])

  // Dragging between columns is a status change; order within a column is the
  // queue's — reorder in the list view (AC-41 holds by construction).
  const move = useCallback(async (issue, to) => {
    setItems((prev) => prev.map((i) => (i.id === issue.id ? { ...i, status: to } : i)))
    try {
      await issuesApi.transition(issue.id, { to })
    } catch (err) {
      toast.error(errorDetail(err, `Could not move ${issue.key ?? 'that item'}`))
    } finally {
      load()
    }
  }, [load, toast])

  if (error) {
    return (
      <div role="alert" className="py-16 text-center text-sm text-muted-foreground">
        {error}
        <Button variant="outline" size="sm" className="ml-3" onClick={load}>Retry</Button>
      </div>
    )
  }
  if (!items) return <IssueBoardSkeleton />
  return (
    <div className="overflow-x-auto scrollbar-thin">
      <IssueBoard
        issues={items}
        onOpen={onOpen}
        onStatusChange={move}
        emptyText={{ done: 'Nothing done in the last 7 days' }}
      />
    </div>
  )
}

// ─── History drawer ──────────────────────────────────────────────────────────

const HISTORY_VERB = { reorder: 'moved', pin: 'pinned', unpin: 'unpinned' }
const HISTORY_ICON = { reorder: 'arrow-up-down', pin: 'pin', unpin: 'pin-off' }

function HistoryDrawer({ open, onClose, ownerRef }) {
  const [state, setState] = useState({ items: [], total: 0, page: 0, loading: false, error: null })

  const loadPage = useCallback((page) => {
    setState((s) => ({ ...s, loading: true, error: null }))
    queueApi.history(ownerRef, { page, size: 30 })
      .then((res) => setState((s) => ({
        items: page === 1 ? res.data.items : [...s.items, ...res.data.items],
        total: res.data.total, page, loading: false, error: null,
      })))
      .catch((err) => setState((s) => ({ ...s, loading: false, error: errorDetail(err, 'Could not load the history.') })))
  }, [ownerRef])

  useEffect(() => { if (open) loadPage(1) }, [open, loadPage])

  return (
    <Sheet open={open} onClose={onClose} title="Queue history" width="w-full max-w-[440px]">
      <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-4" data-testid="queue-history">
        <p className="mb-3 text-[12px] text-muted-foreground">
          Every reorder, pin and unpin, by whoever made it. Items entering or leaving on their own aren’t listed.
        </p>
        {state.error ? (
          <p role="alert" className="text-sm text-muted-foreground">{state.error}</p>
        ) : state.items.length === 0 && state.loading ? (
          <div className="space-y-3" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex gap-2.5">
                <div className="h-7 w-7 shrink-0 animate-pulse rounded-full bg-zinc-200 dark:bg-zinc-700" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 w-3/4 animate-pulse rounded bg-zinc-200 dark:bg-zinc-700" />
                  <div className="h-2.5 w-24 animate-pulse rounded bg-zinc-200 dark:bg-zinc-700" />
                </div>
              </div>
            ))}
          </div>
        ) : state.items.length === 0 ? (
          <Empty icon="history" title="No changes yet" body="Reorders and pins show up here." />
        ) : (
          <ol className="space-y-3">
            {state.items.map((h) => (
              <li key={h.id} className="flex gap-2.5" data-testid="history-item">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                  <Icon name={HISTORY_ICON[h.action]} size={13} aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1 text-[12.5px] leading-snug">
                  <p>
                    <span className="inline-flex items-center gap-1 font-medium">
                      {h.actor && <Avatar user={h.actor} size={14} />}
                      {h.actor?.name ?? 'Someone'}
                    </span>{' '}
                    <span className="text-muted-foreground">{HISTORY_VERB[h.action]}</span>{' '}
                    {h.issue_id && <IssueHoverCard issueId={h.issue_id} label={h.issue_key} />}{' '}
                    <span className="text-foreground">{h.issue_title}</span>
                  </p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground tabular-nums">
                    {h.old_index != null && h.new_index != null && <>#{h.old_index} → #{h.new_index} · </>}
                    <span title={fullTime(h.created_at)}>{relTime(h.created_at)}</span>
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
        {state.items.length < state.total && (
          <Button variant="outline" size="sm" className="mt-4 w-full" loading={state.loading} onClick={() => loadPage(state.page + 1)}>
            Load more
          </Button>
        )}
      </div>
    </Sheet>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function MyWorkPage() {
  const { username } = useParams()
  const { user } = useApp()
  const navigate = useNavigate()
  const owner = useOwner(username, user)
  const isOwner = owner.ref === 'me'
  const [view, setView] = useState(() => readView(user?.id))
  const [queue, setQueue] = useState(null)
  const [error, setError] = useState(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const changeView = (next) => { setView(next); writeView(user?.id, next) }

  const load = useCallback(() => {
    if (owner.ref == null) return
    setError(null)
    queueApi.get(owner.ref)
      .then((res) => setQueue(res.data))
      .catch((err) => setError(err.response?.status === 403
        ? 'Only the owner, a CTO or an Admin can see this queue.'
        : errorDetail(err, 'Could not load the queue.')))
  }, [owner.ref])

  useEffect(() => { setQueue(null); load() }, [load])

  const openItem = (issue) => navigate(`/issue/${issueSlug(issue)}`)

  const openCount = queue ? queue.groups.pinned.length + queue.groups.rest.length : null

  if (owner.error) return <Empty icon="user-x" title="User not found" body={`There's no user called “${username}”.`} />

  const ownerName = owner.user?.name ?? queue?.owner?.name
  const title = isOwner ? 'My Work' : `${ownerName ?? '…'}’s work`

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="border-b border-border px-7 pb-3 pt-5">
        {!isOwner && (
          <nav aria-label="Breadcrumb" className="text-xs text-muted-foreground">
            <Link to={`/u/${username}`} className="hover:text-foreground">{ownerName ?? username}</Link>
          </nav>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-bold">{title}</h1>
          {queue && (
            <span className="text-xs tabular-nums text-muted-foreground">
              {openCount} open · {queue.pins_used}/{queue.pin_limit} pinned
            </span>
          )}
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {isOwner && user && (
              <Link
                to={`/issues?reporter=${user.id}`}
                className="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[12px] text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Icon name="user-pen" size={13} aria-hidden="true" />
                Reported by me
              </Link>
            )}
            <Button variant="outline" size="sm" onClick={() => setHistoryOpen(true)} disabled={owner.ref == null}>
              <Icon name="history" size={13} aria-hidden="true" />
              History
            </Button>
            <Segmented
              value={view}
              onValueChange={changeView}
              options={[
                { value: 'list', label: 'List', icon: <Icon name="list-ordered" size={13} /> },
                { value: 'kanban', label: 'Kanban', icon: <Icon name="kanban" size={13} /> },
              ]}
            />
          </div>
        </div>
        <p className="mt-1 text-[13px] text-muted-foreground">
          {isOwner
            ? 'Everything assigned to you across projects, in the order to work on it.'
            : `You can ${queue?.can_reorder ? 'reorder and pin' : 'view'} this queue. ${ownerName ?? 'They'} will be notified of changes.`}
        </p>
      </header>

      <div className="min-h-0 flex-1 overflow-auto scrollbar-thin">
        {error ? (
          <div role="alert" className="py-16 text-center text-sm text-muted-foreground">
            {error}
            <Button variant="outline" size="sm" className="ml-3" onClick={load}>Retry</Button>
          </div>
        ) : view === 'kanban' ? (
          owner.ref != null
            ? <QueueBoard ownerRef={owner.ref} onOpen={openItem} refreshKey={refreshKey} />
            : <IssueBoardSkeleton />
        ) : !queue ? (
          <ListSkeleton />
        ) : openCount === 0 ? (
          <Empty
            icon="list-todo"
            title={isOwner ? 'Nothing assigned to you' : 'Nothing assigned'}
            body="Open items assigned across every project show up here — To do, Rejected, In progress, in review and Blocked."
          />
        ) : (
          <QueueList
            queue={queue}
            ownerRef={owner.ref}
            isOwner={isOwner}
            onOpen={openItem}
            onChange={(next) => { setQueue(next); setRefreshKey((k) => k + 1) }}
          />
        )}
      </div>

      <HistoryDrawer open={historyOpen} onClose={() => setHistoryOpen(false)} ownerRef={owner.ref ?? 'me'} />
    </div>
  )
}
