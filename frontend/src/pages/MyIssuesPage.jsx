import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import { Tabs } from '../components/ui/Tabs'
import { Empty } from '../components/ui/Empty'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { Icon } from '../components/ui/Icon'
import { FilterDropdown } from '../components/common/FilterDropdown'
import { IssueTable, IssueTableSkeleton } from '../components/common/IssueTable'
import { issuesApi } from '../lib/api'
import { useApp } from '../hooks/useApp'
import { STATUS, SEVERITY, OPEN_STATUSES } from '../lib/constants'

const OPEN_STATUS_SET = new Set(OPEN_STATUSES)

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest' },
  { value: 'oldest', label: 'Oldest' },
  { value: 'severity', label: 'Severity' },
  { value: 'updated', label: 'Last updated' },
]

const STATUS_OPTIONS = [
  { value: 'open', label: 'Open issues' },
  { value: 'all', label: 'All statuses' },
  ...Object.keys(STATUS).map(k => ({ value: k, label: STATUS[k].label })),
]

const SEV_OPTIONS = [
  { value: 'all', label: 'Any' },
  ...Object.keys(SEVERITY).map(k => ({ value: k, label: SEVERITY[k].label })),
]

const PARAM_DEFAULTS = { tab: 'assigned', status: 'open', severity: 'all', sort: 'newest' }

export default function MyIssuesPage() {
  const { user } = useApp()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const tab = searchParams.get('tab') || PARAM_DEFAULTS.tab
  const statusFilter = searchParams.get('status') || PARAM_DEFAULTS.status
  const severityFilter = searchParams.get('severity') || PARAM_DEFAULTS.severity
  const sort = searchParams.get('sort') || PARAM_DEFAULTS.sort

  const updateParams = useCallback((updates) => {
    setSearchParams(p => {
      const next = new URLSearchParams(p)
      Object.entries(updates).forEach(([k, v]) => {
        if (v === PARAM_DEFAULTS[k]) next.delete(k)
        else next.set(k, v)
      })
      return next
    }, { replace: true })
  }, [setSearchParams])

  const [assignedIssues, setAssignedIssues] = useState([])
  const [reportedIssues, setReportedIssues] = useState([])
  const [assignedLoading, setAssignedLoading] = useState(true)
  const [reportedLoading, setReportedLoading] = useState(true)

  const fetchAll = useCallback(async () => {
    if (!user?.id) return
    setAssignedLoading(true)
    setReportedLoading(true)

    const [assignedRes, reportedRes] = await Promise.allSettled([
      issuesApi.list({ assignee_id: user.id, size: 200, sort }),
      issuesApi.list({ reporter_id: user.id, size: 200, sort }),
    ])

    setAssignedIssues(
      assignedRes.status === 'fulfilled' ? (assignedRes.value.data.items || []) : []
    )
    setReportedIssues(
      reportedRes.status === 'fulfilled' ? (reportedRes.value.data.items || []) : []
    )
    setAssignedLoading(false)
    setReportedLoading(false)
  }, [user?.id, sort])

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  const applyFilters = useCallback((issues) => {
    let result = issues
    if (statusFilter === 'open') result = result.filter(i => OPEN_STATUS_SET.has(i.status))
    else if (statusFilter !== 'all') result = result.filter(i => i.status === statusFilter)
    if (severityFilter !== 'all') result = result.filter(i => i.severity === severityFilter)
    return result
  }, [statusFilter, severityFilter])

  const displayedAssigned = useMemo(() => applyFilters(assignedIssues), [applyFilters, assignedIssues])
  const displayedReported = useMemo(() => applyFilters(reportedIssues), [applyFilters, reportedIssues])
  const displayedIssues = tab === 'assigned' ? displayedAssigned : displayedReported
  const loading = tab === 'assigned' ? assignedLoading : reportedLoading

  const openIssue = (issue) => navigate(`/issue/issue-${issue.issue_number}`)

  const statusLabel =
    statusFilter === 'open' ? 'Open issues'
    : statusFilter === 'all' ? 'All statuses'
    : STATUS[statusFilter]?.label ?? statusFilter

  const severityLabel = severityFilter === 'all' ? 'Any' : SEVERITY[severityFilter]?.label ?? severityFilter

  const TAB_OPTIONS = [
    {
      value: 'assigned',
      label: 'Assigned to me',
      badge: assignedLoading ? null : displayedAssigned.length,
    },
    {
      value: 'reported',
      label: 'Reported by me',
      badge: reportedLoading ? null : displayedReported.length,
    },
  ]

  const emptyBody =
    tab === 'assigned'
      ? statusFilter === 'open'
        ? 'No open issues are currently assigned to you.'
        : 'No assigned issues match your filters.'
      : statusFilter === 'open'
        ? 'You have no open issues filed.'
        : 'No reported issues match your filters.'

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="px-7 py-4 border-b border-border">
        <h1 className="text-lg font-semibold text-foreground">My Issues</h1>
        <p className="text-[12px] text-zinc-500 dark:text-zinc-400">
          {loading ? 'Loading…' : `${displayedIssues.length} issue${displayedIssues.length === 1 ? '' : 's'}`}
        </p>
      </div>

      {/* Tabs */}
      <div className="px-7">
        <Tabs
          value={tab}
          onValueChange={(v) => updateParams({ tab: v })}
          options={TAB_OPTIONS}
        />
      </div>

      {/* Filter Bar */}
      <div className="px-7 py-3 border-b border-border flex flex-wrap items-center gap-2 bg-muted/40">
        <FilterDropdown
          icon="circle-dashed"
          label="Status"
          value={statusLabel}
          options={STATUS_OPTIONS}
          onChange={(v) => updateParams({ status: v })}
        />
        <FilterDropdown
          icon="alert-octagon"
          label="Severity"
          value={severityLabel}
          options={SEV_OPTIONS}
          onChange={(v) => updateParams({ severity: v })}
        />
        <div className="ml-auto flex items-center gap-2">
          <Icon name="arrow-up-down" size={12} className="text-zinc-400" />
          <Dropdown
            width={140}
            trigger={
              <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-border bg-background hover:bg-muted text-[12px]">
                <span className="font-medium text-foreground">
                  {SORT_OPTIONS.find(s => s.value === sort)?.label}
                </span>
                <ChevronDown className="h-3 w-3 text-muted-foreground" />
              </button>
            }
          >
            {({ close }) =>
              SORT_OPTIONS.map((opt) => (
                <DropdownItem
                  key={opt.value}
                  onClick={() => { updateParams({ sort: opt.value }); close() }}
                >
                  {opt.label}
                </DropdownItem>
              ))
            }
          </Dropdown>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <IssueTableSkeleton
            rows={8}
            hideAssignee={tab === 'assigned'}
            hideReporter={tab === 'reported'}
            showProject
          />
        ) : displayedIssues.length === 0 ? (
          <Empty
            icon="circle-user-round"
            title="No issues found"
            body={emptyBody}
          />
        ) : (
          <IssueTable
            issues={displayedIssues}
            onOpen={openIssue}
            hideAssignee={tab === 'assigned'}
            hideReporter={tab === 'reported'}
            showProject
          />
        )}
      </div>
    </div>
  )
}
