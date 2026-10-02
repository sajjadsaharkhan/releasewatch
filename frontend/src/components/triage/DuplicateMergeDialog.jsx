import React, { useState } from 'react'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { Textarea } from '../ui/Textarea'
import { issuesApi } from '../../lib/api'
import { issueKey } from '../../lib/issueSlug'
import { SimilarityRing } from './SimilarityRing'
import { mergeEffectSentence } from './mergeEffect'

/**
 * Confirms and performs "Merge into this" for a candidate (slice 06 Duplicate
 * outcome, BR-20/49): says exactly what will happen, takes an optional comment,
 * and calls the triage endpoint itself — so one click on a candidate card is
 * one decision, not a form to find and finish. `onMerged(updatedIssue)` gets
 * the cancelled duplicate. A `duplicate_of_duplicate` refusal offers the real
 * original instead.
 */
export function DuplicateMergeDialog({ issue, hint, onClose, onMerged, toast }) {
  const candidate = hint.candidate
  const [target, setTarget] = useState({ id: candidate.id, key: candidate.key })
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [suggestion, setSuggestion] = useState(null)
  const [error, setError] = useState(null)
  const key = issueKey(issue)

  async function submit() {
    setSubmitting(true)
    setError(null)
    try {
      const res = await issuesApi.triage(issue.id, {
        outcome: 'duplicate', duplicate_of_id: target.id, comment: comment.trim() || null,
      })
      toast({ title: `${key} merged into ${target.key}` })
      onMerged(res.data, target)
    } catch (err) {
      const data = err?.response?.data
      if (data?.code === 'duplicate_of_duplicate' && data.suggested_id) {
        setSuggestion({ id: data.suggested_id, key: data.suggested_key ?? 'its original' })
      } else {
        setError(typeof data?.detail === 'string' ? data.detail : 'The merge failed — nothing was changed.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open onClose={submitting ? undefined : onClose} size="md" title={`Merge ${key} into ${target.key}?`}>
      <div className="space-y-4 p-5">
        <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2.5 dark:border-amber-900/60 dark:bg-amber-950/20">
          <SimilarityRing confidence={hint.confidence} size={36} />
          <p className="min-w-0 text-[12.5px]">
            <span className="font-mono">{candidate.key}</span> {candidate.title}
          </p>
        </div>

        <ul className="space-y-1.5 text-[12.5px]">
          <li className="flex gap-2"><Icon name="x-circle" size={14} className="mt-0.5 shrink-0 text-muted-foreground" aria-hidden="true" />
            <span><span className="font-mono">{key}</span> is cancelled as a duplicate.</span></li>
          <li className="flex gap-2"><Icon name="message-square" size={14} className="mt-0.5 shrink-0 text-muted-foreground" aria-hidden="true" />
            <span>Its title and description, and your comment below, are added to <span className="font-mono">{target.key}</span> as one comment.</span></li>
          <li className="flex gap-2"><Icon name="repeat" size={14} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
            <span><span className="font-mono">{target.key}</span> if merged: {mergeEffectSentence(hint)}.</span></li>
        </ul>

        <div>
          <label htmlFor="merge-comment" className="mb-1.5 flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
            Comment
            <span className="rounded bg-muted px-1.5 py-px text-[10px] font-medium normal-case tracking-normal">Optional</span>
          </label>
          <Textarea id="merge-comment" rows={2} value={comment} onChange={e => setComment(e.target.value)}
            placeholder="Goes into the merge comment on the original, above the merged report" />
        </div>

        {suggestion && (
          <div role="alert" className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300">
            {target.key} is itself a duplicate.{' '}
            <button type="button" onClick={() => { setTarget(suggestion); setSuggestion(null) }}
              className="rounded-sm font-medium underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              Merge into {suggestion.key} instead
            </button>
          </div>
        )}
        {error && (
          <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-800 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
            {error}
          </div>
        )}
      </div>
      <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
        <Button variant="outline" onClick={onClose} disabled={submitting}>Cancel</Button>
        <Button onClick={submit} loading={submitting}
          className="bg-amber-600 text-white hover:bg-amber-700 dark:bg-amber-600 dark:hover:bg-amber-500">
          Merge into {target.key}
        </Button>
      </div>
    </Dialog>
  )
}
