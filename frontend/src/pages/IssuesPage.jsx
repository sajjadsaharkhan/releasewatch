import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Download, Plus, ChevronDown } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Segmented } from '../components/ui/Segmented'
import { FilterDropdown } from '../components/common/FilterDropdown'
import { MultiSelectFilterDropdown } from '../components/common/MultiSelectFilterDropdown'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { Icon } from '../components/ui/Icon'
import { IssueTable } from '../components/common/IssueTable'
import { IssueBoard } from '../components/common/IssueBoard'
import { NewIssueModal } from '../components/issues/NewIssueModal'
import { SEVERITY, STATUS } from '../data/mockData'
import { issuesApi, teamApi, labelsApi } from '../lib/api'
import { useApp } from '../hooks/useApp'

const VIEW_OPTIONS = [
  { value: 'table', label: 'Table' },
  { value: 'board', label: 'Board' },
]

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest' },
  { value: 'oldest', label: 'Oldest' },
  { value: 'severity', label: 'Severity' },
  { value: 'updated', label: 'Last updated' },
]

const SEV_OPTIONS = [{ value: 'all', label: 'Any' }, ...Object.keys(SEVERITY).map(k => ({ value: k, label: SEVERITY[k].label }))]
const STATUS_OPTIONS = [{ value: 'all', label: 'Any' }, ...Object.keys(STATUS).map(k => ({ value: k, label: STATUS[k].label }))]

export default function IssuesPage({ filterAssigned = false }) {
  const { newIssueOpen, setNewIssueOpen, query, releases, activeProjectId, user } = useApp()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [viewMode, setViewMode] = useState('table')

  // Derive filter and sort from URL query params
  const sort = searchParams.get('sort') || 'newest'
  const filter = {
    severity: searchParams.get('severity') || 'all',
    status:   searchParams.get('status')   || 'all',
    assignee: searchParams.get('assignee') || 'all',
    release:  searchParams.get('release')  || 'all',
    labels:   searchParams.getAll('labels'),
  }

  // Write filter + sort changes back to URL
  const updateParams = useCallback((newFilter, newSort) => {
    const p = new URLSearchParams()
    if (newSort !== 'newest')          p.set('sort',     newSort)
    if (newFilter.severity !== 'all')  p.set('severity', newFilter.severity)
    if (newFilter.status   !== 'all')  p.set('status',   newFilter.status)
    if (newFilter.assignee !== 'all')  p.set('assignee', newFilter.assignee)
    if (newFilter.release  !== 'all')  p.set('release',  newFilter.release)
    newFilter.labels.forEach(l => p.append('labels', l))
    setSearchParams(p, { replace: true })
  }, [setSearchParams])

  const [issues, setIssues] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [team, setTeam] = useState([])
  const [labels, setLabels] = useState([])
  const [exporting, setExporting] = useState(false)

  // Load team and labels once
  useEffect(() => {
    teamApi.list().then(r => setTeam(r.data || [])).catch(() => setTeam([]))
    labelsApi.list().then(r => setLabels(r.data || [])).catch(() => setLabels([]))
  }, [])

  // useMemo with searchParams.toString() as a stable primitive dep — avoids
  // the infinite loop that occurs when a plain `filter` object is used directly
  // (new object reference every render → fetchIssues changes → effect re-fires).
  const paramsString = searchParams.toString()
  const apiParams = useMemo(() => {
    const _sort     = searchParams.get('sort')     || 'newest'
    const severity  = searchParams.get('severity') || 'all'
    const status    = searchParams.get('status')   || 'all'
    const assignee  = searchParams.get('assignee') || 'all'
    const release   = searchParams.get('release')  || 'all'
    const labels    = searchParams.getAll('labels')
    return {
      sort: _sort,
      size: 200,
      ...(activeProjectId && { project_id: activeProjectId }),
      ...(severity !== 'all' && { severity }),
      ...(status   !== 'all' && { status }),
      ...(release  !== 'all' && { release_id: release }),
      ...(labels.length > 0  && { labels }),
      ...(query && { search: query }),
      ...(filterAssigned
        ? { assignee_id: user?.id }
        : assignee === 'unassigned'
          ? { unassigned: true }
          : assignee !== 'all'
            ? { assignee_id: assignee }
            : {}),
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsString, activeProjectId, query, filterAssigned, user?.id])

  const fetchIssues = useCallback(async () => {
    setLoading(true)
    try {
      const res = await issuesApi.list(apiParams)
      setIssues(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch (err) {
      console.error('Failed to fetch issues:', err)
      setIssues([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [apiParams])

  useEffect(() => {
    fetchIssues()
  }, [fetchIssues])

  const handleStatusChange = useCallback(async (issue, newStatus) => {
    try {
      await issuesApi.update(issue.id, { status: newStatus })
      setIssues(prev => prev.map(i => i.id === issue.id ? { ...i, status: newStatus } : i))
    } catch (err) {
      console.error('Failed to update issue status:', err)
    }
  }, [])

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await issuesApi.export(apiParams)
      const url = URL.createObjectURL(new Blob([res.data], { type: 'text/csv' }))
      const a = document.createElement('a')
      a.href = url
      a.download = 'issues.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export failed:', err)
    } finally {
      setExporting(false)
    }
  }

  const openIssue = (issue) => {
    navigate(`/issue/issue-${issue.issue_number}`)
  }

  // Build filter options from real data
  const ASSIGNEE_OPTIONS = [
    { value: 'all', label: 'Any' },
    { value: 'unassigned', label: 'Unassigned' },
    ...team.map(u => ({ value: u.id, label: u.name })),
  ]

  const RELEASE_OPTIONS = [
    { value: 'all', label: 'Any' },
    ...releases.map(r => ({ value: r.id, label: r.version })),
  ]

  const LABEL_OPTIONS = labels.map(l => ({ value: l.name, label: l.name }))

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="px-7 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {filterAssigned ? 'My Assigned' : 'All Issues'}
          </h1>
          <p className="text-[12px] text-zinc-500 dark:text-zinc-400">
            {loading ? 'Loading…' : `${issues.length} of ${total} issues`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Segmented size="sm" value={viewMode} onValueChange={setViewMode} options={VIEW_OPTIONS} />
          <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting}>
            <Download className="h-3.5 w-3.5" />
            {exporting ? 'Exporting…' : 'Export'}
          </Button>
          <Button size="sm" onClick={() => setNewIssueOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            New Issue
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="px-7 py-3 border-b border-zinc-200 dark:border-zinc-800 flex flex-wrap items-center gap-2 bg-zinc-50/60 dark:bg-zinc-900/40">
        <FilterDropdown
          icon="alert-octagon"
          label="Severity"
          value={filter.severity === 'all' ? 'Any' : SEVERITY[filter.severity].label}
          options={SEV_OPTIONS}
          onChange={(v) => updateParams({ ...filter, severity: v }, sort)}
        />
        <FilterDropdown
          icon="circle-dashed"
          label="Status"
          value={filter.status === 'all' ? 'Any' : STATUS[filter.status].label}
          options={STATUS_OPTIONS}
          onChange={(v) => updateParams({ ...filter, status: v }, sort)}
        />
        <FilterDropdown
          icon="user"
          label="Assignee"
          value={
            filter.assignee === 'all' ? 'Any'
            : filter.assignee === 'unassigned' ? 'Unassigned'
            : team.find(u => u.id === filter.assignee)?.name ?? 'Any'
          }
          options={ASSIGNEE_OPTIONS}
          onChange={(v) => updateParams({ ...filter, assignee: v }, sort)}
        />
        <FilterDropdown
          icon="tag"
          label="Release"
          value={filter.release === 'all' ? 'Any' : RELEASE_OPTIONS.find(r => r.value === filter.release)?.label ?? 'Any'}
          options={RELEASE_OPTIONS}
          onChange={(v) => updateParams({ ...filter, release: v }, sort)}
        />
        <MultiSelectFilterDropdown
          icon="hash"
          label="Labels"
          selected={filter.labels}
          options={LABEL_OPTIONS}
          onChange={(v) => updateParams({ ...filter, labels: v }, sort)}
        />
        <div className="ml-auto flex items-center gap-2">
          <Icon name="arrow-up-down" size={12} className="text-zinc-400" />
          <Dropdown width={140}
            trigger={
              <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 hover:bg-zinc-50 dark:hover:bg-zinc-900 text-[12px]">
                <span className="font-medium text-zinc-800 dark:text-zinc-100">{SORT_OPTIONS.find(s => s.value === sort)?.label}</span>
                <ChevronDown className="h-3 w-3 text-zinc-400" />
              </button>
            }
          >
            {({ close }) => SORT_OPTIONS.map((opt) => (
              <DropdownItem key={opt.value} onClick={() => { updateParams(filter, opt.value); close(); }}>
                {opt.label}
              </DropdownItem>
            ))}
          </Dropdown>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="py-12 text-center text-sm text-zinc-400">Loading issues…</div>
        ) : viewMode === 'table' ? (
          <IssueTable issues={issues} onOpen={openIssue} />
        ) : (
          <IssueBoard issues={issues} onOpen={openIssue} onStatusChange={handleStatusChange} />
        )}
      </div>

      {/* New Issue Modal */}
      <NewIssueModal open={newIssueOpen} onClose={() => { setNewIssueOpen(false); fetchIssues() }} />
    </div>
  )
}
