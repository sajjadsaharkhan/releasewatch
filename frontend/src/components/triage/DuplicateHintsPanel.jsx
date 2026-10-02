import React, { useEffect, useState } from 'react'
import { Icon } from '../ui/Icon'
import { useDuplicateHints } from '../../hooks/useDuplicateHints'
import { DuplicateCandidateCard } from './DuplicateCandidateCard'
import { DuplicateCompareDialog } from './DuplicateCompareDialog'
import { DuplicateMergeDialog } from './DuplicateMergeDialog'
import { useToast } from '../ui/Toast'

/** At or above this similarity the panel opens by itself — a near-certain match should not hide. */
const AUTO_OPEN_AT = 0.9

/**
 * Stored possible duplicates of a New bug (slice 14, FR-S12–S15) on the item
 * page — the same candidates as the triage pane's Duplicates tab
 * (`DuplicateCandidateCard`, laid out as one row each: similarity ring and %,
 * title and merge effect, **Merge** / **Compare** / **Not a duplicate**).
 * The panel is collapsed to its header by default and opens by itself when the
 * best match is 90% or more; the reader's own toggle wins from then on.
 * **Merge** confirms and performs the merge right here, then calls
 * `onMerged(updatedIssue, original)`. Opening a bug that was never judged
 * starts the comparison; a quiet line says so until it lands. Support never
 * sees this (FR-S13; the page gates on allowed_actions, never the role).
 */
export function DuplicateHintsPanel({ issue, attachments = [], onMerged, onDismissed }) {
  const hints = useDuplicateHints(issue, { onDismissed })
  const { toast } = useToast()
  const [compare, setCompare] = useState(null)
  const [merging, setMerging] = useState(null)
  // null = follow the default; true/false = the reader chose.
  const [chosen, setChosen] = useState(null)
  useEffect(() => { setChosen(null); setCompare(null); setMerging(null) }, [issue.id])

  if (!hints.eligible) return null
  if (hints.hints.length === 0) {
    return hints.computing ? (
      <p role="status" className="mt-3 flex items-center gap-1.5 text-[12px] text-muted-foreground">
        <Icon name="loader" size={12} className="animate-spin text-amber-600 dark:text-amber-400" aria-hidden="true" />
        Looking for similar bugs…
      </p>
    ) : null
  }

  const merge = (candidate) => setMerging(hints.hints.find(h => h.candidate_id === candidate.id) ?? null)
  const top = hints.hints[0]
  const open = chosen ?? top.confidence >= AUTO_OPEN_AT
  const listId = `duplicate-hints-${issue.id}`
  return (
    <section
      aria-label="Possible duplicates"
      data-testid="duplicate-hints"
      className="mt-3 rounded-[var(--radius)] border border-amber-200 bg-amber-50/60 dark:border-amber-900/60 dark:bg-amber-950/20"
    >
      <button
        type="button"
        onClick={() => setChosen(!open)}
        aria-expanded={open}
        aria-controls={listId}
        className="flex w-full items-center gap-1.5 rounded-[var(--radius)] px-3 py-2 text-left text-xs font-semibold text-amber-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-amber-300"
      >
        <Icon name="copy" size={13} aria-hidden="true" />
        Possible duplicate{hints.hints.length > 1 ? `s (${hints.hints.length})` : ''}
        <span className="font-normal text-amber-800/80 dark:text-amber-300/80">
          · best match {Math.round(top.confidence * 100)}%{open ? ' — check before accepting' : ''}
        </span>
        <Icon name={open ? 'chevron-up' : 'chevron-down'} size={14} className="ml-auto" aria-hidden="true" />
      </button>
      {open && (
        <ul id={listId} className="space-y-2 px-3 pb-3">
          {hints.hints.map(hint => (
            <DuplicateCandidateCard key={hint.candidate_id} hint={hint} layout="row"
              onMerge={merge} onCompare={setCompare} onDismiss={hints.dismiss} />
          ))}
        </ul>
      )}
      {compare && (
        <DuplicateCompareDialog issue={issue} attachments={attachments} hint={compare}
          onClose={() => setCompare(null)} onMerge={merge} onDismiss={hints.dismiss} />
      )}
      {merging && (
        <DuplicateMergeDialog issue={issue} hint={merging} toast={toast} onClose={() => setMerging(null)}
          onMerged={(updated, original) => { setMerging(null); onMerged?.(updated, original) }} />
      )}
    </section>
  )
}
