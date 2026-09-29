import React, { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useApp } from '../hooks/useApp'
import { backlogApi, teamApi } from '../lib/api'
import { OPEN_STATUSES, TECH_DEBT } from '../lib/constants'
import { issueKey, issueSlug } from '../lib/issueSlug'
import { fullTime, relTime } from '../lib/relTime'
import {
  Avatar, Empty, Icon, PriorityBadge, StatusBadge, Tooltip, TypeIcon, UserHoverCard, useToast,
} from '../components/ui'
import { FilterDropdown, MultiSelectFilterDropdown, ReportedCount } from '../components/common'

/**
 * Technical debt (slice 08, FR-27/28): every task flagged as debt, across
 * projects, highest priority first. Filters — projects (multi-select), status,
 * assignee — live in the URL so a filtered view can be shared; the backlog's
 * "Technical debt in this project" link opens it pre-filtered.
 */

const STATUS_OPTIONS = [
  { value: 'open', label: 'Open' },
  { value: 'done', label: 'Done' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'all', label: 'All' },
]

const STATUS_PARAM = {
  open: OPEN_STATUSES.join(','),
  done: 'done',
  cancelled: 'cancelled',
  all: undefined,
}

function Skeleton() {
  const pulse = 'rounded bg-zinc-200 dark:bg-zinc-700 animate-pulse'
  return (
    <tbody aria-hidden="true">
      {Array.from({ length: 8 }, (_, i) => (
        <tr key={i} className="border-b border-border">
          <td className="px-4 py-2.5"><div className={`h-3 w-16 ${pulse}`} /></td>
          <td className="px-2 py-2.5"><div className={`h-3 ${['w-56', 'w-72', 'w-48'][i % 3]} ${pulse}`} /></td>
          <td className="px-2 py-2.5"><div className={`h-3 w-20 ${pulse}`} /></td>
          <td className="px-2 py-2.5"><div className={`h-5 w-16 rounded-full ${pulse}`} /></td>
          <td className="px-2 py-2.5"><div className={`h-5 w-20 rounded-full ${pulse}`} /></td>
          <td className="px-2 py-2.5"><div className={`h-6 w-6 rounded-full ${pulse}`} /></td>
          <td className="px-4 py-2.5"><div className={`ml-auto h-3 w-10 ${pulse}`} /></td>
        </tr>
      ))}
    </tbody>
  )
}

export default function TechDebtPage() {
  const navigate = useNavigate()
  const { projects } = useApp()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const [team, setTeam] = useState([])
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  const projectIds = (searchParams.get('project') || '').split(',').filter(Boolean).map(Number)
  const status = searchParams.get('status') || 'open'
  const assignee = searchParams.get('assignee') || 'all'
  const paramsKey = searchParams.toString()

  const update = (key, value, fallback) => {
    const next = new URLSearchParams(searchParams)
    if (value == null || value === fallback || value === '') next.delete(key)
    else next.set(key, value)
    setSearchParams(next, { replace: true })
  }

  useEffect(() => {
    teamApi.list().then((r) => setTeam(r.data || [])).catch(() => setTeam([]))
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    backlogApi.techDebt({
      project_id: projectIds.length ? projectIds.join(',') : undefined,
      status: STATUS_PARAM[status],
      assignee_id: assignee !== 'all' && assignee !== 'unassigned' ? assignee : undefined,
      unassigned: assignee === 'unassigned' || undefined,
    })
      .then((res) => {
        if (cancelled) return
        setItems(res.data.items)
        setTotal(res.data.total)
      })
      .catch((err) => {
        if (!cancelled) toast.error('Failed to load technical debt', err.response?.data?.detail)
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // paramsKey is the stable primitive for the filters (docs/design.md §10).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey])

  const projectOptions = useMemo(
    () => (projects || []).filter((p) => !p.archived_at).map((p) => ({ value: p.id, label: p.name })),
    [projects],
  )
  const assigneeOptions = [
    { value: 'all', label: 'Any' },
    { value: 'unassigned', label: 'Unassigned' },
    ...team.filter((u) => u.role !== 'support').map((u) => ({ value: String(u.id), label: u.name })),
  ]
  const filtered = projectIds.length > 0 || status !== 'open' || assignee !== 'all'

  return (
    <div className="space-y-4 p-6">
      <div>
        <h1 className="flex items-center gap-2 text-lg font-semibold text-foreground">
          <Icon name={TECH_DEBT.icon} size={18} className={TECH_DEBT.iconClass} aria-hidden="true" />
          Technical debt
        </h1>
        <p className="mt-1 text-[12.5px] text-muted-foreground">
          Tasks flagged as technical debt, highest priority first. Debt stays out of the backlog
          until someone picks it up; once it's assigned or in a release it shows on boards like any task.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <MultiSelectFilterDropdown
          icon="folder"
          label="Projects"
          selected={projectIds}
          options={projectOptions}
          onChange={(ids) => update('project', ids.join(','), '')}
        />
        <FilterDropdown
          icon="circle-dot"
          label="Status"
          value={STATUS_OPTIONS.find((o) => o.value === status)?.label ?? 'Open'}
          options={STATUS_OPTIONS}
          onChange={(v) => update('status', v, 'open')}
        />
        <FilterDropdown
          icon="user"
          label="Assignee"
          value={assigneeOptions.find((o) => o.value === assignee)?.label ?? 'Any'}
          options={assigneeOptions}
          onChange={(v) => update('assignee', v, 'all')}
        />
        {filtered && (
          <button
            type="button"
            onClick={() => setSearchParams({}, { replace: true })}
            className="h-8 rounded-md px-2 text-[12px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Reset
          </button>
        )}
        {!loading && (
          <span className="ml-auto text-[12px] tabular-nums text-muted-foreground" aria-live="polite">
            {total} {total === 1 ? 'task' : 'tasks'}
          </span>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
        {!loading && items.length === 0 ? (
          filtered ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No technical debt matches your filters.
            </div>
          ) : (
            <Empty
              icon={TECH_DEBT.icon}
              title="No technical debt recorded"
              body="Flag a task as technical debt when you create it, or from its sidebar. Put components, risk, and approach in the description."
            />
          )
        ) : (
          <table className="w-full text-[13px]">
            <thead className="sticky top-0 border-b border-border bg-card/95 text-[10.5px] uppercase tracking-wide text-muted-foreground backdrop-blur">
              <tr>
                <th className="w-[110px] px-4 py-2.5 text-left font-medium">ID</th>
                <th className="px-2 py-2.5 text-left font-medium">Title</th>
                <th className="w-[140px] px-2 py-2.5 text-left font-medium">Project</th>
                <th className="w-[110px] px-2 py-2.5 text-left font-medium">Placement</th>
                <th className="w-[130px] px-2 py-2.5 text-left font-medium">Status</th>
                <th className="w-[64px] px-2 py-2.5 text-left font-medium">Assignee</th>
                <th className="w-[96px] whitespace-nowrap px-4 py-2.5 text-right font-medium">Age</th>
              </tr>
            </thead>
            {loading ? <Skeleton /> : (
              <tbody>
                {items.map((i) => (
                  <tr
                    key={i.id}
                    onClick={() => navigate(`/issue/${issueSlug(i)}`)}
                    className="cursor-pointer border-b border-border last:border-b-0 hover:bg-muted/50"
                  >
                    <td className="px-4 py-2 font-mono text-[11.5px] text-muted-foreground">
                      <span className="inline-flex items-center gap-1"><TypeIcon type={i.type} />{issueKey(i)}</span>
                    </td>
                    <td className="px-2 py-2">
                      <div className="flex min-w-0 items-center gap-1.5">
                        <PriorityBadge priority={i.priority} />
                        <Link
                          to={`/issue/${issueSlug(i)}`}
                          onClick={(e) => e.stopPropagation()}
                          className="max-w-[440px] truncate rounded-sm font-medium text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {i.title}
                        </Link>
                        <ReportedCount count={i.recurrence_count} />
                      </div>
                    </td>
                    <td className="max-w-[140px] truncate px-2 py-2 text-[12px] text-muted-foreground">
                      {i.project_name ?? '—'}
                    </td>
                    <td className="px-2 py-2 text-[12px]">
                      {i.release_version
                        ? <span className="font-mono text-muted-foreground">{i.release_version}</span>
                        : <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">Backlog</span>}
                    </td>
                    <td className="px-2 py-2"><StatusBadge status={i.status} /></td>
                    <td className="px-2 py-2" onClick={(e) => e.stopPropagation()}>
                      {i.assignee_user ? (
                        <UserHoverCard user={i.assignee_user} size={24}>
                          <Avatar user={i.assignee_user} size={24} />
                        </UserHoverCard>
                      ) : <span className="text-[11px] italic text-muted-foreground">unassigned</span>}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums text-muted-foreground">
                      <Tooltip content={`Created ${fullTime(i.created_at)}`}><span>{relTime(i.created_at)}</span></Tooltip>
                    </td>
                  </tr>
                ))}
              </tbody>
            )}
          </table>
        )}
      </div>
    </div>
  )
}
