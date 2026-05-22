import React, { useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, Plus, ChevronDown } from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { Segmented } from '../components/ui/Segmented'
import { FilterDropdown } from '../components/common/FilterDropdown'
import { MultiSelectFilterDropdown } from '../components/common/MultiSelectFilterDropdown'
import { NativeSelect } from '../components/ui/NativeSelect'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { Icon } from '../components/ui/Icon'
import { IssueTable } from '../components/common/IssueTable'
import { IssueBoard } from '../components/common/IssueBoard'
import { NewIssueModal } from '../components/issues/NewIssueModal'
import { MOCK_ISSUES, MOCK_TEAM, MOCK_RELEASES, MOCK_LABELS, SEVERITY, STATUS, userById } from '../data/mockData'
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
const ASSIGNEE_OPTIONS = [
  { value: 'all', label: 'Any' },
  { value: 'unassigned', label: 'Unassigned' },
  ...MOCK_TEAM.map(u => ({ value: u.id, label: u.name }))
]
const RELEASE_OPTIONS = [
  { value: 'all', label: 'Any' },
  ...MOCK_RELEASES.map(r => ({ value: r.id, label: r.version }))
]
const LABEL_OPTIONS = MOCK_LABELS.map(l => ({ value: l.id, label: l.name }))

export default function IssuesPage({ filterAssigned = false }) {
  const { newIssueOpen, setNewIssueOpen, query } = useApp()
  const navigate = useNavigate()
  const [viewMode, setViewMode] = useState('table')
  const [sort, setSort] = useState('newest')
  const [filter, setFilter] = useState({ severity: 'all', status: 'all', assignee: 'all', release: 'all', labels: [] })
  const [issues, setIssues] = useState(MOCK_ISSUES)

  const handleStatusChange = useCallback((issue, newStatus) => {
    setIssues(prev => prev.map(i =>
      i.id === issue.id ? { ...i, status: newStatus } : i
    ))
  }, [])

  const filtered = useMemo(() => {
    return issues.filter(i => {
      if (filterAssigned && i.assignee !== 'u-1') return false
      if (filter.severity !== 'all' && i.severity !== filter.severity) return false
      if (filter.status !== 'all' && i.status !== filter.status) return false
      if (filter.release !== 'all' && i.releaseId !== filter.release) return false
      if (filter.labels.length > 0) {
        const issueLabels = i.labels ?? []
        if (!filter.labels.some(l => issueLabels.includes(l))) return false
      }
      if (filter.assignee !== 'all') {
        if (filter.assignee === 'unassigned') { if (i.assignee) return false }
        else if (i.assignee !== filter.assignee) return false
      }
      if (query) {
        const q = query.toLowerCase()
        if (!i.title.toLowerCase().includes(q) && !i.id.toLowerCase().includes(q)) return false
      }
      return true
    })
  }, [issues, filter, query, filterAssigned])

  const openIssue = (issue) => {
    navigate(`/issue/${issue.id}`)
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="px-7 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {filterAssigned ? 'My Assigned' : 'All Issues'}
          </h1>
          <p className="text-[12px] text-zinc-500 dark:text-zinc-400">{filtered.length} of {issues.length} issues</p>
        </div>
        <div className="flex items-center gap-2">
          <Segmented size="sm" value={viewMode} onValueChange={setViewMode} options={VIEW_OPTIONS} />
          <Button variant="outline" size="sm">
            <Download className="h-3.5 w-3.5" />
            Export
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
          onChange={(v) => setFilter(f => ({ ...f, severity: v }))}
        />
        <FilterDropdown
          icon="circle-dashed"
          label="Status"
          value={filter.status === 'all' ? 'Any' : STATUS[filter.status].label}
          options={STATUS_OPTIONS}
          onChange={(v) => setFilter(f => ({ ...f, status: v }))}
        />
        <FilterDropdown
          icon="user"
          label="Assignee"
          value={filter.assignee === 'all' ? 'Any' : filter.assignee === 'unassigned' ? 'Unassigned' : userById(filter.assignee)?.name}
          options={ASSIGNEE_OPTIONS}
          onChange={(v) => setFilter(f => ({ ...f, assignee: v }))}
        />
        <FilterDropdown
          icon="tag"
          label="Release"
          value={filter.release === 'all' ? 'Any' : RELEASE_OPTIONS.find(r => r.value === filter.release)?.label}
          options={RELEASE_OPTIONS}
          onChange={(v) => setFilter(f => ({ ...f, release: v }))}
        />
        <MultiSelectFilterDropdown
          icon="hash"
          label="Labels"
          selected={filter.labels}
          options={LABEL_OPTIONS}
          onChange={(v) => setFilter(f => ({ ...f, labels: v }))}
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
              <DropdownItem key={opt.value} onClick={() => { setSort(opt.value); close(); }}>
                {opt.label}
              </DropdownItem>
            ))}
          </Dropdown>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {viewMode === 'table' ? (
          <IssueTable issues={filtered} onOpen={openIssue} />
        ) : (
          <IssueBoard issues={filtered} onOpen={openIssue} onStatusChange={handleStatusChange} />
        )}
      </div>

      {/* New Issue Modal */}
      <NewIssueModal open={newIssueOpen} onClose={() => setNewIssueOpen(false)} />
    </div>
  )
}