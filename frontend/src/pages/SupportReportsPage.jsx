import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Empty } from '../components/ui/Empty'
import { Icon } from '../components/ui/Icon'
import { Input } from '../components/ui/Input'
import { StatusBadge, TypeIcon } from '../components/ui/Badge'
import { Avatar } from '../components/ui/Avatar'
import { UserHoverCard } from '../components/ui/UserHoverCard'
import { Tooltip } from '../components/ui/Tooltip'
import { FilterDropdown } from '../components/common/FilterDropdown'
import { MultiSelectFilterDropdown } from '../components/common/MultiSelectFilterDropdown'
import { ReportedCount } from '../components/common/ReportedCount'
import { projectsApi, supportApi, teamApi } from '../lib/api'
import { STATUS } from '../lib/constants'
import { issueSlug } from '../lib/issueSlug'
import { relTime, fullTime } from '../lib/relTime'
import { useApp } from '../hooks/useApp'
import { SupportReportModal } from '../components/support'
import { ReportRecurrenceButton, referenceDescription } from '../components/issues'
import { canSubmitSupportReport } from '../lib/roles'

// Every support-sourced item across all projects (slice 05, FR-11). Support works
// as a team — everyone sees the whole team's reports — so rows name the reporter
// and the Reporter filter narrows to "Me" or a teammate. Support also uses the
// page to file new reports (the New report button).

const STATUS_OPTIONS = Object.keys(STATUS).map((k) => ({ value: k, label: STATUS[k].label }))
const PAGE_SIZE = 50

export default function SupportReportsPage({ newReportOpen = false }) {
  const { user } = useApp()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') ?? ''
  const projectId = searchParams.get('project') ?? 'all'
  const statuses = useMemo(
    () => (searchParams.get('status') ? searchParams.get('status').split(',') : []),
    [searchParams]
  )
  const page = Number(searchParams.get('page') ?? 1)
  // 'me', a user id, or absent for everyone.
  const reporter = searchParams.get('reporter') ?? 'all'
  // `?ref=<key>` — "New report referencing this" from a Done bug (slice 07, FR-16).
  const refKey = searchParams.get('ref')

  const [query, setQuery] = useState(q)
  const [projects, setProjects] = useState([])
  const [supportTeam, setSupportTeam] = useState([])
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  const updateParams = useCallback((updates) => {
    setSearchParams((p) => {
      const next = new URLSearchParams(p)
      Object.entries(updates).forEach(([k, v]) => {
        if (v == null || v === '' || v === 'all' || (Array.isArray(v) && v.length === 0)) next.delete(k)
        else next.set(k, Array.isArray(v) ? v.join(',') : String(v))
      })
      if (!('page' in updates)) next.delete('page')
      return next
    }, { replace: true })
  }, [setSearchParams])

  useEffect(() => {
    projectsApi.list().then((res) => setProjects(res.data || [])).catch(() => {})
    teamApi.list()
      .then((res) => setSupportTeam((res.data || []).filter((u) => u.role === 'support')))
      .catch(() => {})
  }, [])

  const reporterId = reporter === 'me' ? user?.id : reporter === 'all' ? undefined : reporter

  // Debounce the search box into the URL.
  useEffect(() => {
    const t = setTimeout(() => { if (query !== q) updateParams({ q: query.trim() }) }, 250)
    return () => clearTimeout(t)
  }, [query, q, updateParams])

  useEffect(() => {
    let cancelled = false
    setError(false)
    supportApi.reports({
      q: q || undefined,
      project_id: projectId === 'all' ? undefined : projectId,
      status: statuses.length ? statuses : undefined,
      reporter_id: reporterId,
      page,
      size: PAGE_SIZE,
    })
      .then((res) => { if (!cancelled) setData(res.data) })
      .catch(() => { if (!cancelled) setError(true) })
    return () => { cancelled = true }
  }, [q, projectId, statuses, reporterId, page, reloadKey])

  const projectOptions = [
    { value: 'all', label: 'All projects' },
    ...projects.map((p) => ({ value: String(p.id), label: p.name })),
  ]
  const projectLabel = projectOptions.find((o) => o.value === projectId)?.label ?? 'All projects'
  const reporterOptions = [
    { value: 'all', label: 'Anyone' },
    { value: 'me', label: 'Me' },
    ...supportTeam
      .filter((u) => String(u.id) !== String(user?.id))
      .map((u) => ({ value: String(u.id), label: u.name })),
  ]
  const reporterLabel = reporterOptions.find((o) => o.value === reporter)?.label ?? 'Anyone'
  const filtered = Boolean(q || projectId !== 'all' || statuses.length || reporter !== 'all')
  const lastPage = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-7 py-4 border-b border-border flex items-center gap-4">
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-semibold text-foreground">Support reports</h1>
          <p className="text-[12px] text-zinc-500 dark:text-zinc-400">
            {data ? `${data.total} report${data.total === 1 ? '' : 's'}` : 'Loading…'}
          </p>
        </div>
        {canSubmitSupportReport(user?.role) && (
          <Button onClick={() => navigate('/support/new')}>
            <Icon name="plus" size={14} aria-hidden />
            New report
          </Button>
        )}
      </div>

      <div className="px-7 py-3 border-b border-border flex flex-wrap items-center gap-2 bg-muted/40">
        <div className="relative w-64 max-w-full">
          <Icon name="search" size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" aria-hidden />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search reports…"
            aria-label="Search reports"
            className="h-8 pl-8 text-[12px]"
          />
        </div>
        <FilterDropdown
          icon="folder"
          label="Project"
          value={projectLabel}
          options={projectOptions}
          onChange={(v) => updateParams({ project: v })}
        />
        <FilterDropdown
          icon="user"
          label="Reporter"
          value={reporterLabel}
          options={reporterOptions}
          onChange={(v) => updateParams({ reporter: v })}
        />
        <MultiSelectFilterDropdown
          icon="circle-dashed"
          label="Status"
          selected={statuses}
          options={STATUS_OPTIONS}
          onChange={(v) => updateParams({ status: v })}
        />
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {error ? (
          <Empty icon="triangle-alert" title="Failed to load support reports" className="py-16" />
        ) : data === null ? (
          <div className="flex justify-center py-16">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-primary" />
          </div>
        ) : data.items.length === 0 ? (
          <Empty
            icon="headset"
            title={filtered ? 'No reports match your filters.' : 'No support reports yet'}
            body={filtered ? undefined : 'Reports submitted by Support show up here.'}
            className="py-16"
          />
        ) : (
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-card border-b border-border text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th scope="col" className="text-left font-medium px-7 py-2">Report</th>
                <th scope="col" className="text-left font-medium px-3 py-2 hidden md:table-cell">Project</th>
                <th scope="col" className="text-left font-medium px-3 py-2">Reporter</th>
                <th scope="col" className="text-left font-medium px-3 py-2">Status</th>
                <th scope="col" className="text-left font-medium px-3 py-2">Assignee</th>
                <th scope="col" className="text-right font-medium px-3 py-2">Updated</th>
                <th scope="col" className="px-5 py-2 w-10"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={r.id} className="border-b border-border hover:bg-muted/50">
                  <td className="px-7 py-2.5 min-w-0">
                    <Link
                      to={`/issue/${issueSlug({ type: 'bug', issue_number: r.issue_number })}`}
                      className="flex items-center gap-2 min-w-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                    >
                      <TypeIcon type="bug" />
                      <span className="font-mono text-[12px] text-muted-foreground shrink-0">{r.key}</span>
                      <span className="truncate text-foreground">{r.title}</span>
                      <ReportedCount count={r.recurrence_count} />
                    </Link>
                  </td>
                  <td className="px-3 py-2.5 hidden md:table-cell">
                    <span className="inline-flex items-center gap-1.5 text-[12px] text-muted-foreground">
                      <span className="h-2 w-2 rounded-full" style={{ background: r.project_color ?? '#6366f1' }} aria-hidden />
                      {r.project_name}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    {r.reporter_user ? (
                      <span className="inline-flex items-center gap-1.5 text-[12px] text-foreground whitespace-nowrap">
                        <UserHoverCard user={r.reporter_user} size={20}>
                          <Avatar user={r.reporter_user} size={20} />
                        </UserHoverCard>
                        {String(r.reporter_user.id) === String(user?.id) ? 'You' : r.reporter_user.name}
                      </span>
                    ) : <span className="text-[11px] text-muted-foreground">—</span>}
                  </td>
                  <td className="px-3 py-2.5"><StatusBadge status={r.status} /></td>
                  <td className="px-3 py-2.5">
                    {r.assignee_user ? (
                      <UserHoverCard user={r.assignee_user} size={25}>
                        <Avatar user={r.assignee_user} size={25} />
                      </UserHoverCard>
                    ) : <span className="text-[11px] text-muted-foreground italic">unassigned</span>}
                  </td>
                  <td className="px-3 py-2.5 text-right text-[12px] text-muted-foreground whitespace-nowrap">
                    <Tooltip content={fullTime(r.updated_at)}>
                      <span>{relTime(r.updated_at)}</span>
                    </Tooltip>
                  </td>
                  <td className="px-5 py-1.5 text-right">
                    <ReportRecurrenceButton
                      compact
                      item={r}
                      onReported={(updated) => setData((d) => ({
                        ...d,
                        items: d.items.map((row) => (
                          row.id === updated.id ? { ...row, recurrence_count: updated.recurrence_count } : row
                        )),
                      }))}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {data && lastPage > 1 && (
        <div className="px-7 py-2 border-t border-border flex items-center justify-end gap-2 text-[12px] text-muted-foreground">
          <span>Page {page} of {lastPage}</span>
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => updateParams({ page: page - 1 })}>
            Previous
          </Button>
          <Button size="sm" variant="outline" disabled={page >= lastPage} onClick={() => updateParams({ page: page + 1 })}>
            Next
          </Button>
        </div>
      )}
      {canSubmitSupportReport(user?.role) && (
        <SupportReportModal
          open={newReportOpen}
          initialDescription={refKey ? referenceDescription(refKey) : ''}
          onClose={() => navigate('/support/reports')}
          onSubmitted={() => setReloadKey((k) => k + 1)}
        />
      )}
    </div>
  )
}
