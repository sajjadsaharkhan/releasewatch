import React, { useEffect, useState } from 'react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { issuesApi } from '../../lib/api'
import { issueKey } from '../../lib/issueSlug'
import { useToast } from '../../hooks/useToast'

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

/**
 * On production (19, FR-67): the bar that appears when Verified Stream items
 * are selected, and the confirm dialog behind its button. It is not a generic
 * bulk-status control — only `POST /issues/bulk-production`. All or nothing:
 * a 409 `not_verified_in_stream` names the refused items and changes none.
 * `items` are the selected issues, in the order shown.
 */
export function ProductionBar({ items, onClear, onDone, onRefused }) {
  const { toast } = useToast()
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // Nothing selected (a refresh pruned it) — nothing to confirm.
  useEffect(() => { if (items.length === 0) { setConfirming(false); setError(null) } }, [items.length])

  if (items.length === 0 && !confirming) return null

  async function submit() {
    setBusy(true); setError(null)
    try {
      const res = await issuesApi.bulkProduction(items.map((i) => i.id))
      const n = res.data?.issues?.length ?? items.length
      toast({ title: `${plural(n, 'item')} on production`, body: 'Marked Done.' })
      setConfirming(false)
      onDone?.(res.data)
    } catch (err) {
      const body = err.response?.data
      if (body?.code === 'not_verified_in_stream' && Array.isArray(body.issue_ids)) {
        const refused = items.filter((i) => body.issue_ids.includes(i.id))
        const names = refused.map(issueKey).join(', ') || plural(body.issue_ids.length, 'item')
        setError(`Nothing was changed. ${names} ${refused.length === 1 ? 'is' : 'are'} not Verified in the Stream.`)
        onRefused?.(body.issue_ids)
      } else {
        setError(body?.detail || 'Could not mark these items as on production.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {items.length > 0 && (
        <div
          role="region"
          aria-label="Selection"
          data-testid="production-bar"
          className="pointer-events-none fixed inset-x-0 bottom-6 z-40 flex justify-center px-4"
        >
          <div className="pointer-events-auto flex items-center gap-3 rounded-xl border border-border bg-card py-2 pl-4 pr-2 shadow-lg">
            <span className="text-[13px] tabular-nums">{items.length} selected</span>
            <Button size="sm" onClick={() => { setError(null); setConfirming(true) }}>
              <Icon name="rocket" size={14} aria-hidden="true" />On production
            </Button>
            <Button size="sm" variant="ghost" onClick={onClear} aria-label="Clear selection">
              <Icon name="x" size={14} aria-hidden="true" />
            </Button>
          </div>
        </div>
      )}
      <Dialog open={confirming} onClose={busy ? undefined : () => setConfirming(false)} title="Mark as on production" size="md">
        <div className="space-y-3 px-5 pb-5 pt-3 text-sm">
          <p className="text-[13px] text-muted-foreground">
            {plural(items.length, 'item')} will become <b>Done</b>, each with its own record. Support is told the fix is on production.
          </p>
          <ul className="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-border p-2" aria-label="Items going to production">
            {items.map((i) => (
              <li key={i.id} className="flex items-baseline gap-2 text-[13px]">
                <span className="shrink-0 font-mono text-[11.5px] text-muted-foreground">{issueKey(i)}</span>
                <span className="truncate">{i.title}</span>
              </li>
            ))}
          </ul>
          {error && (
            <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-[13px] text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400">
              {error}
            </div>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" size="sm" onClick={() => setConfirming(false)} disabled={busy}>Cancel</Button>
            <Button size="sm" onClick={submit} loading={busy} disabled={items.length === 0}>
              <Icon name="rocket" size={14} aria-hidden="true" />On production
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  )
}
