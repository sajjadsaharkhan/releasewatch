import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { issuesApi, teamApi, timelineApi, labelsApi, releasesApi, attachmentsApi, regressionsApi, cyclesApi } from '../lib/api'
import { useApp } from './useApp'
import { useToast } from './useToast'

export function canDeleteIssue(currentUser, issue) {
  if (!currentUser || !issue) return false
  return (
    currentUser.role === 'admin' ||
    currentUser.role === 'cto' ||
    currentUser.id === issue.reporter
  )
}

function normalizeAttachment(att) {
  return {
    ...att,
    name: att.file_name,
    size: att.file_size_bytes,
    createdAt: att.created_at,
    type: att.mime_type?.startsWith('image/') ? 'image' : att.mime_type?.startsWith('video/') ? 'video' : 'file',
    url: att.public_url || att.download_url,
    uploading: false,
  }
}

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
  const { user: currentUser } = useApp()
  const { toast } = useToast()

  const [localIssue, setLocalIssue] = useState(initialIssue)
  const issueId = localIssue?.id

  // ── Timeline — managed in local state, fetched directly ──────────────────
  const [timelineBaseItems, setTimelineBaseItems] = useState([])
  const [timelineTotal, setTimelineTotal] = useState(0)
  const [extraItems, setExtraItems] = useState([])
  const [timelinePage, setTimelinePage] = useState(1)
  const [timelineLoadingMore, setTimelineLoadingMore] = useState(false)
  const timelineLoadingRef = useRef(false)

  // Ref so async callbacks always see the latest issueId without stale closure
  const issueIdRef = useRef(issueId)
  issueIdRef.current = issueId

  const fetchTimeline = useCallback(async (id) => {
    if (!id) return
    try {
      const res = await timelineApi.list(id, { page: 1, size: 50 })
      setTimelineBaseItems(res.data?.items || [])
      setTimelineTotal(res.data?.total || 0)
      setExtraItems([])
      setTimelinePage(1)
    } catch (err) {
      console.error('[useIssueDetail] Timeline fetch failed:', err)
    }
  }, [])

  useEffect(() => {
    fetchTimeline(issueId)
  }, [issueId, fetchTimeline])

  const fetchAttachments = useCallback(async (id) => {
    if (!id) return
    try {
      const res = await attachmentsApi.list(id)
      const normalized = (res.data || []).map(normalizeAttachment)
      setLocalIssue(prev => ({ ...prev, attachments: normalized }))
    } catch (err) {
      console.error('[useIssueDetail] Attachments fetch failed:', err)
    }
  }, [])

  useEffect(() => {
    fetchAttachments(issueId)
  }, [issueId, fetchAttachments])

  const allRawItems = [...timelineBaseItems, ...extraItems]
  const { events, comments } = normalizeTimelineItems(allRawItems)
  const timelineHasMore = timelineTotal > allRawItems.length

  // ── Regression history ────────────────────────────────────────────────────
  const [regressions, setRegressions] = useState([])

  const fetchRegressions = useCallback(async (id) => {
    if (!id) return
    try {
      const res = await regressionsApi.list(id)
      setRegressions(res.data || [])
    } catch (err) {
      console.error('[useIssueDetail] Regressions fetch failed:', err)
    }
  }, [])

  useEffect(() => {
    fetchRegressions(issueId)
  }, [issueId, fetchRegressions])

  // ── Issue cycles ──────────────────────────────────────────────────────────
  const [cycles, setCycles] = useState([])

  const fetchCycles = useCallback(async (id) => {
    if (!id) return
    try {
      const res = await cyclesApi.list(id)
      setCycles(res.data || [])
    } catch (err) {
      console.error('[useIssueDetail] Cycles fetch failed:', err)
    }
  }, [])

  useEffect(() => {
    fetchCycles(issueId)
  }, [issueId, fetchCycles])

  // ── Reference data ────────────────────────────────────────────────────────
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

  // ── Mutations ─────────────────────────────────────────────────────────────

  const loadMoreTimeline = async () => {
    const id = issueIdRef.current
    if (!id || timelineLoadingRef.current) return
    timelineLoadingRef.current = true
    setTimelineLoadingMore(true)
    const nextPage = timelinePage + 1
    try {
      const res = await timelineApi.list(id, { page: nextPage, size: 50 })
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
    const id = issueIdRef.current
    try {
      const res = await issuesApi.update(id, patch)
      const updatedIssue = res.data
      setLocalIssue(updatedIssue)
      onUpdate?.(updatedIssue)
      if (successMsg) toast({ title: successMsg })
    } catch {
      toast({ title: 'Failed to update issue' })
      return
    }
    await fetchTimeline(id)
    if (patch.status === 'regression') {
      await fetchRegressions(id)
    }
    if (['regression', 'triaged', 'fixed', 'verified'].includes(patch.status)) {
      await fetchCycles(id)
    }
  }

  const addComment = async (body, isInternal, mentionedUserIds) => {
    const id = issueIdRef.current
    try {
      const res = await timelineApi.addComment(id, {
        body,
        is_internal: isInternal,
        mentioned_user_ids: mentionedUserIds || [],
      })
      const newItem = { ...res.data, actor_user: res.data.actor_user ?? currentUser }
      setTimelineBaseItems(prev => [...prev, newItem])
      setTimelineTotal(prev => prev + 1)
      toast({ title: 'Comment added' })
    } catch {
      toast({ title: 'Failed to add comment' })
    }
  }

  const updateComment = async (commentId, body, isInternal, mentionedUserIds, editedAt) => {
    const id = issueIdRef.current
    try {
      await timelineApi.updateComment(id, commentId, { body })
      const patchItem = (item) =>
        item.id === commentId
          ? { ...item, body, is_internal: isInternal, mentioned_user_ids: mentionedUserIds || [], edited_at: editedAt }
          : item
      setTimelineBaseItems(prev => prev.map(patchItem))
      setExtraItems(prev => prev.map(patchItem))
      toast({ title: 'Comment updated' })
    } catch {
      toast({ title: 'Failed to update comment' })
    }
  }

  const deleteComment = async (commentId) => {
    const id = issueIdRef.current
    try {
      await timelineApi.deleteComment(id, commentId)
      const filterItems = (items) => items.filter(item => item.id !== commentId)
      setTimelineBaseItems(prev => filterItems(prev))
      setExtraItems(prev => filterItems(prev))
      setTimelineTotal(prev => Math.max(0, prev - 1))
      toast({ title: 'Comment deleted' })
    } catch {
      toast({ title: 'Failed to delete comment' })
    }
  }

  const currentCycle = cycles.length > 0 ? cycles[cycles.length - 1] : null

  const deleteIssue = async (onDeleted) => {
    const id = issueIdRef.current
    try {
      await issuesApi.remove(id)
      toast({ title: 'Issue deleted' })
      onDeleted?.()
    } catch {
      toast({ title: 'Failed to delete issue' })
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
    regressions,
    cycles,
    currentCycle,
    applyUpdate,
    addComment,
    updateComment,
    deleteComment,
    loadMoreTimeline,
    fetchAttachments,
    deleteIssue,
  }
}
