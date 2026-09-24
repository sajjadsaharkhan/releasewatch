import React, { useEffect, useState } from 'react'
import { cn } from '../../lib/cn'
import { issuesApi } from '../../lib/api'
import { issueKey } from '../../lib/issueSlug'
import { PRIORITY, PRIORITIES } from '../../lib/constants'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { Select, SelectItem } from '../ui/Select'
import { Textarea } from '../ui/Textarea'
import { DuplicatePicker } from './DuplicatePicker'
import { UserPicker } from '../common'

const OUTCOMES = [
  { value: 'accept', label: 'Accept', icon: 'check' },
  { value: 'needs_info', label: 'Needs info', icon: 'help-circle' },
  { value: 'duplicate', label: 'Duplicate', icon: 'copy' },
  { value: 'reject', label: 'Reject', icon: 'x' },
]

const REJECT_REASONS = [
  { value: 'user_error', label: 'User error' },
  { value: 'expected_behavior', label: 'Expected behavior' },
  { value: 'cannot_reproduce', label: 'Cannot reproduce' },
]

const NO_RELEASE = '__none__'

function FieldLabel({ children, required, htmlFor }) {
  return (
    <label htmlFor={htmlFor} className="block text-[10.5px] uppercase tracking-wide font-semibold text-muted-foreground mb-1.5">
      {children} {required && <span className="text-destructive">*</span>}
    </label>
  )
}

/**
 * The four triage outcomes for one New / Needs info bug (slice 06, FR-18).
 * Each outcome opens a small form asking for exactly its inputs; `onDone`
 * receives the updated item so the page can drop it from the queue.
 */
export function TriageOutcomePanel({ issue, assignable, releases, acceptsReleases, onDone, toast }) {
  const [outcome, setOutcome] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const [priority, setPriority] = useState(null)
  const [assigneeId, setAssigneeId] = useState(null)
  const [releaseId, setReleaseId] = useState(NO_RELEASE)
  const [comment, setComment] = useState('')
  const [reason, setReason] = useState(null)
  const [original, setOriginal] = useState(null)
  const [suggestion, setSuggestion] = useState(null)

  useEffect(() => {
    setOutcome(null)
    setPriority(issue.priority ?? null)
    setAssigneeId(issue.assignee_id ?? null)
    setReleaseId(issue.release_id ? String(issue.release_id) : NO_RELEASE)
    setComment('')
    setReason(null)
    setOriginal(null)
    setSuggestion(null)
  }, [issue.id])

  function choose(next) {
    setOutcome(o => (o === next ? null : next))
    setComment('')
    setSuggestion(null)
  }

  function payload() {
    if (outcome === 'accept') {
      return {
        outcome,
        priority,
        assignee_id: assigneeId,
        // Always sent: the picker is prefilled with the bug's release, so
        // "No release" is an explicit choice of the hotfix path.
        release_id: releaseId === NO_RELEASE ? null : Number(releaseId),
      }
    }
    if (outcome === 'needs_info') return { outcome, comment: comment.trim() }
    if (outcome === 'duplicate') return { outcome, duplicate_of_id: original?.id, comment: comment.trim() || null }
    return { outcome, reason, comment: comment.trim() || null }
  }

  const canSubmit = {
    accept: !!priority,
    needs_info: comment.trim().length > 0,
    duplicate: !!original,
    reject: !!reason,
  }[outcome]

  async function submit() {
    setSubmitting(true)
    setSuggestion(null)
    try {
      const res = await issuesApi.triage(issue.id, payload())
      const key = issueKey(issue)
      const messages = {
        accept: { title: `${key} accepted`, body: 'It moved to To do.' },
        needs_info: { title: 'Question sent', body: 'The reporter was asked for more information.' },
        duplicate: { title: `${key} merged into ${issueKey(original)}` },
        reject: { title: `${key} rejected` },
      }
      toast(messages[outcome])
      onDone(res.data)
    } catch (err) {
      const data = err?.response?.data
      if (data?.code === 'duplicate_of_duplicate' && data.suggested_id) {
        setSuggestion({ id: data.suggested_id, key: data.suggested_key })
      } else {
        toast.error(typeof data?.detail === 'string' ? data.detail : 'Failed to apply the triage outcome')
      }
    } finally {
      setSubmitting(false)
    }
  }

  async function useSuggestion() {
    try {
      const res = await issuesApi.get(suggestion.id)
      setOriginal(res.data)
      setSuggestion(null)
    } catch {
      toast.error('Failed to load the suggested original')
    }
  }

  const submitLabel = {
    accept: 'Accept',
    needs_info: 'Ask reporter',
    duplicate: original ? `Merge into ${issueKey(original)}` : 'Merge',
    reject: 'Reject',
  }[outcome]

  return (
    <div className="mt-5">
      <FieldLabel>Outcome</FieldLabel>
      <div className="grid grid-cols-4 gap-1.5" role="group" aria-label="Triage outcome">
        {OUTCOMES.map(o => (
          <button
            key={o.value}
            type="button"
            onClick={() => choose(o.value)}
            aria-pressed={outcome === o.value}
            className={cn(
              'flex flex-col items-center justify-center gap-1 h-14 rounded-md border text-[11.5px] font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              outcome === o.value
                ? 'border-foreground bg-foreground text-background'
                : 'border-border bg-background text-foreground hover:bg-muted',
            )}
          >
            <Icon name={o.icon} size={14} aria-hidden="true" />
            {o.label}
          </button>
        ))}
      </div>

      {outcome && (
        <div className="mt-4 rounded-lg border border-border bg-background p-4 space-y-4">
          {outcome === 'accept' && (
            <>
              <div>
                <FieldLabel required>Priority</FieldLabel>
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Priority">
                  {PRIORITIES.map(p => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setPriority(p)}
                      aria-pressed={priority === p}
                      className={cn(
                        'h-8 px-2.5 rounded-md text-[11.5px] font-medium border transition-colors flex items-center gap-1.5',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                        priority === p
                          ? 'bg-foreground text-background border-foreground'
                          : 'bg-background text-muted-foreground border-border hover:bg-muted',
                      )}
                    >
                      <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', PRIORITY[p].dot)} />
                      {PRIORITY[p].label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <FieldLabel>Assignee</FieldLabel>
                <UserPicker users={assignable} value={assigneeId} onChange={setAssigneeId} />
              </div>
              {acceptsReleases && (
                <div>
                  <FieldLabel>Release</FieldLabel>
                  <Select value={releaseId} onChange={setReleaseId}>
                    <SelectItem value={NO_RELEASE}>No release (hotfix)</SelectItem>
                    {releases.map(r => (
                      <SelectItem key={r.id} value={String(r.id)}>{r.version}</SelectItem>
                    ))}
                  </Select>
                </div>
              )}
            </>
          )}

          {outcome === 'needs_info' && (
            <div>
              <FieldLabel required htmlFor="triage-question">What's missing</FieldLabel>
              <Textarea
                id="triage-question"
                rows={4}
                value={comment}
                onChange={e => setComment(e.target.value)}
                placeholder="e.g. Which app version is the customer on, and does it happen on Wi-Fi too?"
              />
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                Posted as a public comment. The reporter is notified, and their reply sends the bug back to New.
              </p>
            </div>
          )}

          {outcome === 'duplicate' && (
            <>
              <div>
                <FieldLabel required>Original bug</FieldLabel>
                <DuplicatePicker issue={issue} value={original} onChange={o => { setOriginal(o); setSuggestion(null) }} />
                {suggestion && (
                  <div role="alert" className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300">
                    {issueKey(original)} is itself a duplicate.{' '}
                    <button type="button" onClick={useSuggestion} className="font-medium underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm">
                      Use {suggestion.key ?? 'its original'} instead
                    </button>
                  </div>
                )}
                <p className="mt-1.5 text-[11px] text-muted-foreground">
                  This bug is cancelled and its title and description are added to the original as a comment.
                </p>
              </div>
              <div>
                <FieldLabel htmlFor="triage-dup-comment">Comment</FieldLabel>
                <Textarea id="triage-dup-comment" rows={2} value={comment} onChange={e => setComment(e.target.value)} placeholder="Optional" />
              </div>
            </>
          )}

          {outcome === 'reject' && (
            <>
              <div>
                <FieldLabel required>Reason</FieldLabel>
                <Select value={reason} onChange={setReason} placeholder="Choose a reason…">
                  {REJECT_REASONS.map(r => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
                </Select>
              </div>
              <div>
                <FieldLabel htmlFor="triage-reject-comment">Comment</FieldLabel>
                <Textarea id="triage-reject-comment" rows={2} value={comment} onChange={e => setComment(e.target.value)} placeholder="Optional — posted publicly so the reporter knows why" />
              </div>
            </>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setOutcome(null)} disabled={submitting}>Cancel</Button>
            <Button size="sm" onClick={submit} disabled={!canSubmit} loading={submitting}
              variant={outcome === 'reject' ? 'destructive' : 'default'}>
              {submitLabel}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
