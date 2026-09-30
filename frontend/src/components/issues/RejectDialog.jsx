import React, { useEffect, useState } from 'react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { CommentComposer } from './CommentComposer'
import { issuesApi } from '../../lib/api'
import { CYCLE_REASON } from '../../lib/constants'
import { useToast } from '../../hooks/useToast'

// The same action has two names (09a): Reject for work in review, Return for
// a Done item — it's already out, so it comes back rather than being rejected.
const COPY = {
  reject: {
    title: 'Reject',
    intro: 'The work goes back to its assignee as Rejected, with your comment as the reason.',
    label: "What's wrong with it",
    placeholder: 'What you tested, what happened, what you expected…',
    done: (key) => `${key} is rejected`,
  },
  return: {
    title: 'Return',
    intro: "This work is Done, and something's wrong with it. It goes back to its assignee — in the Stream if its release has shipped — with your comment as the reason.",
    label: "What's wrong with it",
    placeholder: 'Where it broke (release QA or production), who is affected, what they see…',
    done: (key) => `${key} is returned`,
  },
}

/**
 * **Reject** / **Return** (09a): send To review, In review or Done work back
 * with a required comment. One action wherever the problem was caught — the
 * server decides whether it was review, release QA or production, and the item
 * lands in Rejected for its assignee. `onDone` gets the updated item.
 */
export function RejectDialog({ item, open, onClose, onDone }) {
  const { toast } = useToast()
  const [comment, setComment] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [composerKey, setComposerKey] = useState(0)
  const copy = item?.status === 'done' ? COPY.return : COPY.reject

  useEffect(() => {
    if (!open) return
    setComment('')
    setError(null)
    setComposerKey((k) => k + 1)
  }, [open])

  async function submit() {
    if (!comment.trim()) {
      setError('Say why the work is coming back.')
      return
    }
    setSubmitting(true)
    try {
      const res = await issuesApi.reject(item.id, { comment })
      const label = CYCLE_REASON[res.data.reject_reason]?.label ?? 'Rejected'
      toast({ title: copy.done(item.key), body: label })
      onDone?.(res.data)
      onClose()
    } catch (err) {
      toast.error(`Couldn't ${copy.title.toLowerCase()} it`, err.response?.data?.detail)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title={copy.title} size="md">
      <div className="px-5 pt-3 pb-5 space-y-3">
        <p className="text-[13px] text-muted-foreground">{copy.intro}</p>
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            {copy.label} <span className="text-destructive">*</span>
          </label>
          <CommentComposer
            key={composerKey}
            initialValue=""
            onChange={(v) => { setComment(v); if (error && v.trim()) setError(null) }}
            placeholder={copy.placeholder}
            showInternal={false}
            hideFooter
          />
          {error && (
            <p role="alert" className="mt-1.5 inline-flex items-center gap-1 text-[12px] text-destructive">
              <Icon name="alert-circle" size={12} aria-hidden="true" /> {error}
            </p>
          )}
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" variant="destructive" loading={submitting} disabled={!comment.trim()} onClick={submit}>
            {copy.title}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
