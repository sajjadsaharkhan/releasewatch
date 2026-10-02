import React, { useEffect, useState } from 'react'
import { cn } from '../../lib/cn'
import { issuesApi } from '../../lib/api'
import { issueKey } from '../../lib/issueSlug'
import { PRIORITY, PRIORITIES } from '../../lib/constants'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { Textarea } from '../ui/Textarea'
import { DuplicatePicker } from './DuplicatePicker'
import { BacklogCategoryPicker, ContainerPicker, UserPicker } from '../common'
import { useBacklogCategories } from '../../hooks/useBacklogCategories'

// Each outcome has one hue, used for its button, icon, notes and submit button:
// accept green, needs info sky (the Needs info status), duplicate amber (the
// possible-duplicate marker), reject red. Semantic colors use raw palette
// classes with explicit dark: variants (docs/design.md §2).
const TONE = {
  green: {
    idle: 'border-green-200 hover:bg-green-50 dark:border-green-900/60 dark:hover:bg-green-950/30',
    icon: 'text-green-600 dark:text-green-400',
    on: 'border-green-600 bg-green-600 text-white dark:border-green-600 dark:bg-green-600',
    note: 'border-green-200 bg-green-50 text-green-800 dark:border-green-900/60 dark:bg-green-950/30 dark:text-green-300',
    submit: 'bg-green-600 text-white hover:bg-green-700 dark:bg-green-600 dark:hover:bg-green-500',
  },
  sky: {
    idle: 'border-sky-200 hover:bg-sky-50 dark:border-sky-900/60 dark:hover:bg-sky-950/30',
    icon: 'text-sky-600 dark:text-sky-400',
    on: 'border-sky-600 bg-sky-600 text-white dark:border-sky-600 dark:bg-sky-600',
    note: 'border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-900/60 dark:bg-sky-950/30 dark:text-sky-300',
    submit: 'bg-sky-600 text-white hover:bg-sky-700 dark:bg-sky-600 dark:hover:bg-sky-500',
  },
  amber: {
    idle: 'border-amber-200 hover:bg-amber-50 dark:border-amber-900/60 dark:hover:bg-amber-950/30',
    icon: 'text-amber-600 dark:text-amber-400',
    on: 'border-amber-600 bg-amber-600 text-white dark:border-amber-600 dark:bg-amber-600',
    note: 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300',
    submit: 'bg-amber-600 text-white hover:bg-amber-700 dark:bg-amber-600 dark:hover:bg-amber-500',
  },
  red: {
    idle: 'border-red-200 hover:bg-red-50 dark:border-red-900/60 dark:hover:bg-red-950/30',
    icon: 'text-red-600 dark:text-red-400',
    on: 'border-red-600 bg-red-600 text-white dark:border-red-600 dark:bg-red-600',
    note: 'border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300',
    submit: '',
  },
}

const OUTCOMES = [
  { value: 'accept', label: 'Accept', icon: 'check', tone: 'green' },
  { value: 'needs_info', label: 'Needs info', icon: 'help-circle', tone: 'sky' },
  { value: 'duplicate', label: 'Duplicate', icon: 'copy', tone: 'amber' },
  { value: 'reject', label: 'Reject', icon: 'x', tone: 'red' },
]

function FieldLabel({ children, required, optional, htmlFor }) {
  return (
    <label htmlFor={htmlFor} className="block text-[10.5px] uppercase tracking-wide font-semibold text-muted-foreground mb-1.5">
      {children} {required && <span className="text-destructive">*</span>}
      {optional && (
        <span className="ml-1.5 rounded bg-muted px-1.5 py-px text-[10px] font-medium normal-case tracking-normal text-muted-foreground">Optional</span>
      )}
    </label>
  )
}

/** A note that matters — tinted with its outcome's hue, never muted grey. */
function Note({ tone, icon = 'info', children }) {
  return (
    <p className={cn('mt-2 flex items-start gap-2 rounded-md border px-2.5 py-2 text-[11.5px] leading-snug', TONE[tone].note)}>
      <Icon name={icon} size={13} className="mt-px shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </p>
  )
}

/**
 * The four triage outcomes for one New / Needs info bug (slice 06, FR-18).
 * Each outcome opens a small form asking for exactly its inputs; `onDone`
 * receives the updated item so the page can drop it from the queue.
 * `presetOriginal` (slice 14) opens the Duplicate outcome with that item
 * already chosen — what a duplicate hint's **Merge into this** passes.
 */
export function TriageOutcomePanel({ issue, assignable, onDone, toast, presetOriginal }) {
  const [outcome, setOutcome] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const [priority, setPriority] = useState(null)
  const [assigneeId, setAssigneeId] = useState(null)
  const [releaseId, setReleaseId] = useState(null)
  const [category, setCategory] = useState(null)
  const { categories } = useBacklogCategories(issue.project_id)
  const intoBacklog = releaseId == null
  const [comment, setComment] = useState('')
  const [original, setOriginal] = useState(null)
  const [suggestion, setSuggestion] = useState(null)

  useEffect(() => {
    setOutcome(null)
    setPriority(issue.priority ?? null)
    setAssigneeId(issue.assignee_id ?? null)
    setReleaseId(issue.release_id ?? null)
    setCategory(issue.backlog_category_id ?? null)
    setComment('')
    setOriginal(null)
    setSuggestion(null)
  }, [issue.id])

  // A hint's "Merge into this": the Duplicate form, preselected (FR-S14).
  useEffect(() => {
    if (!presetOriginal) return
    setOutcome('duplicate')
    setOriginal(presetOriginal)
  }, [presetOriginal])

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
        // Always sent: the picker is prefilled with the bug's container, so
        // "Backlog" is an explicit choice.
        release_id: releaseId,
        // Only for the backlog, and only when changed — otherwise the bug keeps
        // its category (Default).
        ...(intoBacklog && category != null && category !== issue.backlog_category_id
          ? { backlog_category_id: category } : {}),
      }
    }
    if (outcome === 'needs_info') return { outcome, comment: comment.trim() }
    if (outcome === 'duplicate') return { outcome, duplicate_of_id: original?.id, comment: comment.trim() || null }
    return { outcome, comment: comment.trim() }
  }

  const tone = OUTCOMES.find(o => o.value === outcome)?.tone
  const canSubmit = {
    accept: !!priority,
    needs_info: comment.trim().length > 0,
    duplicate: !!original,
    reject: comment.trim().length > 0,
  }[outcome]

  async function submit() {
    setSubmitting(true)
    setSuggestion(null)
    try {
      const res = await issuesApi.triage(issue.id, payload())
      const key = issueKey(issue)
      const messages = {
        accept: {
          title: `${key} accepted`,
          body: intoBacklog ? 'It moved to To do, in the backlog.' : 'It moved to To do.',
        },
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
                ? TONE[o.tone].on
                : cn('bg-background text-foreground', TONE[o.tone].idle),
            )}
          >
            <Icon name={o.icon} size={15} className={outcome === o.value ? undefined : TONE[o.tone].icon} aria-hidden="true" />
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
                <FieldLabel optional>Assignee</FieldLabel>
                <UserPicker users={assignable} value={assigneeId} onChange={setAssigneeId} />
              </div>
              <div>
                <FieldLabel>Place in</FieldLabel>
                <ContainerPicker projectId={issue.project_id} value={releaseId} onChange={setReleaseId} />
              </div>
              {/* Only for the backlog, and only worth asking when the project
                  has more than Default. */}
              {intoBacklog && categories.length > 1 && (
                <div>
                  <FieldLabel optional>
                    <span id="triage-category-label">Backlog category</span>
                  </FieldLabel>
                  <BacklogCategoryPicker
                    aria-labelledby="triage-category-label"
                    categories={categories}
                    value={category}
                    onChange={setCategory}
                  />
                  <Note tone="green" icon="archive">
                    In the backlog, the bug is grouped under this category. Leave it empty to use the project&apos;s Default.
                  </Note>
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
              <Note tone="sky" icon="megaphone">
                Posted as a public comment. The reporter is notified, and their reply sends the bug back to New.
              </Note>
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
                <Note tone="amber" icon="info">
                  This bug is cancelled and its title and description are added to the original as a comment.
                </Note>
              </div>
              <div>
                <FieldLabel optional htmlFor="triage-dup-comment">Comment</FieldLabel>
                <Textarea id="triage-dup-comment" rows={2} value={comment} onChange={e => setComment(e.target.value)} placeholder="Optional" />
              </div>
            </>
          )}

          {outcome === 'reject' && (
            <div>
              <FieldLabel required htmlFor="triage-reject-comment">Why it is rejected</FieldLabel>
              <Textarea id="triage-reject-comment" rows={3} value={comment} onChange={e => setComment(e.target.value)}
                placeholder="e.g. Works as designed — the limit is 10 MB per file." />
              <Note tone="red" icon="megaphone">
                Posted publicly so the reporter knows why.
              </Note>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setOutcome(null)} disabled={submitting}>Cancel</Button>
            <Button size="sm" onClick={submit} disabled={!canSubmit} loading={submitting}
              variant={outcome === 'reject' ? 'destructive' : 'default'}
              className={TONE[tone].submit}>
              {submitLabel}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
