import { useState, useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { issuesApi, teamApi, timelineApi, labelsApi, releasesApi } from '../lib/api'
import { useApp } from './useApp'
import { useToast } from './useToast'

function normalizeTimelineItems(apiItems) {
  const events = []
  const comments = []
  for (const e of apiItems) {
    if (e.event_type === 'comment') {
      comments.push({
        id: e.id,
        actor: e.actor_id,
        actor_user: e.actor_user,
        body: e.body,
        createdAt: e.created_at,
        isInternal: e.is_internal,
        mentionedUsers: e.mentioned_user_ids || [],
        editedAt: e.edited_at,
      })
    } else {
      events.push({
        id: e.id,
        type: e.event_type,
        actor: e.actor_id,
        actor_user: e.actor_user,
        timestamp: e.created_at,
        meta: e.meta,
        from: e.meta?.from,
        to: e.meta?.to,
        detail: e.meta?.assignee_id,
      })
    }
  }
  return { events, comments }
}

export function useIssueDetail(initialIssue, { onUpdate } = {}) {
  const queryClient = useQueryClient()
  const { user: currentUser } = useApp()
  const { toast } = useToast()

  const [localIssue, setLocalIssue] = useState(initialIssue)
  const issueId = localIssue?.id

  // Timeline — TanStack Query owns fetching; invalidateQueries triggers re-fetch after mutations
  const { data: timelineData } = useQuery({
    queryKey: ['timeline', issueId],
    queryFn: () => timelineApi.list(issueId, { page: 1, size: 50 }).then(r => r.data),
    enabled: !!issueId,
    staleTime: 0,
  })

  // Extra pages loaded via loadMoreTimeline — reset when base query refreshes
  const [extraItems, setExtraItems] = useState([])
  const [timelinePage, setTimelinePage] = useState(1)
  const [timelineLoadingMore, setTimelineLoadingMore] = useState(false)
  const timelineLoadingRef = useRef(false)
  const prevTimelineDataRef = useRef(null)

  useEffect(() => {
    if (timelineData !== prevTimelineDataRef.current) {
      prevTimelineDataRef.current = timelineData
      setExtraItems([])
      setTimelinePage(1)
    }
  }, [timelineData])

  const baseItems = timelineData?.items || []
  const allRawItems = [...baseItems, ...extraItems]
  const { events, comments } = normalizeTimelineItems(allRawItems)
  const timelineHasMore = (timelineData?.total ?? 0) > allRawItems.length

  // Reference data — long staleTime since these change rarely
  const { data: teamUsers = [] } = useQuery({
    queryKey: ['team'],
    queryFn: () => teamApi.list().then(r => r.data || []),
    staleTime: 5 * 60 * 1000,
  })

  const { data: availableLabels = [] } = useQuery({
    queryKey: ['labels'],
    queryFn: () => labelsApi.list().then(r => r.data || []),
    staleTime: 5 * 60 * 1000,
  })

  const { data: availableReleases = [] } = useQuery({
    queryKey: ['releases', initialIssue?.project_id],
    queryFn: () =>
      releasesApi.list({ project_id: initialIssue.project_id }).then(r => r.data?.releases || r.data || []),
    enabled: !!initialIssue?.project_id,
    staleTime: 5 * 60 * 1000,
  })

  const loadMoreTimeline = async () => {
    if (!issueId || timelineLoadingRef.current) return
    timelineLoadingRef.current = true
    setTimelineLoadingMore(true)
    const nextPage = timelinePage + 1
    try {
      const res = await timelineApi.list(issueId, { page: nextPage, size: 50 })
      setExtraItems(prev => [...prev, ...(res.data?.items || [])])
      setTimelinePage(nextPage)
    } catch (err) {
      console.error('[useIssueDetail] Load more timeline failed:', err)
    } finally {
      timelineLoadingRef.current = false
      setTimelineLoadingMore(false)
    }
  }

  const applyUpdate = async (patch, successMsg) => {
    let updatedIssue
    try {
      const res = await issuesApi.update(issueId, patch)
      updatedIssue = res.data
      setLocalIssue(updatedIssue)
      onUpdate?.(updatedIssue)
      if (successMsg) toast.success(successMsg)
    } catch {
      toast.error('Failed to update issue')
      return
    }
    // Fetch fresh timeline and write directly to cache — setQueryData bypasses
    // observer-state checks that invalidateQueries depends on, so it works even
    // when a dialog state change is batched in the same event (e.g. release blocker confirm).
    try {
      const tlRes = await timelineApi.list(updatedIssue.id, { page: 1, size: 50 })
      queryClient.setQueryData(['timeline', updatedIssue.id], tlRes.data)
    } catch (err) {
      console.error('[applyUpdate] Timeline refresh failed:', err)
    }
  }

  const addComment = async (body, isInternal, mentionedUserIds) => {
    try {
      const res = await timelineApi.addComment(issueId, {
        body,
        is_internal: isInternal,
        mentioned_user_ids: mentionedUserIds || [],
      })
      const newItem = { ...res.data, actor_user: res.data.actor_user ?? currentUser }
      queryClient.setQueryData(['timeline', issueId], (old) => {
        if (!old) return { items: [newItem], total: 1, page: 1, size: 50 }
        return { ...old, items: [...old.items, newItem], total: (old.total || 0) + 1 }
      })
      toast.success('Comment added')
    } catch {
      toast.error('Failed to add comment')
    }
  }

  const updateComment = async (commentId, body, isInternal, mentionedUserIds, editedAt) => {
    try {
      await timelineApi.updateComment(issueId, commentId, { body })
      const patchItem = (item) =>
        item.id === commentId
          ? { ...item, body, is_internal: isInternal, mentioned_user_ids: mentionedUserIds || [], edited_at: editedAt }
          : item
      queryClient.setQueryData(['timeline', issueId], (old) => {
        if (!old) return old
        return { ...old, items: old.items.map(patchItem) }
      })
      setExtraItems(prev => prev.map(patchItem))
      toast.success('Comment updated')
    } catch {
      toast.error('Failed to update comment')
    }
  }

  const deleteComment = async (commentId) => {
    try {
      await timelineApi.deleteComment(issueId, commentId)
      const filterItems = (items) => items.filter(item => item.id !== commentId)
      queryClient.setQueryData(['timeline', issueId], (old) => {
        if (!old) return old
        return { ...old, items: filterItems(old.items), total: Math.max(0, (old.total || 0) - 1) }
      })
      setExtraItems(prev => filterItems(prev))
      toast.success('Comment deleted')
    } catch {
      toast.error('Failed to delete comment')
    }
  }

  return {
    localIssue,
    setLocalIssue,
    events,
    comments,
    timelineHasMore,
    timelineLoadingMore,
    teamUsers,
    availableLabels,
    availableReleases,
    applyUpdate,
    addComment,
    updateComment,
    deleteComment,
    loadMoreTimeline,
  }
}
