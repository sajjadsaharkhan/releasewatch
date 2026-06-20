import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, FileText, Users, LayoutDashboard, Inbox, Tag, BarChart2, Settings, Loader2 } from 'lucide-react'
import { cn } from '../../lib/cn'
import { useApp } from '../../hooks/useApp'
import { searchApi, teamApi } from '../../lib/api'

const SEVERITY_DOT = {
  blocker: 'bg-red-500',
  critical: 'bg-red-400',
  major: 'bg-amber-400',
  minor: 'bg-slate-400',
  enhancement: 'bg-blue-400',
}

const PAGES = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard' },
  { id: 'inbox', label: 'Inbox', icon: Inbox, path: '/inbox' },
  { id: 'issues', label: 'All Issues', icon: FileText, path: '/issues' },
  { id: 'triage', label: 'Triage', icon: Tag, path: '/triage' },
  { id: 'releases', label: 'Releases', icon: Tag, path: '/releases' },
  { id: 'regressions', label: 'Regressions', icon: BarChart2, path: '/regressions' },
  { id: 'contributions', label: 'Contributions', icon: BarChart2, path: '/contributions' },
  { id: 'team', label: 'Team', icon: Users, path: '/team' },
  { id: 'settings', label: 'Settings', icon: Settings, path: '/settings' },
]

export function CommandPalette() {
  const { commandPaletteOpen, setCommandPaletteOpen, activeProjectId } = useApp()
  const [query, setQuery] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [issueResults, setIssueResults] = useState([])
  const [teamMembers, setTeamMembers] = useState([])
  const [searching, setSearching] = useState(false)
  const inputRef = useRef(null)
  const debounceRef = useRef(null)
  const navigate = useNavigate()

  // Load team once when palette opens
  useEffect(() => {
    if (commandPaletteOpen && teamMembers.length === 0) {
      teamApi.listAll().then((res) => setTeamMembers(res.data || [])).catch(() => {})
    }
  }, [commandPaletteOpen])

  useEffect(() => {
    if (commandPaletteOpen) {
      setQuery('')
      setSelectedIdx(0)
      setIssueResults([])
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [commandPaletteOpen])

  const runSearch = useCallback(
    async (q) => {
      if (!q.trim() || !activeProjectId) {
        setIssueResults([])
        return
      }
      setSearching(true)
      try {
        const res = await searchApi.query(q.trim(), activeProjectId, 5)
        setIssueResults(res.data.results || [])
      } catch {
        setIssueResults([])
      } finally {
        setSearching(false)
      }
    },
    [activeProjectId],
  )

  function handleQueryChange(e) {
    const val = e.target.value
    setQuery(val)
    setSelectedIdx(0)
    clearTimeout(debounceRef.current)
    if (val.trim().length >= 2) {
      debounceRef.current = setTimeout(() => runSearch(val), 300)
    } else {
      setIssueResults([])
    }
  }

  const lower = query.toLowerCase()
  const matchedPages = query.trim()
    ? PAGES.filter((p) => p.label.toLowerCase().includes(lower)).slice(0, 3)
    : PAGES.slice(0, 5)
  const matchedTeam = query.trim()
    ? teamMembers.filter(
        (u) => u.name?.toLowerCase().includes(lower) || u.username?.toLowerCase().includes(lower),
      ).slice(0, 3)
    : []

  // Flat list for keyboard nav
  const flatResults = [
    ...issueResults.map((i) => ({ type: 'issue', data: i })),
    ...matchedPages.map((p) => ({ type: 'page', data: p })),
    ...matchedTeam.map((u) => ({ type: 'user', data: u })),
  ]

  function select(item) {
    setCommandPaletteOpen(false)
    if (item.type === 'issue') navigate(`/issue/issue-${item.data.issue_number}`)
    else if (item.type === 'page') navigate(item.data.path)
    else if (item.type === 'user') navigate(`/u/${item.data.username}`)
  }

  function handleKey(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIdx((i) => Math.min(i + 1, flatResults.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && flatResults[selectedIdx]) {
      e.preventDefault()
      select(flatResults[selectedIdx])
    } else if (e.key === 'Escape') {
      setCommandPaletteOpen(false)
    }
  }

  if (!commandPaletteOpen) return null

  let globalIdx = 0

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[15vh] px-4">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setCommandPaletteOpen(false)}
      />
      <div className="relative z-10 w-full max-w-xl rounded-xl border border-border bg-card shadow-2xl overflow-hidden">
        {/* Input */}
        <div className="flex items-center gap-3 border-b border-border px-4 py-3">
          {searching
            ? <Loader2 className="h-4 w-4 text-muted-foreground shrink-0 animate-spin" />
            : <Search className="h-4 w-4 text-muted-foreground shrink-0" />
          }
          <input
            ref={inputRef}
            value={query}
            onChange={handleQueryChange}
            onKeyDown={handleKey}
            placeholder="Search issues, pages, team…"
            className="flex-1 bg-transparent text-sm placeholder:text-muted-foreground focus:outline-none"
          />
          <kbd className="hidden sm:inline-flex h-5 items-center rounded border border-border bg-muted px-1.5 text-xs font-mono text-muted-foreground">
            Esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[60vh] overflow-y-auto scrollbar-thin py-2 space-y-1">
          {flatResults.length === 0 && query.trim() && !searching && (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">
              No results for "{query}"
            </p>
          )}

          {/* Issues */}
          {issueResults.length > 0 && (
            <div>
              <p className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Issues</p>
              {issueResults.map((issue) => {
                const idx = globalIdx++
                return (
                  <div
                    key={issue.issue_id}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 cursor-pointer rounded-lg mx-1 transition-colors',
                      selectedIdx === idx ? 'bg-accent' : 'hover:bg-accent',
                    )}
                    onMouseEnter={() => setSelectedIdx(idx)}
                    onClick={() => select({ type: 'issue', data: issue })}
                  >
                    <span className={cn('h-2 w-2 rounded-full shrink-0', SEVERITY_DOT[issue.severity] ?? 'bg-slate-400')} />
                    <span className="font-mono text-xs text-muted-foreground w-24 shrink-0">
                      issue-{issue.issue_number}
                    </span>
                    <span className="flex-1 text-sm truncate">{issue.title}</span>
                  </div>
                )
              })}
            </div>
          )}

          {/* Pages */}
          {matchedPages.length > 0 && (
            <div>
              <p className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Pages</p>
              {matchedPages.map((page) => {
                const idx = globalIdx++
                const PageIcon = page.icon
                return (
                  <div
                    key={page.id}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 cursor-pointer rounded-lg mx-1 transition-colors',
                      selectedIdx === idx ? 'bg-accent' : 'hover:bg-accent',
                    )}
                    onMouseEnter={() => setSelectedIdx(idx)}
                    onClick={() => select({ type: 'page', data: page })}
                  >
                    <PageIcon className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="text-sm">{page.label}</span>
                  </div>
                )
              })}
            </div>
          )}

          {/* Team */}
          {matchedTeam.length > 0 && (
            <div>
              <p className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Team</p>
              {matchedTeam.map((user) => {
                const idx = globalIdx++
                return (
                  <div
                    key={user.id}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 cursor-pointer rounded-lg mx-1 transition-colors',
                      selectedIdx === idx ? 'bg-accent' : 'hover:bg-accent',
                    )}
                    onMouseEnter={() => setSelectedIdx(idx)}
                    onClick={() => select({ type: 'user', data: user })}
                  >
                    <span
                      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-white text-xs font-semibold"
                      style={{ backgroundColor: user.avatar_color || '#6366f1' }}
                    >
                      {user.name?.split(' ').map((n) => n[0]).join('').slice(0, 2)}
                    </span>
                    <span className="text-sm font-medium">{user.name}</span>
                    <span className="text-xs text-muted-foreground">@{user.username}</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-border px-4 py-2 flex items-center gap-3 text-xs text-muted-foreground">
          <span><kbd className="font-mono">↑↓</kbd> navigate</span>
          <span><kbd className="font-mono">↵</kbd> select</span>
          <span><kbd className="font-mono">esc</kbd> close</span>
        </div>
      </div>
    </div>
  )
}
