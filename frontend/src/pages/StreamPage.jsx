import React, { useEffect, useState } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { Icon } from '../components/ui/Icon'
import { Tabs } from '../components/ui/Tabs'
import { Empty } from '../components/ui/Empty'
import { ContainerWork } from '../components/releases'
import { IssueBoardSkeleton } from '../components/common/IssueBoard'
import { DoneRangePicker, readDoneRange, writeDoneRange } from '../components/common/DoneRangePicker'
import { projectsApi } from '../lib/api'
import { useProjectRoute } from '../hooks/useProjectRoute'

// The project's Stream (FR-46, FR-47): continuous work where every item ships
// on its own when it's Done. A five-column board and an items table. The
// Done column shows the last 7 days unless the time picker says otherwise; the
// range and the tab live in the URL. The Stream can't be edited, cancelled or
// deleted, so the page has no such controls.
export default function StreamPage() {
  const { slug, project, notFound, redirectTo } = useProjectRoute('stream')
  const [searchParams, setSearchParams] = useSearchParams()
  const view = searchParams.get('tab') === 'items' ? 'items' : 'board'
  const doneRange = readDoneRange(searchParams)
  const [stream, setStream] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!project) return
    setStream(null); setError(null)
    projectsApi.stream(project.id)
      .then((res) => setStream(res.data))
      .catch((err) => setError(err.response?.data?.detail || 'Could not load the Stream.'))
  }, [project?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!slug) return redirectTo ? <Navigate to={redirectTo} replace /> : <Empty icon="waves" title="No projects yet" />
  if (notFound) return <Empty icon="waves" title="Project not found" body={`There's no project called “${slug}”.`} />

  const setDoneRange = (range) => setSearchParams(writeDoneRange(searchParams, range), { replace: true })

  const setTab = (tab) => {
    const next = new URLSearchParams(searchParams)
    if (tab === 'board') next.delete('tab'); else next.set('tab', tab)
    setSearchParams(next, { replace: true })
  }

  return (
    <div className="flex h-full flex-col">
      <header className="px-7 pt-5">
        <nav aria-label="Breadcrumb" className="text-xs text-muted-foreground">
          {project?.name ?? '…'}
        </nav>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
            <Icon name="waves" size={16} aria-hidden />
          </span>
          <h1 className="text-xl font-bold">Stream</h1>
          {stream && (
            <span className="text-xs text-muted-foreground tabular-nums">
              {stream.open_issues} open · {stream.counts?.done ?? 0} done all time
            </span>
          )}
        </div>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Continuous work — each item is on production the moment it’s Done.
        </p>
        {/* One range for both tabs, so the picker sits on the tab row, not inside a tab. */}
        <div className="mt-3 flex items-end gap-3 border-b border-border">
          <Tabs
            className="flex-1 border-b-0"
            value={view}
            onValueChange={setTab}
            options={[
              { value: 'board', label: 'Board', icon: 'kanban' },
              { value: 'items', label: 'Items', icon: 'table-2' },
            ]}
          />
          <DoneRangePicker value={doneRange} onChange={setDoneRange} className="mb-1.5 shrink-0" />
        </div>
      </header>
      <div className="flex-1 min-h-0 overflow-auto scrollbar-thin">
        {error ? (
          <div role="alert" className="py-16 text-center text-sm text-muted-foreground">{error}</div>
        ) : !stream ? (
          <IssueBoardSkeleton />
        ) : (
          <ContainerWork
            container={stream}
            view={view}
            doneRange={doneRange}
          />
        )}
      </div>
    </div>
  )
}
