import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { reviewQueueApi } from '../../lib/api'
import { cn } from '../../lib/cn'
import { issuePath } from '../../lib/issueSlug'
import { isPlainClick } from '../../lib/linkClick'
import { Avatar } from '../ui/Avatar'
import { Button } from '../ui/Button'
import { Checkbox } from '../ui/Checkbox'
import { Empty } from '../ui/Empty'
import { Icon } from '../ui/Icon'
import { Popover, PopoverContent, PopoverTrigger } from '../ui/Popover'
import { Segmented } from '../ui/Segmented'
import { StatusBadge } from '../ui/Badge'
import { Tooltip } from '../ui/Tooltip'
import { CyclesPill, PlacementChip, TypeMark } from './QueueMarks'
import { PriorityPicker } from './QueueItemRow'

// The To review tab of My Work (slice 22, PRD v3.1 FR-73): everything in To
// review or In review, in every project, whoever it is assigned to — grouped by
// project, then by status. Read-only: a row opens the item, where the status
// moves, Verify and Reject live (no row actions, so no bulk path — BR-60).

const DAY = 86400000
/** Past this the wait turns amber, as the overdue marker does. */
const SLOW_AFTER_MS = 2 * DAY

const TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'bug', label: 'Bugs' },
  { value: 'task', label: 'Tasks' },
]
const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'to_review', label: 'To review' },
  { value: 'in_review', label: 'In review' },
]
const STATUS_GROUP_LABEL = { to_review: 'To review', in_review: 'In review' }

/** "<1h", "5h", "2d" — how long the item has sat in its current review status. */
export function waitLabel(iso) {
  const ms = Date.now() - new Date(iso).getTime()
  if (ms < 3600000) return '<1h'
  if (ms < DAY) return `${Math.floor(ms / 3600000)}h`
  return `${Math.floor(ms / DAY)}d`
}

/**
 * The review queue and its counts. Refetches on mount (coming back from the
 * item page) and when the window regains focus — there is no push for items a
 * person isn't involved in.
 */
export function useReviewQueue(enabled, filters) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const key = JSON.stringify(filters)

  const load = useCallback(async () => {
    if (!enabled) return
    try {
      const res = await reviewQueueApi.get(JSON.parse(key))
      setData(res.data)
      setError(null)
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load the review queue.')
    }
  }, [enabled, key])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (!enabled) return undefined
    const refresh = () => { if (document.visibilityState === 'visible') load() }
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [enabled, load])

  return { data, error, reload: load }
}

function Waiting({ since }) {
  const slow = Date.now() - new Date(since).getTime() > SLOW_AFTER_MS
  return (
    <Tooltip content={`In this status since ${new Date(since).toLocaleString()}`}>
      <span
        data-testid="waiting"
        data-slow={slow ? 'true' : undefined}
        className={cn(
          'inline-flex shrink-0 items-center gap-1 text-[11.5px] tabular-nums',
          slow ? 'font-medium text-amber-700 dark:text-amber-400' : 'text-zinc-500 dark:text-zinc-400',
        )}
      >
        <Icon name="hourglass" size={11} aria-hidden="true" />
        waiting {waitLabel(since)}
      </span>
    </Tooltip>
  )
}

function ReviewRow({ item, onOpen }) {
  return (
    <li data-testid="review-row" data-item-id={item.id}>
      <div className="group flex items-center gap-3 rounded-xl border border-border bg-card px-3 py-3 transition-[border-color] hover:border-zinc-300 dark:hover:border-zinc-700">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <TypeMark type={item.type} />
            <Link
              to={issuePath(item)}
              onClick={(e) => {
                if (!isPlainClick(e)) return
                e.preventDefault()
                onOpen(item)
              }}
              className="truncate rounded text-left text-[13.5px] font-medium text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {item.title}
            </Link>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11.5px] text-muted-foreground">
            <span className="font-mono">{item.key}</span>
            <PlacementChip container={item.container} />
            {item.cycle_count > 1 && <CyclesPill item={item} />}
            <Waiting since={item.waiting_since} />
          </div>
        </div>
        <StatusBadge status={item.status} className="hidden lg:inline-flex" />
        <PriorityPicker item={item} disabled />
        {item.assignee
          ? <Avatar user={item.assignee} size={24} />
          : (
            <span
              className="h-6 w-6 shrink-0 rounded-full border border-dashed border-zinc-300 dark:border-zinc-600"
              title="Unassigned"
              role="img"
              aria-label="Unassigned"
            />
          )}
      </div>
    </li>
  )
}

function ProjectFilter({ projects, value, onChange }) {
  const [open, setOpen] = useState(false)
  const label = value.length === 0 ? 'All projects'
    : value.length === 1 ? (projects.find((p) => p.id === value[0])?.name ?? '1 project')
      : `${value.length} projects`
  const toggle = (id) => onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id])
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" aria-haspopup="listbox" aria-expanded={open} data-testid="review-project-filter">
          <Icon name="folder" size={14} aria-hidden="true" />{label}
          <Icon name="chevron-down" size={12} className="opacity-50" aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent width={240} className="p-1">
        <ul className="max-h-72 overflow-auto scrollbar-thin" aria-label="Projects">
          {projects.map((p) => (
            <li key={p.id}>
              <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-[13px] hover:bg-muted">
                <Checkbox checked={value.includes(p.id)} onCheckedChange={() => toggle(p.id)} aria-label={p.name} />
                <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: p.color }} aria-hidden="true" />
                <span className="truncate">{p.name}</span>
              </label>
            </li>
          ))}
        </ul>
        {value.length > 0 && (
          <button type="button" onClick={() => onChange([])} className="w-full rounded-md px-2 py-1.5 text-left text-[12px] text-muted-foreground hover:bg-muted hover:text-foreground">
            Clear
          </button>
        )}
      </PopoverContent>
    </Popover>
  )
}

function ReviewSkeleton() {
  return (
    <div className="space-y-2 px-7 pt-4" aria-hidden="true" data-testid="review-skeleton">
      {[0, 1, 2].map((n) => (
        <div key={n} className="flex items-center gap-3 rounded-xl border border-border px-3 py-3.5">
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

/** Rows are already in display order; group them without reordering. */
function groupRows(items) {
  const projects = []
  for (const item of items) {
    let g = projects[projects.length - 1]
    if (!g || g.project.id !== item.project.id) {
      g = { project: item.project, statuses: [] }
      projects.push(g)
    }
    let s = g.statuses[g.statuses.length - 1]
    if (!s || s.status !== item.status) {
      s = { status: item.status, rows: [] }
      g.statuses.push(s)
    }
    s.rows.push(item)
  }
  return projects
}

export function ReviewQueue({ data, error, onReload, filters, onFilters, projects }) {
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(() => new Set())
  const groups = useMemo(() => groupRows(data?.items ?? []), [data])
  const filtered = Boolean(filters.type || filters.status || filters.project_ids.length)
  const toggle = (id) => setCollapsed((prev) => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id); else next.add(id)
    return next
  })

  return (
    <div className="px-7 pb-24 pt-4" data-testid="review-queue">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <ProjectFilter projects={projects} value={filters.project_ids} onChange={(v) => onFilters({ ...filters, project_ids: v })} />
        <Segmented value={filters.type} onValueChange={(v) => onFilters({ ...filters, type: v })} options={TYPE_OPTIONS} />
        <Segmented value={filters.status} onValueChange={(v) => onFilters({ ...filters, status: v })} options={STATUS_OPTIONS} />
      </div>

      {error ? (
        <div role="alert" className="py-16 text-center text-sm text-muted-foreground">
          {error}
          <Button variant="outline" size="sm" className="ml-3" onClick={onReload}>Retry</Button>
        </div>
      ) : !data ? <ReviewSkeleton /> : groups.length === 0 ? (
        <Empty
          icon="clipboard-check"
          title="Nothing waiting for review"
          body={filtered ? 'Nothing matches these filters.' : 'Items in To review and In review, from every project, show up here.'}
        />
      ) : (
        <div className="space-y-6">
          {groups.map(({ project, statuses }) => {
            const open = !collapsed.has(project.id)
            const count = statuses.reduce((n, s) => n + s.rows.length, 0)
            return (
              <section key={project.id} aria-label={project.name} data-testid="review-project">
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => toggle(project.id)}
                  className="mb-2 flex w-full items-center gap-2 rounded px-1 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Icon name={open ? 'chevron-down' : 'chevron-right'} size={12} aria-hidden="true" />
                  <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: project.color }} aria-hidden="true" />
                  {project.name}
                  <span className="font-normal normal-case tracking-normal">· {count}</span>
                  <span className="h-px flex-1 bg-border" />
                </button>
                {open && statuses.map(({ status, rows }) => (
                  <div key={status} className="mb-3" data-testid={`review-group-${status}`}>
                    <h3 className="mb-1.5 px-1 text-[12px] font-medium text-foreground/80">
                      {STATUS_GROUP_LABEL[status] ?? status}
                      <span className="font-normal text-muted-foreground"> · {rows.length}</span>
                    </h3>
                    <ol className="space-y-2">
                      {rows.map((item) => <ReviewRow key={item.id} item={item} onOpen={(i) => navigate(issuePath(i))} />)}
                    </ol>
                  </div>
                ))}
              </section>
            )
          })}
          {data.truncated && (
            <p className="text-center text-[12px] text-muted-foreground">Showing the first 500. Narrow it with a filter.</p>
          )}
        </div>
      )}
    </div>
  )
}
