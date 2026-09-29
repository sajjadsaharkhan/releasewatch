import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { backlogCategoriesApi } from '../lib/api'

const key = (projectId) => ['backlog-categories', projectId]

/**
 * A project's backlog categories, Default first (2026-09-28). Shared by every
 * picker (New task, triage Accept, item sidebar, backlog bulk bar) through the
 * react-query cache; Settings calls `useInvalidateBacklogCategories()` after an
 * edit so they all refresh. Returns `{ categories, canManage, isLoading }`.
 */
export function useBacklogCategories(projectId) {
  const query = useQuery({
    queryKey: key(projectId),
    queryFn: () => backlogCategoriesApi.list(projectId).then((res) => res.data),
    enabled: !!projectId,
    staleTime: 60_000,
  })
  return {
    categories: query.data?.categories ?? [],
    canManage: !!query.data?.can_manage,
    isLoading: query.isLoading,
  }
}

export function useInvalidateBacklogCategories() {
  const client = useQueryClient()
  return useCallback(
    (projectId) => client.invalidateQueries({ queryKey: projectId ? key(projectId) : ['backlog-categories'] }),
    [client],
  )
}
