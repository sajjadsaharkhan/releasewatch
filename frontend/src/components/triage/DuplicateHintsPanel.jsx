import React, { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '../ui/Button'
import { StatusBadge, TypeIcon } from '../ui'
import { Icon } from '../ui/Icon'
import { issuesApi } from '../../lib/api'
import { useApp } from '../../hooks/useApp'
import { issueSlug } from '../../lib/issueSlug'
import { STATUS } from '../../lib/constants'

// What "Merge into this" will do to the candidate, per BR-49 — the sentence
// the API's merge_effect renders (FR-S13, AC-S11). The backend computes the
// effect with the merge's own reason function, so this never disagrees with
// what actually happens.
function mergeEffectSentence(hint) {
  const label = STATUS[hint.candidate.status]?.label ?? hint.candidate.status
  switch (hint.merge_effect) {
    case 'stays_cancelled':
      return 'Stays Cancelled'
    case 'returns_release_qa':
      return 'Done → back to To do (release QA)'
    case 'returns_production':
      return 'Done → back to To do (production)'
    default:
      return `Stays ${label}`
  }
}

/**
 * Stored possible duplicates of a New bug (slice 14, FR-S12–S15): each hint
 * names the candidate and says what merging will do. **Merge into this**
 * opens the Duplicate outcome with the candidate preselected (the parent
 * wires that); **Not a duplicate** dismisses the pair for good (BR-S12).
 * Shown in the triage detail pane and, where the item allows it, on the item
 * page — Support never sees it (FR-S13; the page gates on allowed_actions,
 * never the role).
 */
export function DuplicateHintsPanel({ issue, onMerge, onDismissed }) {
  const { features } = useApp()
  const queryClient = useQueryClient()
  const [dismissed, setDismissed] = useState([])
  const eligible = issue.status === 'new' && features?.jev_enabled

  const { data: hints = [] } = useQuery({
    queryKey: ['duplicate-hints', issue.id],
    queryFn: async () => (await issuesApi.duplicateHints(issue.id)).data?.hints ?? [],
    enabled: eligible,
    // Fresh on every mount: hints appear while the lead watches the queue.
    staleTime: 0,
  })
  // A dismissal leaves immediately and is undone only if the call fails.
  const shown = hints.filter((h) => !dismissed.includes(h.candidate_id))

  if (!eligible || shown.length === 0) return null

  async function dismiss(hint) {
    setDismissed((prev) => [...prev, hint.candidate_id])
    try {
      await issuesApi.dismissDuplicateHint(issue.id, hint.candidate_id)
      await queryClient.invalidateQueries({ queryKey: ['duplicate-hints', issue.id] })
      onDismissed?.(hint)
    } catch {
      setDismissed((prev) => prev.filter((id) => id !== hint.candidate_id))
    }
  }

  return (
    <section
      aria-label="Possible duplicates"
      data-testid="duplicate-hints"
      className="mt-3 rounded-[var(--radius)] border border-amber-200 bg-amber-50/60 p-3 dark:border-amber-900/60 dark:bg-amber-950/20"
    >
      <h3 className="flex items-center gap-1.5 text-xs font-medium text-amber-800 dark:text-amber-300">
        <Icon name="copy" size={13} aria-hidden />
        Possible duplicate{shown.length > 1 ? `s (${shown.length})` : ''}
      </h3>
      <ul className="mt-2 space-y-2">
        {shown.map((hint) => (
          <li
            key={hint.candidate_id}
            className="rounded-md border border-border/60 bg-background px-2.5 py-2"
          >
            <div className="flex items-start gap-2">
              <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <TypeIcon type={hint.candidate.type} aria-hidden />
                <span className="font-mono">{hint.candidate.key}</span>
              </span>
              <span className="min-w-0 flex-1">
                <a
                  href={`/issue/${issueSlug(hint.candidate)}`}
                  target="_blank"
                  rel="noreferrer"
                  className="block truncate text-[13px] text-foreground underline-offset-2 hover:underline"
                >
                  {hint.candidate.title}
                </a>
                <span className="mt-0.5 flex items-center gap-1.5">
                  <StatusBadge status={hint.candidate.status} />
                  <span className="text-[11px] text-muted-foreground">
                    {mergeEffectSentence(hint)}
                  </span>
                </span>
              </span>
            </div>
            <div className="mt-1.5 flex items-center gap-2">
              <Button size="sm" onClick={() => onMerge?.(hint.candidate)}>
                Merge into this
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-muted-foreground"
                onClick={() => dismiss(hint)}
              >
                Not a duplicate
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
