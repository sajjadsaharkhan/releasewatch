import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { IssueBoard, IssueBoardSkeleton } from '../common/IssueBoard'
import { IssueTable, IssueTableSkeleton } from '../common/IssueTable'
import { DoneRangePicker, doneRangeToApi, doneRangeLabel } from '../common/DoneRangePicker'
import { Button } from '../ui/Button'
import { Empty } from '../ui/Empty'
import { releasesApi, issuesApi } from '../../lib/api'
import { issueSlug } from '../../lib/issueSlug'
import { useToast } from '../../hooks/useToast'

// A container's Board and Items tabs (FR-47, FR-51) — the Stream page and the
// release page share it. The board comes from GET /releases/{id}/board; only
// the Done column is bounded, by `doneRange` (the Stream's time picker).
export function ContainerWork({ container, view, readOnly = false, doneRange = null, onDoneRangeChange, refreshKey = 0, onChanged }) {
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
        const res = await releasesApi.items(container.id)
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

  const move = useCallback(async (issue, to) => {
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
  }, [load, onChanged, toast])

  const toolbar = view === 'board' && doneRange && (
    <div className="flex items-center justify-end gap-2 px-7 pt-4">
      <DoneRangePicker value={doneRange} onChange={onDoneRangeChange} />
    </div>
  )

  if (error) {
    return (
      <div role="alert" className="py-16 text-center text-sm text-muted-foreground">
        {error}
        <Button variant="outline" size="sm" className="ml-3" onClick={load}>Retry</Button>
      </div>
    )
  }

  if (view === 'board') {
    return (
      <>
        {toolbar}
        {loading && !data ? (
          <IssueBoardSkeleton />
        ) : (
          <div className={cn('overflow-x-auto scrollbar-thin', loading && 'opacity-60 transition-opacity')} aria-busy={loading}>
            <IssueBoard
              issues={data ?? []}
              onOpen={open}
              onStatusChange={readOnly ? undefined : move}
              readOnly={readOnly}
              emptyText={doneRange ? { done: `Nothing done · ${doneRangeLabel(doneRange).toLowerCase()}` } : {}}
            />
          </div>
        )}
      </>
    )
  }

  if (loading && !data) return <IssueTableSkeleton rows={6} hideRelease />
  if (!data?.length) {
    return (
      <Empty
        icon={container.kind === 'stream' ? 'waves' : 'package'}
        title="No items yet"
        body={container.kind === 'stream'
          ? 'Items placed in the Stream ship on their own when they’re Done.'
          : 'Move items here from the backlog, or pick this release when filing one.'}
      />
    )
  }
  return <IssueTable issues={data} onOpen={open} hideRelease />
}
