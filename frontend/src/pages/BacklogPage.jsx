import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors,
} from '@dnd-kit/core'
import {
  SortableContext, arrayMove, sortableKeyboardCoordinates, verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { Clock, Construction, Layers, ListOrdered } from 'lucide-react'
import { useApp } from '../hooks/useApp'
import { backlogApi, issuesApi } from '../lib/api'
import { useContainers } from '../hooks/useContainers'
import { issueSlug } from '../lib/issueSlug'
import { cn } from '../lib/cn'
import { Button, Empty, Segmented, Switch, useToast } from '../components/ui'
import {
  BacklogGroupHeader, BacklogRow, BacklogRowsSkeleton, BulkMoveBar, groupMeta,
} from '../components/backlog'

/**
 * A project's backlog (slice 08, FR-23–25): its open items with no container, as
 * a ranked list — never a board. Grouped by category by default, or flat in
 * rank order. Drag (pointer or keyboard) to rank; select to move many to a
 * container (the Stream or a release) at once. Technical debt is hidden unless "Show technical debt" is on.
 *
 * Membership, grouping, the stale rule and who may manage all come from the
 * API — this page only renders them. View and debt toggle live in the URL.
 */


const DND_SCREEN_READER = {
  draggable:
    'To pick up an item, press Space or Enter. Use the arrow keys to move it, ' +
    'then press Space or Enter to drop it, or Escape to cancel.',
}

function moveAfter(items, id, afterId, beforeId) {
  const moved = items.find((i) => i.id === id)
  const rest = items.filter((i) => i.id !== id)
  let at = afterId != null ? rest.findIndex((i) => i.id === afterId) + 1 : rest.findIndex((i) => i.id === beforeId)
  if (at < 0) at = rest.length
  rest.splice(at, 0, moved)
  return rest
}

export default function BacklogPage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const { projects, activeProjectId, switchProject } = useApp()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()

  const view = searchParams.get('view') === 'ranked' ? 'ranked' : 'grouped'
  const showDebt = searchParams.get('debt') === '1'
  const project = projects?.find((p) => p.slug === slug)

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [collapsed, setCollapsed] = useState(() => new Set())
  const [selected, setSelected] = useState(() => new Set())
  const [rowErrors, setRowErrors] = useState({})
  const [releaseId, setReleaseId] = useState(null)
  const [moving, setMoving] = useState(false)
  const [categorizing, setCategorizing] = useState(false)
  const lastClicked = useRef(null)

  // ── Keep the URL's project and the active project in step ────────────────
  // The URL wins whenever it names a project: the active project is switched
  // to it. Only once they agree does a later change of the active project
  // (the topbar switcher) move the page to that project's backlog — so the
  // saved active project restoring after mount never overrides the URL.
  const synced = useRef(false)
  const urlProjectId = useRef(null)
  useEffect(() => {
    if (!project) return
    if (urlProjectId.current !== project.id) {
      urlProjectId.current = project.id
      synced.current = false
    }
    if (activeProjectId === project.id) {
      synced.current = true
      return
    }
    if (!synced.current) {
      switchProject(project.id)
      return
    }
    const next = projects.find((p) => p.id === activeProjectId)
    if (next) navigate(`/projects/${next.slug}/backlog?${searchParams.toString()}`)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id, activeProjectId])

  // ── Data ─────────────────────────────────────────────────────────────────
  const load = useCallback(async ({ silent = false } = {}) => {
    if (!project) return
    if (!silent) setLoading(true)
    try {
      const res = await backlogApi.get(project.id, {
        group_by: 'category',
        include_tech_debt: showDebt || undefined,
      })
      setData(res.data)
      setLoadError(null)
    } catch (err) {
      setLoadError(err.response?.data?.detail || 'The backlog could not be loaded.')
      toast.error('Failed to load backlog', err.response?.data?.detail)
    } finally {
      setLoading(false)
    }
  }, [project?.id, showDebt, toast]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load() }, [load])

  // Selection and errors belong to one project's list.
  useEffect(() => {
    setSelected(new Set())
    setRowErrors({})
    setReleaseId(null)
  }, [project?.id])

  const { streamId, releases } = useContainers(project?.id)

  // ── Derived ──────────────────────────────────────────────────────────────
  const items = data?.items ?? []
  const byId = useMemo(() => new Map(items.map((i) => [i.id, i])), [items])
  const stale = useMemo(() => new Set(data?.stale_item_ids ?? []), [data])
  const canManage = (data?.allowed_actions ?? []).includes('manage_backlog')
  const manageReason = data?.blocked_actions?.find((b) => b.action === 'manage_backlog')?.detail
  const groups = (data?.groups ?? []).map((g) => ({
    ...g, items: g.item_ids.map((id) => byId.get(id)).filter(Boolean),
  }))
  // The order rows appear in — shift-click ranges follow it.
  const visibleOrder = view === 'ranked'
    ? items.map((i) => i.id)
    : groups.flatMap((g) => (collapsed.has(g.key) ? [] : g.item_ids))

  const setParam = (key, value) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    setSearchParams(next, { replace: true })
  }

  // ── Selection ────────────────────────────────────────────────────────────
  const onSelect = (id, next, event) => {
    setSelected((prev) => {
      const out = new Set(prev)
      if (event?.shiftKey && lastClicked.current != null) {
        const a = visibleOrder.indexOf(lastClicked.current)
        const b = visibleOrder.indexOf(id)
        if (a >= 0 && b >= 0) {
          visibleOrder.slice(Math.min(a, b), Math.max(a, b) + 1).forEach((x) => (next ? out.add(x) : out.delete(x)))
          return out
        }
      }
      next ? out.add(id) : out.delete(id)
      return out
    })
    lastClicked.current = id
  }

  const selectGroup = (ids, next) => setSelected((prev) => {
    const out = new Set(prev)
    ids.forEach((x) => (next ? out.add(x) : out.delete(x)))
    return out
  })

  const clearSelection = useCallback(() => {
    setSelected(new Set())
    setRowErrors({})
  }, [])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'Escape' || selected.size === 0) return
      if (e.target.closest?.('input, textarea, [role="listbox"], [data-bulk-bar]')) return
      clearSelection()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selected.size, clearSelection])

  // ── Ranking ──────────────────────────────────────────────────────────────
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const keyOf = (id) => byId.get(id)?.key ?? 'item'
  const announcements = {
    onDragStart: ({ active }) => `Picked up ${keyOf(active.id)}.`,
    onDragOver: ({ active, over }) =>
      over ? `${keyOf(active.id)} is over ${keyOf(over.id)}.` : `${keyOf(active.id)} is not over a position.`,
    onDragEnd: ({ active, over }) =>
      over ? `${keyOf(active.id)} was placed at the position of ${keyOf(over.id)}.` : `${keyOf(active.id)} was dropped.`,
    onDragCancel: ({ active }) => `Moving ${keyOf(active.id)} was cancelled.`,
  }

  const onDragEnd = async ({ active, over }) => {
    if (!over || active.id === over.id) return
    // Grouped view ranks within a group; dropping into another group would
    // change its category, which dragging doesn't do.
    const list = view === 'ranked'
      ? items.map((i) => i.id)
      : groups.find((g) => g.item_ids.includes(active.id))?.item_ids
    if (!list || !list.includes(over.id)) return

    const nextList = arrayMove(list, list.indexOf(active.id), list.indexOf(over.id))
    const at = nextList.indexOf(active.id)
    const afterId = nextList[at - 1] ?? null
    const beforeId = nextList[at + 1] ?? null

    const snapshot = data
    setData((d) => ({
      ...d,
      items: moveAfter(d.items, active.id, afterId, beforeId),
      groups: d.groups?.map((g) => (g.item_ids.includes(active.id) ? { ...g, item_ids: nextList } : g)),
    }))
    try {
      await backlogApi.reorder(project.id, { issueId: active.id, afterId, beforeId })
    } catch (err) {
      setData(snapshot)
      toast.error("Couldn't save the new order", err.response?.data?.detail)
    }
  }

  // ── Bulk move ────────────────────────────────────────────────────────────
  const onMove = async () => {
    const ids = visibleOrder.filter((id) => selected.has(id))
    const extra = [...selected].filter((id) => !ids.includes(id))
    const all = [...ids, ...extra]
    const target = releaseId === streamId ? 'the Stream' : releases.find((r) => r.id === releaseId)?.version
    setMoving(true)
    try {
      await issuesApi.bulkMove(all, releaseId)
      toast({ title: `Moved ${all.length} ${all.length === 1 ? 'item' : 'items'} to ${target}` })
      clearSelection()
      setReleaseId(null)
      load({ silent: true })
    } catch (err) {
      const body = err.response?.data
      if ((body?.code === 'bulk_move_failed' || body?.code === 'done_item_immobile') && body.errors) {
        setRowErrors(body.errors)
        const n = Object.keys(body.errors).length
        toast.error('Nothing was moved', `${n} of ${all.length} items can't go to ${target}. They're marked in the list.`)
      } else {
        toast.error("Couldn't move the items", body?.detail)
      }
    } finally {
      setMoving(false)
    }
  }

  // ── Bulk category ────────────────────────────────────────────────────────
  const selectedInOrder = () => [
    ...visibleOrder.filter((id) => selected.has(id)),
    ...[...selected].filter((id) => !visibleOrder.includes(id)),
  ]

  const onSetCategory = async (category) => {
    const all = selectedInOrder()
    const label = category.name
    setCategorizing(true)
    try {
      const res = await backlogApi.setCategory(project.id, all, category.id)
      const n = res.data.updated_ids.length
      toast({
        title: n === 0
          ? `Already in ${label}`
          : `Moved ${n} ${n === 1 ? 'item' : 'items'} to ${label}`,
      })
      clearSelection()
      load({ silent: true })
    } catch (err) {
      const body = err.response?.data
      if (body?.code === 'bulk_category_failed' && body.errors) {
        setRowErrors(body.errors)
        toast.error('No categories were changed', `${Object.keys(body.errors).length} of ${all.length} items can't be changed. They're marked in the list.`)
      } else {
        toast.error("Couldn't change the category", body?.detail)
      }
    } finally {
      setCategorizing(false)
    }
  }

  const openItem = (item) => navigate(`/issue/${issueSlug(item)}`)

  // ── Routing states ───────────────────────────────────────────────────────
  if (!slug) {
    const target = projects?.find((p) => p.id === activeProjectId) ?? projects?.[0]
    if (target) return <Navigate to={`/projects/${target.slug}/backlog`} replace />
    if (!projects?.length) return <Empty icon="list-ordered" title="No projects yet" body="Create a project to start a backlog." />
    return null
  }
  if (projects?.length && !project) {
    return <Empty icon="list-ordered" title="Project not found" body={`There's no project called “${slug}”.`} />
  }

  const renderRow = (item, rank) => (
    <BacklogRow
      key={item.id}
      item={item}
      rank={rank}
      selected={selected.has(item.id)}
      onSelect={onSelect}
      canManage={canManage}
      manageReason={manageReason}
      stale={stale.has(item.id)}
      error={rowErrors[String(item.id)]}
      onOpen={openItem}
    />
  )

  const total = data?.total ?? 0
  const hidden = data?.hidden_tech_debt_count ?? 0

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="flex items-baseline gap-2 text-lg font-semibold text-foreground">
            Backlog
            {project && <span className="truncate text-sm font-normal text-muted-foreground">{project.name}</span>}
          </h1>
          <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-[12.5px] text-muted-foreground">
            {loading && !data ? (
              <span className="inline-block h-3 w-40 rounded bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
            ) : (
              <>
                <span className="tabular-nums">{total} {total === 1 ? 'item' : 'items'}</span>
                {data?.stale_count > 0 && (
                  <>
                    <span aria-hidden="true">·</span>
                    <span className="inline-flex items-center gap-1 text-amber-700 dark:text-amber-400">
                      <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                      <span className="tabular-nums">{data.stale_count}</span> untouched for over 6 months
                    </span>
                  </>
                )}
              </>
            )}
          </p>
        </div>
        {project && (
          <Button variant="outline" size="sm" onClick={() => navigate(`/tech-debt?project=${project.id}`)}>
            <Construction className="h-3.5 w-3.5" aria-hidden="true" />
            Technical debt in this project
          </Button>
        )}
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          value={view}
          onValueChange={(v) => setParam('view', v === 'ranked' ? 'ranked' : null)}
          options={[
            { value: 'grouped', label: 'Grouped', icon: <Layers className="h-3.5 w-3.5" /> },
            { value: 'ranked', label: 'Ranked', icon: <ListOrdered className="h-3.5 w-3.5" /> },
          ]}
        />
        <label className="flex cursor-pointer items-center gap-2 text-[12.5px] text-muted-foreground">
          <Switch
            checked={showDebt}
            onCheckedChange={(v) => setParam('debt', v ? '1' : null)}
            aria-label="Show technical debt"
          />
          <span className="text-foreground">Show technical debt</span>
          {!showDebt && hidden > 0 && (
            <span className="rounded-full bg-muted px-1.5 text-[10.5px] font-medium tabular-nums">{hidden} hidden</span>
          )}
        </label>
      </div>

      {/* List */}
      {loading && !data ? (
        <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          <BacklogRowsSkeleton />
        </div>
      ) : loadError && !data ? (
        <div className="rounded-xl border border-border bg-card shadow-sm">
          <Empty icon="alert-circle" title="Failed to load backlog" body={loadError}>
            <Button size="sm" variant="outline" onClick={() => load()}>Try again</Button>
          </Empty>
        </div>
      ) : total === 0 ? (
        <div className="rounded-xl border border-border bg-card shadow-sm">
          {hidden > 0 ? (
            <Empty
              icon="construction"
              title="Only technical debt here"
              body={`${hidden} technical-debt ${hidden === 1 ? 'task is' : 'tasks are'} hidden.`}
            >
              <Button size="sm" variant="outline" onClick={() => setParam('debt', '1')}>Show technical debt</Button>
            </Empty>
          ) : (
            <Empty
              icon="list-ordered"
              title="Backlog is empty"
              body="Work that isn't planned yet lands here — tasks created without a place, bugs accepted into the backlog, and items taken out of the Stream or a release."
            />
          )}
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={onDragEnd}
          accessibility={{ announcements, screenReaderInstructions: DND_SCREEN_READER }}
        >
          <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
            {view === 'ranked' ? (
              <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
                <ul aria-label="Backlog, in rank order">
                  {items.map((item, idx) => renderRow(item, idx + 1))}
                </ul>
              </SortableContext>
            ) : (
              groups.map((g) => {
                const open = !collapsed.has(g.key)
                const label = groupMeta(g).label
                return (
                  <section key={g.key} aria-label={label}>
                    <BacklogGroupHeader
                      group={g}
                      open={open}
                      canManage={canManage}
                      selectedCount={g.item_ids.filter((id) => selected.has(id)).length}
                      onSelectAll={(next) => selectGroup(g.item_ids, next)}
                      onToggle={() => setCollapsed((prev) => {
                        const out = new Set(prev)
                        out.has(g.key) ? out.delete(g.key) : out.add(g.key)
                        return out
                      })}
                    />
                    {open && (
                      <div id={`backlog-group-${g.key}`}>
                        {g.items.length === 0 ? (
                          <p className="border-b border-border px-14 py-2.5 text-[12px] italic text-muted-foreground">
                            Nothing in {label} yet.
                          </p>
                        ) : (
                          <SortableContext items={g.item_ids} strategy={verticalListSortingStrategy}>
                            <ul aria-label={label}>{g.items.map((item) => renderRow(item, null))}</ul>
                          </SortableContext>
                        )}
                      </div>
                    )}
                  </section>
                )
              })
            )}
          </div>
          {canManage && (
            <p className={cn('text-[11.5px] text-muted-foreground', view === 'grouped' && 'pt-0.5')}>
              Drag the handle to rank{view === 'grouped' ? ' within a group' : ''} — or focus it and press Space, then the arrow keys.
              Shift-click checkboxes to select a range.
            </p>
          )}
        </DndContext>
      )}

      {canManage && (
        <BulkMoveBar
          count={selected.size}
          projectId={project?.id}
          releaseId={releaseId}
          onReleaseChange={setReleaseId}
          onMove={onMove}
          onClear={clearSelection}
          moving={moving}
          categories={groups.filter((g) => g.category).map((g) => g.category)}
          selectedCategories={[...selected].map((id) => byId.get(id)?.backlog_category_id ?? null)}
          onSetCategory={onSetCategory}
          categorizing={categorizing}
        />
      )}
    </div>
  )
}
