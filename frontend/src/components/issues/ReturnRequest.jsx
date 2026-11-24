import React, { useEffect, useState } from 'react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { Avatar } from '../ui/Avatar'
import { Tooltip } from '../ui/Tooltip'
import { CommentComposer } from './CommentComposer'
import { AttachmentsSection } from './AttachmentsSection'
import { ActionButton, actionState } from '../common/ActionButton'
import { returnRequestsApi } from '../../lib/api'
import { relTime, fullTime } from '../../lib/relTime'
import { useToast } from '../../hooks/useToast'

/**
 * Problem is back (slice 20, FR-68) — a Support user says a Done item's problem
 * has returned. It records a request; it doesn't create an item, change the
 * status or count a recurrence. With a Pending request the same dialog adds to
 * it. The comment is required, attachments optional. `onSaved` runs after.
 */
export function ReturnRequestDialog({ item, open, onClose, onSaved }) {
  const { toast } = useToast()
  const pending = !!(item?.pending_return_request || item?.return_requested)
  const [comment, setComment] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [composerKey, setComposerKey] = useState(0)
  const [attachments, setAttachments] = useState([])
  const [pendingAttachments, setPendingAttachments] = useState([])
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    if (!open) return
    setComment('')
    setError(null)
    setAttachments([])
    setPendingAttachments([])
    setComposerKey((k) => k + 1)
  }, [open])

  async function submit() {
    if (!comment.trim()) {
      setError("Say what the customer sees now.")
      return
    }
    setSubmitting(true)
    try {
      await returnRequestsApi.request(item.id, { comment, pending_attachments: pendingAttachments })
      toast({
        title: pending ? 'Added to the pending request' : 'Return requested',
        body: pending ? 'Triage will see your report with the others.' : `Triage will decide whether ${item.key} goes back for a fix.`,
      })
      onSaved?.()
      onClose()
    } catch (err) {
      toast.error("Couldn't send the request", err.response?.data?.detail)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title={pending ? 'Add to pending request' : 'Problem is back'} size="md">
      <div className="px-5 pt-3 pb-5 space-y-3">
        <p className="text-[13px] text-muted-foreground">
          <span className="font-mono">{item?.key}</span> is Done, but the problem is back on production.
          {pending
            ? ' Triage already has a request open — yours is added to it.'
            : ' This asks triage to send it back for another fix. Nothing changes on the item until they decide, and you will hear the outcome.'}
        </p>
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            What happened this time <span className="text-destructive">*</span>
          </label>
          <CommentComposer
            key={composerKey}
            initialValue=""
            onChange={(v) => { setComment(v); if (error && v.trim()) setError(null) }}
            placeholder="Customer, account or order, when it happened, what they see…"
            showInternal={false}
            hideFooter
          />
          {error && (
            <p role="alert" className="mt-1.5 inline-flex items-center gap-1 text-[12px] text-destructive">
              <Icon name="alert-circle" size={12} aria-hidden="true" /> {error}
            </p>
          )}
        </div>
        <AttachmentsSection
          compact
          issue={{ attachments }}
          onAttachmentsChange={setAttachments}
          onUploadingChange={setUploading}
          onPendingAttachment={(p) => setPendingAttachments((prev) => [...prev, p])}
        />
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" loading={submitting} disabled={uploading || !comment.trim()} onClick={submit}>
            {pending ? 'Add to request' : 'Send request'}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}

/**
 * The Problem is back control for one Done item. Its presence comes from the API
 * (`request_return` in allowed_actions) — tech roles never get it.
 */
export function ProblemIsBackButton({ item, onSaved, className, compact = false }) {
  const [open, setOpen] = useState(false)
  if (!item?.allowed_actions?.includes('request_return')) return null
  const pending = !!(item.pending_return_request || item.return_requested)
  const label = pending ? 'Add to pending request' : 'Problem is back'
  return (
    <>
      {compact ? (
        <Tooltip content={label}>
          <Button
            size="icon-sm" variant="ghost" aria-label={label}
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(true) }}
          >
            <Icon name="rotate-ccw" size={14} aria-hidden="true" />
          </Button>
        </Tooltip>
      ) : (
        <ActionButton
          action="request_return" item={item} variant="outline" className={className}
          onClick={() => setOpen(true)}
        >
          <Icon name="rotate-ccw" size={14} className="mr-1" aria-hidden="true" />
          {label}
        </ActionButton>
      )}
      <ReturnRequestDialog item={item} open={open} onClose={() => setOpen(false)} onSaved={onSaved} />
    </>
  )
}

/** Dismiss: the item stays Done, and the requesters get the explanation. */
function DismissDialog({ request, item, open, onClose, onDone }) {
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
      setError('Tell Support why it stays Done.')
      return
    }
    setSubmitting(true)
    try {
      await returnRequestsApi.dismiss(request.id, comment)
      toast({ title: 'Request dismissed', body: `${item.key} stays Done. Support has your explanation.` })
      onDone?.()
      onClose()
    } catch (err) {
      toast.error("Couldn't dismiss the request", err.response?.data?.detail)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Dismiss request" size="md">
      <div className="px-5 pt-3 pb-5 space-y-3">
        <p className="text-[13px] text-muted-foreground">
          The item stays Done and no cycle starts. Your comment is posted publicly and sent to the people who asked.
        </p>
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Why it stays Done <span className="text-destructive">*</span>
          </label>
          <CommentComposer
            key={composerKey}
            initialValue=""
            onChange={(v) => { setComment(v); if (error && v.trim()) setError(null) }}
            placeholder="What you checked, why this isn't the same problem…"
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
          <Button size="sm" loading={submitting} disabled={!comment.trim()} onClick={submit}>Dismiss request</Button>
        </div>
      </div>
    </Dialog>
  )
}

/**
 * Confirm / Dismiss for one Pending request — used on the item page's banner and
 * in the Triage page's detail pane. Shown only where `decide_return_request` is
 * allowed. `onDecided` runs after either outcome.
 */
export function ReturnRequestActions({ request, item, onDecided, size = 'sm' }) {
  const { toast } = useToast()
  const [confirming, setConfirming] = useState(false)
  const [dismissing, setDismissing] = useState(false)

  async function confirm() {
    setConfirming(true)
    try {
      const res = await returnRequestsApi.confirm(request.id)
      toast({
        title: res.data.item_already_returned ? 'Request closed' : `${item.key} is going back`,
        body: res.data.item_already_returned
          ? 'The item had already left Done.'
          : 'Rejected, and its assignee has your comment as the reason.',
      })
      onDecided?.()
    } catch (err) {
      toast.error("Couldn't confirm the request", err.response?.data?.detail)
    } finally {
      setConfirming(false)
    }
  }

  return (
    <>
      <Button size={size} loading={confirming} onClick={confirm}>
        <Icon name="undo-2" size={14} className="mr-1" aria-hidden="true" /> Confirm
      </Button>
      <Button size={size} variant="outline" onClick={() => setDismissing(true)}>Dismiss</Button>
      <DismissDialog
        request={request} item={item} open={dismissing}
        onClose={() => setDismissing(false)} onDone={onDecided}
      />
    </>
  )
}

/**
 * The banner on an item with a Pending return request: who asked, how many
 * reports, and — for whoever may decide — Confirm and Dismiss. `onChanged`
 * refreshes the item after a decision.
 */
export function ReturnRequestBanner({ item, onChanged }) {
  const request = item?.pending_return_request
  if (!request) return null
  const entries = request.entries ?? []
  const n = entries.length
  const canDecide = actionState(item, 'decide_return_request').state === 'allowed'
  const first = entries[0]
  const names = [...new Set(entries.map((e) => e.user?.name).filter(Boolean))]

  return (
    <section
      role="note"
      aria-label="Return requested"
      data-testid="return-request-banner"
      className="mt-4 rounded-md border border-amber-200 bg-amber-50/70 px-3.5 py-3 text-[13px] dark:border-amber-900/50 dark:bg-amber-950/20"
    >
      <div className="flex items-start gap-2">
        <Icon name="rotate-ccw" size={14} className="mt-0.5 shrink-0 text-amber-700 dark:text-amber-300" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-amber-900 dark:text-amber-200">
            Return requested
            <span className="font-normal text-amber-800/80 dark:text-amber-300/80">
              {' '}· {n} {n === 1 ? 'report' : 'reports'} · waiting for triage
            </span>
          </p>
          <p className="mt-0.5 text-[12px] text-amber-800/80 dark:text-amber-300/80" title={fullTime(request.requested_at)}>
            {names.length > 0 && <>{names.join(', ')} · </>}asked {relTime(request.requested_at)}
          </p>
          {canDecide && first?.body && (
            <blockquote className="mt-2 border-l-2 border-amber-300 pl-2.5 text-[12.5px] text-foreground/80 line-clamp-3 dark:border-amber-800">
              {first.body}
            </blockquote>
          )}
          {canDecide && (
            <div className="mt-3 flex items-center gap-2">
              <ReturnRequestActions request={request} item={item} onDecided={onChanged} />
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

/** Who pressed Problem is back, as small avatars — the Triage row and detail pane. */
export function Requesters({ users = [] }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="flex -space-x-1">
        {users.slice(0, 3).map((u) => <Avatar key={u.id} user={u} size={14} />)}
      </span>
      <span>{users.map((u) => u.name).slice(0, 2).join(', ')}{users.length > 2 ? ` +${users.length - 2}` : ''}</span>
    </span>
  )
}
