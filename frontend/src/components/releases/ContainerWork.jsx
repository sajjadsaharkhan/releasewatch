import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { IssueBoard, IssueBoardSkeleton } from '../common/IssueBoard'
import { IssueTable, IssueTableSkeleton } from '../common/IssueTable'
import { doneRangeToApi, doneRangeLabel } from '../common/DoneRangePicker'
import { Button } from '../ui/Button'
import { Empty } from '../ui/Empty'
import { WorkContext } from '../common/WorkContext'
import { ProductionBar } from './ProductionBar'
import { SelectAllVerified } from './SelectAllVerified'
import { DONE_AT_SHIP_TEXT } from '../../lib/constants'
import { releasesApi, issuesApi } from '../../lib/api'
import { issueSlug } from '../../lib/issueSlug'
import { useToast } from '../../hooks/useToast'

// A container's Board and Items tabs (FR-47, FR-51) — the Stream page and the
// release page share it. Board and Items share one range: `doneRange` (the
// Stream's time picker, which the page puts on its tab row) bounds Done items only.
export function ContainerWork({ container, view, readOnly = false, doneRange = null, refreshKey = 0, onChanged }) {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [data, setData] = useState(null) // board: issues[]; items: issues[]
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Keyed by value: the page rebuilds `doneRange` from the URL on every render.
  const rangeKey = doneRange ? JSON.stringify(doneRange) : ''
  const params = useMemo(() => (doneRange ? doneRangeToApi(doneRange) : undefined), [rangeKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      if (view === 'board') {
        const res = await releasesApi.board(container.id, params)
        setData(res.data.columns.flatMap((c) => c.items))
      } else {
        const res = await releasesApi.items(container.id, params)
        setData(res.data.items)
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load the items.')
    } finally {
      setLoading(false)
    }
  }, [container.id, view, params])

  useEffect(() => { load() }, [load, refreshKey])

  const open = (issue) => navigate(`/issue/${issueSlug(issue)}`)

  // On production (FR-67): in the Stream only, Verified items can be selected.
  // Shift-click selects the range between the last click and this one.
  const isStream = container.kind === 'stream'
  const [selected, setSelected] = useState(() => new Set())
  const anchor = useRef(null)
  const isSelectable = useCallback(
    (item) => isStream && !readOnly && item.status === 'verified'
      && (item.allowed_actions ? item.allowed_actions.includes('mark_production') : true),
    [isStream, readOnly],
  )
  const selectableItems = useMemo(() => (data ?? []).filter(isSelectable), [data, isSelectable])
  // A refresh may have taken items out of Verified — drop them from the selection.
  useEffect(() => {
    setSelected((prev) => {
      const live = new Set(selectableItems.map((i) => i.id))
      const next = new Set([...prev].filter((id) => live.has(id)))
      return next.size === prev.size ? prev : next
    })
  }, [selectableItems])
  const toggle = useCallback((item, shiftKey) => {
    // Read the anchor now: the updater below runs later, after it moves.
    const anchorId = anchor.current
    anchor.current = item.id
    setSelected((prev) => {
      const next = new Set(prev)
      const ids = selectableItems.map((i) => i.id)
      const from = anchorId != null ? ids.indexOf(anchorId) : -1
      const to = ids.indexOf(item.id)
      if (shiftKey && from >= 0 && to >= 0) {
        const [a, b] = from < to ? [from, to] : [to, from]
        ids.slice(a, b + 1).forEach((id) => next.add(id))
      } else if (next.has(item.id)) next.delete(item.id)
      else next.add(item.id)
      return next
    })
  }, [selectableItems])
  const selectAll = useCallback(() => setSelected(new Set(selectableItems.map((i) => i.id))), [selectableItems])
  const clear = useCallback(() => setSelected(new Set()), [])
  const workContext = useMemo(() => ({
    containerKind: container.kind,
    selection: isStream && !readOnly
      ? { selected, isSelectable, toggle, selectAll, clear, total: selectableItems.length }
      : null,
  }), [container.kind, isStream, readOnly, selected, isSelectable, toggle, selectAll, clear, selectableItems.length])
  const selectedItems = selectableItems.filter((i) => selected.has(i.id))

  const move = useCallback(async (issue, to) => {
    // Done at ship (BR-67): a release item never gets there by a move.
    if (to === 'done' && !isStream) {
      toast.error(DONE_AT_SHIP_TEXT)
      return
    }
    // Optimistic: the card lands in its new column, then the server decides.
    setData((prev) => prev.map((i) => (i.id === issue.id ? { ...i, status: to } : i)))
    try {
      await issuesApi.transition(issue.id, { to })
      onChanged?.()
    } catch (err) {
      toast.error(err.response?.data?.detail || `Could not move ${issue.key ?? 'that item'}`)
    } finally {
      load()
    }
  }, [load, onChanged, toast, isStream])


  if (error) {
    return (
      <div role="alert" className="py-16 text-center text-sm text-muted-foreground">
        {error}
        <Button variant="outline" size="sm" className="ml-3" onClick={load}>Retry</Button>
      </div>
    )
  }

  const production = isStream ? (
    <ProductionBar
      items={selectedItems}
      total={selectableItems.length}
      onSelectAll={selectAll}
      onClear={clear}
      onDone={() => { setSelected(new Set()); load(); onChanged?.() }}
      onRefused={(ids) => { setSelected((prev) => new Set([...prev].filter((id) => !ids.includes(id)))); load() }}
    />
  ) : null

  if (view === 'board') {
    return (
      <WorkContext.Provider value={workContext}>
        {loading && !data ? (
          <IssueBoardSkeleton />
        ) : (
          <div className={cn('overflow-x-auto scrollbar-thin', loading && 'opacity-60 transition-opacity')} aria-busy={loading}>
            <IssueBoard
              issues={data ?? []}
              onOpen={open}
              onStatusChange={readOnly ? undefined : move}
              readOnly={readOnly}
              columnHeaderExtra={isStream && !readOnly ? { verified: <SelectAllVerified /> } : {}}
              lockedColumns={isStream ? {} : { done: DONE_AT_SHIP_TEXT }}
              emptyText={isStream
                ? (doneRange ? { done: `Nothing done · ${doneRangeLabel(doneRange).toLowerCase()}` } : {})
                : { done: 'Done after ship' }}
            />
          </div>
        )}
        {production}
      </WorkContext.Provider>
    )
  }

  if (loading && !data) return <IssueTableSkeleton rows={6} hideRelease />
  if (!data?.length) {
    return (
      <>
      <Empty
        icon={container.kind === 'stream' ? 'waves' : 'package'}
        title={doneRange ? 'Nothing in this range' : 'No items yet'}
        body={doneRange
          ? `No open items, and nothing was done in ${doneRangeLabel(doneRange).toLowerCase()}. Widen the range to see older work.`
          : container.kind === 'stream'
            ? 'Items placed in the Stream ship on their own when they’re Done.'
            : 'Move items here from the backlog, or pick this release when filing one.'}
      />
      </>
    )
  }
  return (
    <WorkContext.Provider value={workContext}>
      <div className={loading ? 'opacity-60 transition-opacity' : undefined} aria-busy={loading}>
        <IssueTable issues={data} onOpen={open} hideRelease />
      </div>
      {production}
    </WorkContext.Provider>
  )
}

