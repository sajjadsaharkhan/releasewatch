import React, { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, Plus } from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { Segmented } from '../components/ui/Segmented'
import { FilterDropdown } from '../components/common/FilterDropdown'
import { FilterChipStatic } from '../components/ui/FilterChipStatic'
import { NativeSelect } from '../components/ui/NativeSelect'
import { IssueTable } from '../components/common/IssueTable'
import { IssueBoard } from '../components/common/IssueBoard'
import { NewIssueModal } from '../components/issues/NewIssueModal'
import { MOCK_ISSUES, MOCK_TEAM, SEVERITY, STATUS, userById } from '../data/mockData'
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

export default function IssuesPage({ filterAssigned = false }) {
  const { newIssueOpen, setNewIssueOpen, query } = useApp()
  const navigate = useNavigate()
  const [viewMode, setViewMode] = useState('table')
  const [sort, setSort] = useState('newest')
  const [filter, setFilter] = useState({ severity: 'all', status: 'all', assignee: 'all' })

  const filtered = useMemo(() => {
    return MOCK_ISSUES.filter(i => {
      if (filterAssigned && i.assignee !== 'u-1') return false
      if (filter.severity !== 'all' && i.severity !== filter.severity) return false
      if (filter.status !== 'all' && i.status !== filter.status) return false
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
  }, [filter, query, filterAssigned])

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
          <p className="text-[12px] text-zinc-500 dark:text-zinc-400">{filtered.length} of {MOCK_ISSUES.length} issues</p>
        </div>
        <div className="flex items-center gap-2">
          <Segmented size="sm" value={viewMode} onChange={setViewMode} options={VIEW_OPTIONS} />
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
        <FilterChipStatic icon="tag" label="Release" value="v2.4.1" />
        <FilterChipStatic icon="hash" label="Labels" value="Any" />
        <button className="text-[12px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 px-2">+ Add filter</button>
        <div className="ml-auto flex items-center gap-2">
          <NativeSelect
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="text-[12px]"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </NativeSelect>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {viewMode === 'table' ? <IssueTable issues={filtered} onOpen={openIssue} /> : <IssueBoard issues={filtered} onOpen={openIssue} />}
      </div>

      {/* New Issue Modal */}
      <NewIssueModal open={newIssueOpen} onClose={() => setNewIssueOpen(false)} />
    </div>
  )
}