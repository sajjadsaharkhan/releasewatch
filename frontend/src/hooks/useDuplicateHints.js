import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { issuesApi } from '../lib/api'
import { useApp } from './useApp'

/**
 * The stored possible duplicates of a New bug (slice 14), most similar first.
 * The API only returns hints that cleared the similarity threshold and hides
 * them unless the bug is New and Jev is on — `eligible` says whether any can
 * exist. A dismissal leaves at once and is undone only if the call fails.
 */
export function useDuplicateHints(issue, { onDismissed } = {}) {
  const { features } = useApp()
  const queryClient = useQueryClient()
  const [dismissed, setDismissed] = useState([])
  const eligible = !!issue && issue.status === 'new' && !!features?.jev_enabled

  const { data, isLoading } = useQuery({
    queryKey: ['duplicate-hints', issue?.id],
    queryFn: async () => (await issuesApi.duplicateHints(issue.id)).data?.hints ?? [],
    enabled: eligible,
    // Fresh on every mount: hints appear while the lead watches the queue.
    staleTime: 0,
  })

  const mark = (hint) => `${issue.id}:${hint.candidate_id}`
  const hints = (data ?? [])
    .filter((h) => !dismissed.includes(mark(h)))
    .sort((a, b) => b.confidence - a.confidence)

  async function dismiss(hint) {
    setDismissed((prev) => [...prev, mark(hint)])
    try {
      await issuesApi.dismissDuplicateHint(issue.id, hint.candidate_id)
      await queryClient.invalidateQueries({ queryKey: ['duplicate-hints', issue.id] })
      onDismissed?.(hint)
    } catch {
      setDismissed((prev) => prev.filter((k) => k !== mark(hint)))
    }
  }

  return { eligible, hints, isLoading: eligible && isLoading, dismiss }
}
