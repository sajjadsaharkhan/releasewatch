import React, { useState, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { LayoutGrid, List, SlidersHorizontal } from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Segmented } from '../components/ui/Segmented'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { FilterDropdown } from '../components/common/FilterDropdown'
import { IssueTable } from '../components/common/IssueTable'
import { IssueBoard } from '../components/common/IssueBoard'
import { NewIssueModal } from '../components/issues/NewIssueModal'
import { IssueDetail } from '../components/issues/IssueDetail'
import { MOCK_ISSUES, MOCK_LABELS, MOCK_TEAM, MOCK_RELEASES, SEVERITY, STATUS, issueById } from '../data/mockData'
import { useApp } from '../hooks/useApp'
import { Plus } from 'lucide-react'

const VIEW_OPTIONS = [
  { value: 'table', label: '', icon: <List className="h-4 w-4" /> },
  { value: 'board', label: '', icon: <LayoutGrid className="h-4 w-4" /> },
]

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'severity', label: 'Severity' },
  { value: 'status', label: 'Status' },
]

const SEV_OPTIONS = Object.entries(SEVERITY).map(([k, v]) => ({ value: k, label: v.label }))
const STATUS_OPTIONS = Object.entries(STATUS).map(([k, v]) => ({ value: k, label: v.label }))

export default function IssuesPage({ filterAssigned = false }) {
  const { newIssueOpen, setNewIssueOpen } = useApp()
  const [view, setView] = useState('table')
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState('newest')
  const [sevFilter, setSevFilter] = useState([])
  const [statusFilter, setStatusFilter] = useState([])
  const [openIssue, setOpenIssue] = useState(null)

  const CURRENT_USER = 'u-1'

  const issues = useMemo(() => {
    let list = filterAssigned
      ? MOCK_ISSUES.filter((i) => i.assignee === CURRENT_USER)
      : MOCK_ISSUES

    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(
        (i) => i.title.toLowerCase().includes(q) || i.id.toLowerCase().includes(q)
      )
    }
    if (sevFilter.length > 0) list = list.filter((i) => sevFilter.includes(i.severity))
    if (statusFilter.length > 0) list = list.filter((i) => statusFilter.includes(i.status))

    list = [...list].sort((a, b) => {
      if (sort === 'oldest') return new Date(a.createdAt) - new Date(b.createdAt)
      if (sort === 'severity') {
        const ORDER = { blocker: 0, critical: 1, major: 2, minor: 3, enhancement: 4 }
        return (ORDER[a.severity] ?? 9) - (ORDER[b.severity] ?? 9)
      }
      if (sort === 'status') return a.status.localeCompare(b.status)
      return new Date(b.createdAt) - new Date(a.createdAt)
    })

    return list
  }, [search, sevFilter, statusFilter, sort, filterAssigned])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border px-5 py-3 flex-wrap">
        <h1 className="text-base font-semibold mr-2">
          {filterAssigned ? 'Assigned to Me' : 'Issues'}
        </h1>
        <span className="text-xs text-muted-foreground bg-muted rounded-full px-2 py-0.5">
          {issues.length}
        </span>

        <div className="flex items-center gap-2 ml-2 flex-wrap">
          <FilterDropdown
            label="Severity"
            options={SEV_OPTIONS}
            selected={sevFilter}
            onChange={setSevFilter}
          />
          <FilterDropdown
            label="Status"
            options={STATUS_OPTIONS}
            selected={statusFilter}
            onChange={setStatusFilter}
          />
        </div>

        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search issues…"
          className="w-48 h-8 text-xs"
        />

        <Dropdown
          trigger={
            <Button variant="outline" size="sm">
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Sort
            </Button>
          }
        >
          {SORT_OPTIONS.map((o) => (
            <DropdownItem key={o.value} onClick={() => setSort(o.value)}>
              {o.label}
            </DropdownItem>
          ))}
        </Dropdown>

        <div className="ml-auto flex items-center gap-2">
          <Segmented
            value={view}
            onValueChange={setView}
            options={VIEW_OPTIONS}
          />
          <Button size="sm" onClick={() => setNewIssueOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            New Issue
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className={cn('flex-1 overflow-auto', view === 'board' && 'flex')}>
        {view === 'table' ? (
          <IssueTable issues={issues} onOpen={setOpenIssue} />
        ) : (
          <IssueBoard issues={issues} onOpen={setOpenIssue} />
        )}
      </div>

      {/* Modals */}
      <NewIssueModal open={newIssueOpen} onClose={() => setNewIssueOpen(false)} />

      {openIssue && (
        <div className="fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpenIssue(null)} />
          <div className="relative z-10 ml-auto flex flex-col w-full max-w-5xl bg-card border-l border-border shadow-2xl">
            <div className="flex items-center justify-between border-b border-border px-5 py-3 shrink-0">
              <span className="font-mono text-sm text-muted-foreground">{openIssue.id}</span>
              <Button variant="ghost" size="sm" onClick={() => setOpenIssue(null)}>Close</Button>
            </div>
            <div className="flex-1 overflow-hidden">
              <IssueDetail issue={openIssue} onUpdate={setOpenIssue} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Wrapper for /issue/:id route
export function IssueDetailWrapper() {
  const { id } = useParams()
  const issue = issueById(id)

  if (!issue) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">Issue {id} not found.</p>
      </div>
    )
  }

  return <IssueDetail issue={issue} />
}
