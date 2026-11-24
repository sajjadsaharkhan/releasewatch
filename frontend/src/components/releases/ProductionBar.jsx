import React, { useEffect, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
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
export function ProductionBar({ items, total = 0, onSelectAll, onClear, onDone, onRefused }) {
  const reduce = useReducedMotion()
  const { toast } = useToast()
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // What the dialog was opened with: a refusal prunes the live selection, but the
  // person still needs to read which items were refused.
  const [frozen, setFrozen] = useState([])

  // Nothing selected (a refresh pruned it) and nothing to explain — close.
  useEffect(() => { if (items.length === 0 && !error) setConfirming(false) }, [items.length, error])

  if (items.length === 0 && !confirming) return null

  const close = () => { setConfirming(false); setError(null) }
  const listed = confirming ? frozen : items

  async function submit() {
    setBusy(true); setError(null)
    try {
      const res = await issuesApi.bulkProduction(frozen.map((i) => i.id))
      const n = res.data?.issues?.length ?? items.length
      toast({ title: `${plural(n, 'item')} on production`, body: 'Marked Done.' })
      setConfirming(false)
      onDone?.(res.data)
    } catch (err) {
      const body = err.response?.data
      if (body?.code === 'not_verified_in_stream' && Array.isArray(body.issue_ids)) {
        const refused = frozen.filter((i) => body.issue_ids.includes(i.id))
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
      <AnimatePresence>
        {items.length > 0 && (
          <motion.div
            key="bar"
            role="region"
            aria-label="Selection"
            data-testid="production-bar"
            className="pointer-events-none fixed inset-x-0 bottom-6 z-40 flex justify-center px-4"
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: 16 }}
            transition={{ type: 'spring', stiffness: 380, damping: 32 }}
          >
            <div className="pointer-events-auto flex items-center gap-3 rounded-xl border border-border bg-card py-2 pl-4 pr-2 shadow-lg">
              <span className="text-[13px] tabular-nums">{items.length} selected</span>
              {onSelectAll && items.length < total && (
                <Button size="sm" variant="ghost" onClick={onSelectAll} data-testid="select-all-bar">
                  <Icon name="check-check" size={14} aria-hidden="true" />Select all {total}
                </Button>
              )}
              <Button size="sm" data-tour="production-submit" onClick={() => { setError(null); setFrozen(items); setConfirming(true) }}>
                <Icon name="rocket" size={14} aria-hidden="true" />On production
              </Button>
              <Button size="sm" variant="ghost" onClick={onClear} aria-label="Clear selection">
                <Icon name="x" size={14} aria-hidden="true" />
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <Dialog open={confirming} onClose={busy ? undefined : close} title="Mark as on production" size="md">
        <div className="space-y-3 px-5 pb-5 pt-3 text-sm">
          <p className="text-[13px] text-muted-foreground">
            {plural(listed.length, 'item')} will become <b>Done</b>, each with its own record. Support is told the fix is on production.
          </p>
          <ul className="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-border p-2" aria-label="Items going to production">
            {listed.map((i) => (
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
            <Button variant="outline" size="sm" onClick={close} disabled={busy}>{error ? 'Close' : 'Cancel'}</Button>
            <Button size="sm" onClick={submit} loading={busy} disabled={listed.length === 0 || !!error}>
              <Icon name="rocket" size={14} aria-hidden="true" />On production
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  )
}
