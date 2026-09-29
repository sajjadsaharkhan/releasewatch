import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { projectsApi, releasesApi } from '../lib/api'
import { isOpenRelease } from '../lib/constants'

const key = (projectId) => ['containers', projectId]

/**
 * A project's containers (08a): its Stream and its Releases. Shared by every
 * placement picker through the react-query cache. Returns
 * `{ streamId, releases, openReleases, isLoading }` — `releases` never holds
 * the Stream; `openReleases` are the ones that still take items.
 */
export function useContainers(projectId) {
  const query = useQuery({
    queryKey: key(projectId),
    queryFn: async () => {
      const [project, releases] = await Promise.all([
        projectsApi.get(projectId).then((res) => res.data),
        releasesApi.list({ project_id: projectId }).then((res) => res.data?.releases ?? []),
      ])
      return { streamId: project?.stream_id ?? null, releases }
    },
    enabled: !!projectId,
    staleTime: 30_000,
  })
  const releases = query.data?.releases ?? []
  return {
    streamId: query.data?.streamId ?? null,
    releases,
    openReleases: releases.filter(isOpenRelease),
    isLoading: query.isLoading,
  }
}

export function useInvalidateContainers() {
  const client = useQueryClient()
  return useCallback(
    (projectId) => client.invalidateQueries({ queryKey: projectId ? key(projectId) : ['containers'] }),
    [client],
  )
}
