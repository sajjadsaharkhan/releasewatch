import React, { useEffect, useState } from 'react'
import { cn } from '../../lib/cn'
import { issuesApi, searchApi } from '../../lib/api'
import { issueKey, parseIssueRef } from '../../lib/issueSlug'
import { Input } from '../ui/Input'
import { StatusBadge, TypeIcon } from '../ui/Badge'
import { Icon } from '../ui/Icon'

// Search results and list rows name the id differently; the picker hands the
// panel one shape.
const fromSearch = (r) => ({
  id: r.issue_id, key: r.key, type: r.type, issue_number: r.issue_number,
  title: r.title, status: r.status,
})

/**
 * Search-picker for the Duplicate outcome's original — a bug or a task in
 * the same project (BR-20, 08a), never the item itself. Works like the Search
 * page's box: type `#13`, `13`, `BUG-13` or `TASK-13` to jump straight to that
 * item, or words to search by meaning (Persian, English or both).
 */
export function DuplicatePicker({ issue, value, onChange }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  // Set when the text looked like an item number but no such item can be picked.
  const [missing, setMissing] = useState(null)

  useEffect(() => {
    let cancelled = false
    const text = query.trim()
    setLoading(true)
    setMissing(null)

    async function run() {
      const ref = parseIssueRef(text)
      if (ref) {
        try {
          const found = (await issuesApi.getByNumber(ref.number)).data
          const usable = String(found.project_id) === String(issue.project_id)
            && found.id !== issue.id
            && (!ref.type || found.type === ref.type)
          if (usable) return [found]
        } catch { /* not an item number after all */ }
        if (!cancelled) setMissing(text)
      }
      if (!text) {
        const res = await issuesApi.list({ project_id: issue.project_id, sort: 'updated', size: 8 })
        return res.data.items
      }
      try {
        const res = await searchApi.search({ q: text, scope: 'project', project_id: issue.project_id, mode: 'palette' })
        return (res.data.results ?? []).map(fromSearch)
      } catch {
        // Search unavailable — fall back to the plain keyword filter.
        const res = await issuesApi.list({ project_id: issue.project_id, search: text, sort: 'updated', size: 8 })
        return res.data.items
      }
    }

    const timer = setTimeout(() => {
      run()
        .then(items => { if (!cancelled) setResults(items.filter(i => i.id !== issue.id)) })
        .catch(() => { if (!cancelled) setResults([]) })
        .finally(() => { if (!cancelled) setLoading(false) })
    }, 250)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [query, issue.id, issue.project_id])

  return (
    <div>
      <Input
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search bugs and tasks, or jump to #13 / BUG-13…"
        aria-label="Search for the original item"
        dir="auto"
        className="h-8 text-[12.5px]"
      />
      {missing && (
        <p className="mt-1.5 text-[11.5px] text-amber-700 dark:text-amber-300">
          No bug or task {missing} in this project — showing a text search instead.
        </p>
      )}
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
                <TypeIcon type={r.type} aria-hidden />
                <span className="font-mono text-[11px] text-muted-foreground shrink-0">{issueKey(r)}</span>
                <span dir="auto" className="truncate text-foreground">{r.title}</span>
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
