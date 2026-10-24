import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { whatsNewApi } from '../lib/api'
import { useApp } from './useApp'

const KEY = ['whats-new']

/**
 * What's new for the signed-in person (TASK-575): their team's notes, newest
 * first, and `show` — the note whose modal opens now. Notes only change with a
 * deploy, so it's fetched once per session. `markSeen(ids)` records notes as
 * seen and updates the cache at once, so nothing reopens while the request runs.
 */
export function useWhatsNew() {
  const { isAuthenticated } = useApp()
  const client = useQueryClient()
  const query = useQuery({
    queryKey: KEY,
    queryFn: () => whatsNewApi.list().then((res) => res.data),
    enabled: isAuthenticated,
    staleTime: Infinity,
  })
  const seen = useMutation({
    mutationFn: (ids) => whatsNewApi.markSeen(ids),
    onMutate: (ids) => {
      client.setQueryData(KEY, (data) =>
        data && {
          notes: data.notes.map((n) => (ids.includes(n.id) ? { ...n, seen: true } : n)),
          show: ids.includes(data.show) ? null : data.show,
        },
      )
    },
  })
  const notes = query.data?.notes ?? []
  return {
    notes,
    show: query.data?.show ?? null,
    hasUnseen: notes.some((n) => !n.seen),
    markSeen: (ids) => ids.length && seen.mutate(ids),
  }
}
