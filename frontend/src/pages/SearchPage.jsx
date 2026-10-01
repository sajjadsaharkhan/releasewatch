import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { cn } from '../lib/cn'
import { StatusBadge, TypeIcon } from '../components/ui/Badge'
import { Empty } from '../components/ui/Empty'
import { Icon } from '../components/ui/Icon'
import { Segmented } from '../components/ui/Segmented'
import { useToast } from '../components/ui/Toast'
import { MultiSelectFilterDropdown } from '../components/common/MultiSelectFilterDropdown'
import { useApp } from '../hooks/useApp'
import { issuesApi, searchApi } from '../lib/api'
import { STATUS, TYPE } from '../lib/constants'
import { issueKey, issueSlug, parseIssueSlug } from '../lib/issueSlug'

const TYPE_OPTIONS = Object.entries(TYPE).map(([value, t]) => ({ value, label: t.label, icon: t.icon }))
const STATUS_OPTIONS = Object.entries(STATUS).map(([value, s]) => ({ value, label: s.label, icon: s.icon }))

/** `#13`, `BUG-13`, `bug-13` jump straight to the item instead of searching. */
function parseJump(q) {
  if (/^#\d+$/.test(q)) return parseInt(q.slice(1), 10)
  return parseIssueSlug(q.toLowerCase())
}

function ResultRow({ result, onOpen }) {
  const cancelled = result.is_cancelled
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'relative w-full text-left rounded-xl border border-border bg-card p-4 transition-colors group',
        'hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
      )}
    >
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        <span className="inline-flex items-center gap-1 font-mono text-[11.5px] text-muted-foreground">
          <TypeIcon type={result.type} />
          {result.key ?? issueKey(result)}
        </span>
        <StatusBadge status={result.status} />
        {result.project && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Icon name="folder" size={12} aria-hidden />
            {result.project.name}
          </span>
        )}
      </div>
      <p
        dir="auto"
        className={cn(
          'text-sm font-medium leading-snug group-hover:text-primary transition-colors',
          cancelled ? 'text-muted-foreground line-through decoration-zinc-400' : 'text-foreground',
        )}
      >
        {result.title}
      </p>
      {result.snippet && (
        <p dir="auto" className="mt-1 text-xs text-muted-foreground line-clamp-2 leading-relaxed">
          {result.snippet_source === 'comment' && (
            <span className="inline-flex items-center gap-1 mr-1.5 align-middle text-[11px] font-medium text-foreground/70">
              <Icon name="message-square" size={11} aria-hidden />
              Comment:
            </span>
          )}
          {result.snippet}
        </p>
      )}
    </button>
  )
}

export default function SearchPage() {
  const { activeProjectId, projects = [] } = useApp()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [params, setParams] = useSearchParams()

  const q = params.get('q') || ''
  const scope = params.get('scope') === 'all' ? 'all' : 'project'
  const types = (params.get('type') || '').split(',').filter(Boolean)
  const statuses = (params.get('status') || '').split(',').filter(Boolean)

  const [input, setInput] = useState(q)
  const [data, setData] = useState(null) // { results, less_relevant } once a search ran
  const [loading, setLoading] = useState(false)
  const [showLess, setShowLess] = useState(false)
  const inputRef = useRef(null)
  const debounceRef = useRef(null)
  const requestRef = useRef(0)

  const activeProject = projects.find((p) => p.id === activeProjectId)

  function update(changes) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      for (const [k, v] of Object.entries(changes)) {
        if (v) next.set(k, v)
        else next.delete(k)
      }
      return next
    }, { replace: true })
  }

  const run = useCallback(async () => {
    const query = q.trim()
    if (!query) {
      setData(null)
      return
    }
    const jump = parseJump(query)
    if (jump !== null) {
      try {
        const res = await issuesApi.getByNumber(jump)
        navigate(`/issue/${issueSlug(res.data)}`, { replace: true })
        return
      } catch {
        // Not an item number after all — search for the text.
      }
    }
    if (scope === 'project' && !activeProjectId) return
    const id = ++requestRef.current
    setLoading(true)
    try {
      const res = await searchApi.search({
        q: query,
        scope,
        project_id: scope === 'project' ? activeProjectId : undefined,
        type: types.length ? types : undefined,
        status: statuses.length ? statuses : undefined,
        mode: 'page',
      })
      if (id !== requestRef.current) return
      setData(res.data)
      setShowLess(false)
    } catch (err) {
      if (id !== requestRef.current) return
      setData({ results: [], less_relevant: [] })
      toast.error('Search failed', err.response?.data?.detail)
    } finally {
      if (id === requestRef.current) setLoading(false)
    }
  }, [q, scope, activeProjectId, params.get('type'), params.get('status')]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { run() }, [run])
  useEffect(() => { inputRef.current?.focus() }, [])
  useEffect(() => { setInput(q) }, [q])

  function handleChange(e) {
    const value = e.target.value
    setInput(value)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => update({ q: value.trim() }), 400)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      clearTimeout(debounceRef.current)
      update({ q: input.trim() })
    }
  }

  const results = data?.results ?? []
  const less = data?.less_relevant ?? []
  const open = (r) => navigate(`/issue/${issueSlug(r)}`)

  return (
    <div className="p-6 space-y-4 max-w-3xl mx-auto">
      <div>
        <h1 className="text-xl font-bold">Search</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Finds items by meaning, in Persian, English or both. Jump to an item with #13 or BUG-13.
        </p>
      </div>

      <div className="relative">
        <Icon
          name="search" size={16} aria-hidden
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
        />
        <input
          ref={inputRef}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          dir="auto"
          aria-label="Search"
          placeholder="Search items, or jump to #13 / BUG-13…"
          className={cn(
            'w-full h-10 rounded-lg border border-border bg-background pl-9 pr-9 text-sm',
            'placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring',
          )}
        />
        {loading && (
          <Icon name="loader-2" size={16} aria-hidden className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-muted-foreground" />
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          value={scope}
          onValueChange={(v) => update({ scope: v === 'all' ? 'all' : '' })}
          options={[
            { value: 'project', label: activeProject ? activeProject.name : 'This project' },
            { value: 'all', label: 'All projects' },
          ]}
        />
        <MultiSelectFilterDropdown
          icon="shapes" label="Type" selected={types} options={TYPE_OPTIONS}
          onChange={(v) => update({ type: v.join(',') })}
        />
        <MultiSelectFilterDropdown
          icon="circle-dot" label="Status" selected={statuses} options={STATUS_OPTIONS}
          onChange={(v) => update({ status: v.join(',') })}
        />
        {data && !loading && results.length > 0 && (
          <p className="ml-auto text-xs text-muted-foreground" aria-live="polite">
            {results.length} result{results.length === 1 ? '' : 's'}
          </p>
        )}
      </div>

      <div className="space-y-2">
        {!q && (
          <Empty
            icon="search"
            title="Search across your items"
            body="Titles, descriptions, steps, and the comments that say something about the problem."
          />
        )}
        {q && data && !loading && results.length === 0 && less.length === 0 && (
          <Empty icon="search-x" title="No matches" body="Nothing like this has been reported yet." />
        )}
        {q && data && !loading && results.length === 0 && less.length > 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">No close matches</p>
        )}
        {results.map((r) => <ResultRow key={r.issue_id} result={r} onOpen={() => open(r)} />)}

        {/* Results the relevance check judged weak (slice 13) — collapsed, never hidden. */}
        {less.length > 0 && (
          <div className="pt-2">
            <button
              type="button"
              onClick={() => setShowLess((v) => !v)}
              aria-expanded={showLess}
              className="inline-flex items-center gap-1.5 rounded-md px-1 py-1 text-xs font-medium text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Icon name={showLess ? 'chevron-down' : 'chevron-right'} size={14} aria-hidden />
              Less relevant results ({less.length})
            </button>
            {showLess && (
              <div className="mt-2 space-y-2">
                {less.map((r) => <ResultRow key={r.issue_id} result={r} onOpen={() => open(r)} />)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
