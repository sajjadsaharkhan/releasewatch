import React, { useEffect, useState } from 'react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { CommentComposer } from './CommentComposer'
import { issuesApi } from '../../lib/api'
import { useToast } from '../../hooks/useToast'

/**
 * Report recurrence (slice 07, FR-13) — one more occurrence of an open or
 * Cancelled bug instead of a duplicate report. The comment is required: it's
 * where the new customer's details go. `onReported` gets the updated item.
 */
export function RecurrenceDialog({ item, open, onClose, onReported }) {
  const { toast } = useToast()
  const [comment, setComment] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [composerKey, setComposerKey] = useState(0)

  useEffect(() => {
    if (!open) return
    setComment('')
    setError(null)
    setComposerKey((k) => k + 1)
  }, [open])

  async function submit() {
    if (!comment.trim()) {
      setError("Add the new occurrence's details.")
      return
    }
    setSubmitting(true)
    try {
      const res = await issuesApi.reportRecurrence(item.id, { comment })
      toast({ title: 'Recurrence recorded', body: `${item.key} has been reported ${res.data.recurrence_count} times.` })
      onReported?.(res.data)
      onClose()
    } catch (err) {
      toast.error('Failed to report recurrence', err.response?.data?.detail)
    } finally {
      setSubmitting(false)
    }
  }

  const cancelled = item?.status === 'cancelled'

  return (
    <Dialog open={open} onClose={onClose} title="Report recurrence" size="md">
      <div className="px-5 pt-3 pb-5 space-y-3">
        <p className="text-[13px] text-muted-foreground">
          Someone else hit <span className="font-mono">{item?.key}</span>. This adds one to its
          report count and posts your comment on its timeline. You'll hear when it's fixed or closed.
        </p>
        {cancelled && (
          <p className="flex items-start gap-1.5 rounded-md border border-amber-200 bg-amber-50/70 px-3 py-2 text-[12px] text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300">
            <Icon name="info" size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
            This bug is cancelled. It stays cancelled; the triage lead is told so they can reconsider.
          </p>
        )}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            What happened this time
          </label>
          <CommentComposer
            key={composerKey}
            initialValue=""
            onChange={(v) => { setComment(v); if (error && v.trim()) setError(null) }}
            placeholder="Customer, account or order, when it happened, anything different…"
            showInternal={false}
            hideFooter
          />
          {error && <p role="alert" className="mt-1.5 text-[12px] text-destructive">{error}</p>}
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" loading={submitting} onClick={submit}>Report recurrence</Button>
        </div>
      </div>
    </Dialog>
  )
}
