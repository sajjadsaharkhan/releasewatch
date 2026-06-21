import React, { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search, Loader2, AlertCircle, ArrowRight } from 'lucide-react'
import { cn } from '../lib/cn'
import { Badge } from '../components/ui/Badge'
import { useApp } from '../hooks/useApp'
import { searchApi } from '../lib/api'

const SEVERITY_TONE = {
  blocker: 'red',
  critical: 'red',
  major: 'amber',
  minor: 'default',
  enhancement: 'blue',
}

const STATUS_TONE = {
  new: 'default',
  triaged: 'blue',
  in_progress: 'blue',
  fixed: 'green',
  verified: 'green',
  closed: 'default',
  regression: 'red',
}

function MatchedVia({ tags }) {
  if (!tags?.length) return null
  return (
    <div className="flex gap-1 flex-wrap">
      {tags.map((t) => (
        <span
          key={t}
          className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium bg-muted text-muted-foreground border border-border"
        >
          {t}
        </span>
      ))}
    </div>
  )
}

function ResultCard({ result, onClick }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-xl border border-border bg-card p-4 hover:bg-accent/50 transition-colors group"
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className="text-xs text-muted-foreground font-mono">#{result.issue_number}</span>
            <Badge tone={SEVERITY_TONE[result.severity] ?? 'default'} size="sm">
              {result.severity}
            </Badge>
            <Badge tone={STATUS_TONE[result.status] ?? 'default'} size="sm">
              {result.status?.replace('_', ' ')}
            </Badge>
          </div>
          <p className="text-sm font-medium text-foreground leading-snug mb-1 group-hover:text-primary transition-colors">
            {result.title}
          </p>
          {result.snippet && (
            <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
              {result.snippet}
            </p>
          )}
          <div className="mt-2 flex items-center gap-3">
            <MatchedVia tags={result.matched_via} />
            {result.assignee && (
              <span className="text-xs text-muted-foreground">→ {result.assignee}</span>
            )}
          </div>
        </div>
        <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </button>
  )
}

export default function SearchPage() {
  const { activeProjectId } = useApp()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searched, setSearched] = useState(false)
  const inputRef = useRef(null)
  const debounceRef = useRef(null)

  const runSearch = useCallback(
    async (q) => {
      if (!q.trim() || !activeProjectId) return
      setLoading(true)
      setError(null)
      try {
        const res = await searchApi.query(q.trim(), activeProjectId)
        setResults(res.data.results || [])
        setSearched(true)
        setSearchParams({ q: q.trim() }, { replace: true })
      } catch (err) {
        setError(err.response?.data?.detail || 'Search failed. Please try again.')
        setResults([])
      } finally {
        setLoading(false)
      }
    },
    [activeProjectId, setSearchParams],
  )

  // Run search for URL-seeded query on mount
  useEffect(() => {
    const q = searchParams.get('q')
    if (q) runSearch(q)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  function handleInputChange(e) {
    const val = e.target.value
    setQuery(val)
    clearTimeout(debounceRef.current)
    if (val.trim().length >= 2) {
      debounceRef.current = setTimeout(() => runSearch(val), 600)
    } else {
      setResults([])
      setSearched(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      clearTimeout(debounceRef.current)
      runSearch(query)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search bar */}
      <div className="border-b border-border bg-card px-6 py-4">
        <div className="max-w-2xl mx-auto">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <input
              ref={inputRef}
              value={query}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Search issues by title, description, comments, environment…"
              className={cn(
                'w-full h-10 rounded-lg border border-border bg-background pl-9 pr-4',
                'text-sm placeholder:text-muted-foreground',
                'focus:outline-none focus:ring-2 focus:ring-ring',
              )}
            />
            {loading && (
              <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
            )}
          </div>
          {searched && !loading && (
            <p className="text-xs text-muted-foreground mt-2">
              {results.length === 0
                ? 'No results found'
                : `${results.length} result${results.length !== 1 ? 's' : ''}`}
            </p>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="max-w-2xl mx-auto space-y-2">
          {error && (
            <div className="flex items-center gap-2 rounded-lg p-3 text-sm bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          {!loading && searched && results.length === 0 && !error && (
            <div className="text-center py-16 text-muted-foreground">
              <Search className="h-8 w-8 mx-auto mb-3 opacity-30" />
              <p className="text-sm">No issues matched your query.</p>
              <p className="text-xs mt-1">Try different keywords or check the LLM configuration in Settings.</p>
            </div>
          )}

          {!searched && !loading && (
            <div className="text-center py-16 text-muted-foreground">
              <Search className="h-8 w-8 mx-auto mb-3 opacity-20" />
              <p className="text-sm">Type to search across all issues</p>
              <p className="text-xs mt-1">Searches title, description, labels, environment, steps, and comments</p>
            </div>
          )}

          {results.map((r) => (
            <ResultCard
              key={r.issue_id}
              result={r}
              onClick={() => navigate(`/issue/issue-${r.issue_number}`)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
