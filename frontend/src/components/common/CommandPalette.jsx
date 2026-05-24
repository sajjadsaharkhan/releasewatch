import React, { useState, useEffect, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, FileText, Users, LayoutDashboard, Inbox, Tag, BarChart2, Settings } from 'lucide-react'
import { cn } from '../../lib/cn'
import { useApp } from '../../hooks/useApp'
import { MOCK_ISSUES, MOCK_TEAM, SEVERITY } from '../../data/mockData'

const SYNONYMS = {
  crash: ['error', 'fail', '500', 'exception', 'crash'],
  slow: ['timeout', 'lag', 'latency', 'performance', 'slow'],
  login: ['auth', 'session', 'signin', 'authentication', 'login'],
  payment: ['billing', 'invoice', 'stripe', 'charge', 'payment'],
}

function expandQuery(q) {
  const lower = q.toLowerCase()
  const extras = []
  Object.entries(SYNONYMS).forEach(([key, synonyms]) => {
    if (synonyms.some((s) => lower.includes(s))) {
      extras.push(...synonyms)
    }
  })
  return [lower, ...extras]
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
  const { commandPaletteOpen, setCommandPaletteOpen } = useApp()
  const [query, setQuery] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (commandPaletteOpen) {
      setQuery('')
      setSelectedIdx(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [commandPaletteOpen])

  const results = useMemo(() => {
    if (!query.trim()) {
      return { issues: [], pages: PAGES.slice(0, 5), team: [] }
    }
    const terms = expandQuery(query)

    const issues = MOCK_ISSUES.filter((issue) =>
      terms.some((t) =>
        issue.title.toLowerCase().includes(t) ||
        issue.id.toLowerCase().includes(t) ||
        (issue.description ?? '').toLowerCase().includes(t)
      )
    ).slice(0, 5)

    const pages = PAGES.filter((p) =>
      terms.some((t) => p.label.toLowerCase().includes(t))
    ).slice(0, 3)

    const team = MOCK_TEAM.filter((u) =>
      terms.some((t) =>
        u.name.toLowerCase().includes(t) ||
        u.username.toLowerCase().includes(t)
      )
    ).slice(0, 3)

    return { issues, pages, team }
  }, [query])

  const flatResults = useMemo(() => {
    const flat = []
    results.issues.forEach((i) => flat.push({ type: 'issue', data: i }))
    results.pages.forEach((p) => flat.push({ type: 'page', data: p }))
    results.team.forEach((u) => flat.push({ type: 'user', data: u }))
    return flat
  }, [results])

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

  function Section({ title, items, renderItem }) {
    if (items.length === 0) return null
    return (
      <div>
        <p className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {title}
        </p>
        {items.map((item) => {
          const idx = globalIdx++
          return (
            <div
              key={item.id ?? item.data?.id ?? idx}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 cursor-pointer rounded-lg mx-1 transition-colors',
                selectedIdx === idx ? 'bg-accent' : 'hover:bg-accent'
              )}
              onMouseEnter={() => setSelectedIdx(idx)}
              onClick={() => select(flatResults[idx])}
            >
              {renderItem(item)}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[15vh] px-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setCommandPaletteOpen(false)}
      />
      {/* Panel */}
      <div className="relative z-10 w-full max-w-xl rounded-xl border border-border bg-card shadow-2xl overflow-hidden">
        {/* Input */}
        <div className="flex items-center gap-3 border-b border-border px-4 py-3">
          <Search className="h-4 w-4 text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIdx(0) }}
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
          {/* Reset global idx at render */}
          {(() => { globalIdx = 0 })()}

          {flatResults.length === 0 && query.trim() && (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">
              No results for "{query}"
            </p>
          )}

          {/* Issues */}
          {results.issues.length > 0 && (
            <div>
              <p className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Issues</p>
              {results.issues.map((issue) => {
                const idx = globalIdx++
                const sevToken = SEVERITY[issue.severity]
                return (
                  <div
                    key={issue.id}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 cursor-pointer rounded-lg mx-1 transition-colors',
                      selectedIdx === idx ? 'bg-accent' : 'hover:bg-accent'
                    )}
                    onMouseEnter={() => setSelectedIdx(idx)}
                    onClick={() => select({ type: 'issue', data: issue })}
                  >
                    {sevToken && <span className={cn('h-2 w-2 rounded-full shrink-0', sevToken.dot)} />}
                    <span className="font-mono text-xs text-muted-foreground w-24 shrink-0">issue-{issue.issue_number}</span>
                    <span className="flex-1 text-sm truncate">{issue.title}</span>
                  </div>
                )
              })}
            </div>
          )}

          {/* Pages */}
          {results.pages.length > 0 && (
            <div>
              <p className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Pages</p>
              {results.pages.map((page) => {
                const idx = globalIdx++
                const PageIcon = page.icon
                return (
                  <div
                    key={page.id}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 cursor-pointer rounded-lg mx-1 transition-colors',
                      selectedIdx === idx ? 'bg-accent' : 'hover:bg-accent'
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
          {results.team.length > 0 && (
            <div>
              <p className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Team</p>
              {results.team.map((user) => {
                const idx = globalIdx++
                return (
                  <div
                    key={user.id}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 cursor-pointer rounded-lg mx-1 transition-colors',
                      selectedIdx === idx ? 'bg-accent' : 'hover:bg-accent'
                    )}
                    onMouseEnter={() => setSelectedIdx(idx)}
                    onClick={() => select({ type: 'user', data: user })}
                  >
                    <span
                      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-white text-xs font-semibold"
                      style={{ backgroundColor: user.avatar_color }}
                    >
                      {user.name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
                    </span>
                    <span className="text-sm font-medium">{user.name}</span>
                    <span className="text-xs text-muted-foreground">@{user.username}</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer hint */}
        <div className="border-t border-border px-4 py-2 flex items-center gap-3 text-xs text-muted-foreground">
          <span><kbd className="font-mono">↑↓</kbd> navigate</span>
          <span><kbd className="font-mono">↵</kbd> select</span>
          <span><kbd className="font-mono">esc</kbd> close</span>
        </div>
      </div>
    </div>
  )
}
