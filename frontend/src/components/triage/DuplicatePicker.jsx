import React, { useEffect, useState } from 'react'
import { cn } from '../../lib/cn'
import { issuesApi } from '../../lib/api'
import { issueKey } from '../../lib/issueSlug'
import { Input } from '../ui/Input'
import { StatusBadge } from '../ui/Badge'
import { Icon } from '../ui/Icon'

/**
 * Search-picker for the Duplicate outcome's original — a bug or a task in
 * the same project (BR-20, 08a), never the item itself.
 */
export function DuplicatePicker({ issue, value, onChange }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const timer = setTimeout(() => {
      issuesApi.list({
        project_id: issue.project_id,
        search: query.trim() || undefined,
        sort: 'updated',
        size: 8,
      })
        .then(res => {
          if (!cancelled) setResults(res.data.items.filter(i => i.id !== issue.id))
        })
        .catch(() => { if (!cancelled) setResults([]) })
        .finally(() => { if (!cancelled) setLoading(false) })
    }, 200)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [query, issue.id, issue.project_id])

  return (
    <div>
      <Input
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search bugs and tasks in this project…"
        aria-label="Search for the original item"
        className="h-8 text-[12.5px]"
      />
      <ul className="mt-1.5 max-h-56 overflow-y-auto rounded-md border border-border bg-background" role="listbox" aria-label="Original item">
        {loading && results.length === 0 && (
          <li className="px-3 py-3 text-[12px] text-muted-foreground">Searching…</li>
        )}
        {!loading && results.length === 0 && (
          <li className="px-3 py-3 text-[12px] text-muted-foreground">Nothing matches.</li>
        )}
        {results.map(r => {
          const selected = value?.id === r.id
          return (
            <li key={r.id}>
              <button
                type="button"
                role="option"
                aria-selected={selected}
                onClick={() => onChange(r)}
                className={cn(
                  'flex w-full items-center gap-2 px-3 py-2 text-left text-[12.5px] border-b border-border last:border-b-0',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  selected ? 'bg-muted' : 'hover:bg-muted/60',
                )}
              >
                <span className="font-mono text-[11px] text-muted-foreground shrink-0">{issueKey(r)}</span>
                <span className="truncate text-foreground">{r.title}</span>
                <span className="ml-auto shrink-0"><StatusBadge status={r.status} /></span>
                {selected && <Icon name="check" size={12} className="shrink-0 text-foreground" />}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
