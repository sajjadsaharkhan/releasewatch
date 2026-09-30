import React, { useEffect, useState } from 'react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { CommentComposer } from './CommentComposer'
import { issuesApi } from '../../lib/api'
import { CYCLE_REASON } from '../../lib/constants'
import { useToast } from '../../hooks/useToast'

// Copy per way of sending work back (08a Part 3). The server decides a Done
// item's reason; `item.return_reason` only names the control.
const COPY = {
  review: {
    title: 'Reject',
    intro: 'The work goes back to To do for its assignee, with your comment as the reason.',
    label: "What's wrong with it",
    placeholder: 'What you tested, what happened, what you expected…',
    confirm: 'Reject',
  },
  release_qa: {
    title: 'Return from release QA',
    intro: "Release QA found a problem with this Done item. It goes back to To do in the same release, and its assignee is told why.",
    label: 'What release QA found',
    placeholder: 'Build, steps, what broke…',
    confirm: 'Return to To do',
  },
  production: {
    title: 'Problem on production',
    intro: "This work is on production and something's wrong. It goes back to To do — in the Stream if its release has shipped — and its assignee is told why.",
    label: "What's happening on production",
    placeholder: 'Who is affected, since when, what they see…',
    confirm: 'Send back',
  },
}

/**
 * Send work back with a required reason (08a Part 3): **Reject** from In
 * review (FR-57), **Return from release QA** / **Problem on production** from
 * Done (FR-59, FR-60). `reason` is `review` for a reject, else the item's
 * `return_reason`. `onDone` gets the updated item.
 */
export function SendBackDialog({ item, reason, open, onClose, onDone }) {
  const { toast } = useToast()
  const [comment, setComment] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [composerKey, setComposerKey] = useState(0)
  const copy = COPY[reason] ?? COPY.production

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
      const res = reason === 'review'
        ? await issuesApi.transition(item.id, { to: 'todo', comment })
        : await issuesApi.returnItem(item.id, { comment })
      const label = CYCLE_REASON[res.data.returned?.reason]?.label ?? copy.title
      toast({ title: `${item.key} is back in To do`, body: label })
      onDone?.(res.data)
      onClose()
    } catch (err) {
      toast.error("Couldn't send it back", err.response?.data?.detail)
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
            {copy.confirm}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
