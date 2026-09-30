import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { Icon } from '../components/ui/Icon'
import { Empty } from '../components/ui/Empty'
import { Segmented } from '../components/ui/Segmented'
import {
  CreateReleaseModal, ReleaseLifecycleBadge, OverdueMarker, ReleaseProgress, GoNogoBadge,
} from '../components/releases'
import { projectsApi } from '../lib/api'
import { isOpenRelease } from '../lib/constants'
import { useApp } from '../hooks/useApp'
import { useProjectRoute } from '../hooks/useProjectRoute'
import { formatDay as formatDate } from '../lib/relTime'

// A project's releases (slice 09): lifecycle status, progress, target ship
// date and the Overdue marker, sortable by date and progress. The Stream is
// never in this list — it has its own page (sidebar).

const SORTS = {
  target: { label: 'Target date', icon: 'calendar' },
  progress: { label: 'Progress', icon: 'gauge' },
  created: { label: 'Newest', icon: 'clock' },
}

function compare(sort, dir) {
  const sign = dir === 'desc' ? -1 : 1
  return (a, b) => {
    let av, bv
    if (sort === 'target') {
      // Undated releases sort last either way.
      av = a.target_date ? new Date(a.target_date).getTime() : null
      bv = b.target_date ? new Date(b.target_date).getTime() : null
      if (av == null || bv == null) return av == null && bv == null ? 0 : av == null ? 1 : -1
    } else if (sort === 'progress') {
      av = a.progress ?? -1; bv = b.progress ?? -1
    } else {
      av = new Date(a.created_at).getTime(); bv = new Date(b.created_at).getTime()
    }
    return av === bv ? 0 : av < bv ? -sign : sign
  }
}

function RowSkeleton() {
  const pulse = 'bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse'
  return (
    <tr className="border-b border-border">
      <td className="px-5 py-3"><div className={`h-3 w-24 ${pulse}`} /></td>
      <td className="px-2 py-3"><div className={`h-4 w-20 rounded-full ${pulse}`} /></td>
      <td className="px-2 py-3"><div className={`h-1.5 w-40 ${pulse}`} /></td>
      <td className="px-2 py-3"><div className={`h-3 w-20 ${pulse}`} /></td>
      <td className="px-5 py-3"><div className={`h-4 w-12 rounded-full ${pulse}`} /></td>
    </tr>
  )
}

export default function ReleasesPage() {
  const { slug, project, notFound, redirectTo } = useProjectRoute('releases')
  const { refetchReleases } = useApp()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const sort = SORTS[searchParams.get('sort')] ? searchParams.get('sort') : 'target'
  const dir = searchParams.get('dir') === 'desc' ? 'desc' : 'asc'
  const show = ['open', 'closed'].includes(searchParams.get('show')) ? searchParams.get('show') : 'all'
  const [releases, setReleases] = useState(null)
  const [error, setError] = useState(null)
  const [createOpen, setCreateOpen] = useState(false)

  const load = useCallback(async () => {
    if (!project) return
    setError(null)
    try {
      const res = await projectsApi.releases(project.id)
      setReleases(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load the releases.')
    }
  }, [project?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { setReleases(null); load() }, [load])

  const rows = useMemo(() => {
    if (!releases) return []
    const filtered = releases.filter((r) =>
      show === 'all' ? true : show === 'open' ? isOpenRelease(r) : !isOpenRelease(r))
    return [...filtered].sort(compare(sort, dir))
  }, [releases, sort, dir, show])

  const setParam = (key, value, fallback) => {
    const next = new URLSearchParams(searchParams)
    if (value === fallback) next.delete(key); else next.set(key, value)
    setSearchParams(next, { replace: true })
  }

  if (!slug) return redirectTo ? <Navigate to={redirectTo} replace /> : <Empty icon="package" title="No projects yet" />
  if (notFound) return <Empty icon="package" title="Project not found" body={`There's no project called “${slug}”.`} />

  const openCount = releases?.filter(isOpenRelease).length ?? 0
  const overdueCount = releases?.filter((r) => r.is_overdue).length ?? 0

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <p className="text-xs text-muted-foreground">{project?.name ?? '…'}</p>
          <h1 className="text-xl font-bold">Releases</h1>
        </div>
        {releases && (
          <p className="text-sm text-muted-foreground self-end pb-0.5">
            {openCount} open
            {overdueCount > 0 && <span className="text-red-600 dark:text-red-400"> · {overdueCount} overdue</span>}
          </p>
        )}
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Icon name="plus" size={14} /> New release
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Segmented
          value={show}
          onValueChange={(v) => setParam('show', v, 'all')}
          options={[
            { value: 'all', label: 'All' },
            { value: 'open', label: 'Open' },
            { value: 'closed', label: 'Released & cancelled' },
          ]}
        />
        <div className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
          <span>Sort</span>
          <Segmented
            value={sort}
            onValueChange={(v) => setParam('sort', v, 'target')}
            options={Object.entries(SORTS).map(([value, s]) => ({ value, label: s.label }))}
          />
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={dir === 'asc' ? 'Ascending — switch to descending' : 'Descending — switch to ascending'}
            onClick={() => setParam('dir', dir === 'asc' ? 'desc' : 'asc', 'asc')}
          >
            <Icon name={dir === 'asc' ? 'arrow-up-narrow-wide' : 'arrow-down-wide-narrow'} size={14} />
          </Button>
        </div>
      </div>

      <CreateReleaseModal
        open={createOpen}
        projectId={project?.id}
        onClose={() => setCreateOpen(false)}
        onCreated={(r) => { refetchReleases?.(); navigate(`/releases/${r.id}`) }}
      />

      {error ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400">
          {error}
          <Button variant="outline" size="sm" className="ml-3" onClick={load}>Retry</Button>
        </div>
      ) : releases && rows.length === 0 ? (
        <div className="rounded-xl border border-border bg-card">
          <Empty
            icon="package"
            title={releases.length === 0 ? 'No releases yet' : 'Nothing matches'}
            body={releases.length === 0
              ? 'Group work that ships together into a release. Continuous work goes in the Stream.'
              : 'Try another filter.'}
          >
            {releases.length === 0 && (
              <Button size="sm" onClick={() => setCreateOpen(true)}><Icon name="plus" size={14} /> New release</Button>
            )}
          </Empty>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead className="text-[10.5px] uppercase tracking-wide text-muted-foreground border-b border-border">
              <tr>
                <th className="text-left font-medium px-5 py-2.5">Release</th>
                <th className="text-left font-medium px-2 py-2.5 w-[190px]">Status</th>
                <th className="text-left font-medium px-2 py-2.5 w-[220px]">Progress</th>
                <th className="text-left font-medium px-2 py-2.5 w-[130px]">Target ship</th>
                <th className="text-left font-medium px-5 py-2.5 w-[100px]">Go / no-go</th>
              </tr>
            </thead>
            <tbody>
              {!releases
                ? [0, 1, 2].map((i) => <RowSkeleton key={i} />)
                : rows.map((r) => (
                  <tr
                    key={r.id}
                    className={cn(
                      'border-b border-border last:border-0 hover:bg-accent/60 transition-colors cursor-pointer',
                      !isOpenRelease(r) && 'text-muted-foreground',
                    )}
                    onClick={() => navigate(`/releases/${r.id}`)}
                  >
                    <td className="px-5 py-3">
                      <Link
                        to={`/releases/${r.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="font-mono font-semibold text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                      >
                        {r.version}
                      </Link>
                      {r.description && <p className="mt-0.5 max-w-md truncate text-xs text-muted-foreground">{r.description}</p>}
                    </td>
                    <td className="px-2 py-3">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <ReleaseLifecycleBadge status={r.status} />
                        <OverdueMarker release={r} />
                      </div>
                    </td>
                    <td className="px-2 py-3"><ReleaseProgress release={r} /></td>
                    <td className="px-2 py-3 tabular-nums">
                      {r.status === 'released'
                        ? <span title="Shipped">{formatDate(r.released_at)}</span>
                        : formatDate(r.target_date) ?? <span className="text-muted-foreground">—</span>}
                    </td>
                    <td className="px-5 py-3"><GoNogoBadge status={r.go_nogo_status} /></td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
