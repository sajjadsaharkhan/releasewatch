import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { issuesApi, teamApi, timelineApi, labelsApi, projectsApi, attachmentsApi, cyclesApi } from '../lib/api'
import { useApp } from './useApp'
import { useToast } from './useToast'
import { downloadIssueMarkdown } from '../lib/issueMarkdown'

export function canDeleteIssue(currentUser, issue) {
  if (!currentUser || !issue) return false
  return (
    currentUser.role === 'admin' ||
    currentUser.role === 'cto' ||
    currentUser.id === issue.reporter_id ||
    (issue.project_triage_lead_id != null && currentUser.id === issue.project_triage_lead_id)
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
    // A recurrence (slice 07) is a public comment carrying a new occurrence's
    // details — rendered as a comment card, marked as a recurrence.
    if (e.event_type === 'comment' || e.event_type === 'recurrence') {
      comments.push({
        isRecurrence: e.event_type === 'recurrence',
        id: e.id,
        actor: e.actor_id,
        actor_user: e.actor_user,
        body: e.body,
        createdAt: e.created_at,
        isInternal: e.is_internal,
        mentionedUsers: e.mentioned_user_ids || [],
        editedAt: e.edited_at,
        reactions: e.reactions || [],
        meta: e.meta,
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
        body: e.body ?? null,
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

  // ── Issue cycles (08a) — one pass of work each; returns start the next ─────
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

  const { data: assignableUsers = [] } = useQuery({
    queryKey: ['team', 'assignable'],
    queryFn: () => teamApi.listAssignable().then(r => r.data || []),
    staleTime: 5 * 60 * 1000,
  })

  const { data: availableLabels = [] } = useQuery({
    queryKey: ['labels'],
    queryFn: () => labelsApi.list().then(r => r.data || []),
    staleTime: 5 * 60 * 1000,
  })

  const { data: availableProjects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list().then(r => r.data?.projects || r.data || []),
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

  // Resolves true when the PATCH succeeded (the Move dialog closes on it).
  const applyUpdate = async (patch, successMsg) => {
    const id = issueIdRef.current
    try {
      const res = await issuesApi.update(id, patch)
      const updatedIssue = res.data
      // The update response carries no attachments — keep the ones we fetched
      // separately so they survive a status/field change.
      setLocalIssue(prev => ({
        ...updatedIssue,
        attachments: updatedIssue.attachments ?? prev?.attachments ?? [],
      }))
      onUpdate?.(updatedIssue)
      if (successMsg) toast({ title: successMsg })
    } catch (err) {
      toast({ title: err.response?.data?.detail || 'Failed to update issue' })
      return false
    }
    await fetchTimeline(id)
    // Status, assignee and placement all touch the cycles (08a).
    if (patch.status || 'assignee_id' in patch || 'release_id' in patch) {
      await fetchCycles(id)
    }
    return true
  }

  // After a Reject (09a): the item is Rejected with a new cycle and a reason
  // comment on the timeline.
  const sentBack = async (updatedIssue) => {
    const id = issueIdRef.current
    setLocalIssue(prev => ({
      ...updatedIssue,
      attachments: updatedIssue.attachments ?? prev?.attachments ?? [],
    }))
    onUpdate?.(updatedIssue)
    await fetchTimeline(id)
    await fetchCycles(id)
  }

  // After Report recurrence (slice 07): new count on the item, new entry on the timeline.
  const recurrenceReported = async (updatedIssue) => {
    setLocalIssue(prev => ({
      ...updatedIssue,
      attachments: updatedIssue.attachments ?? prev?.attachments ?? [],
    }))
    onUpdate?.(updatedIssue)
    await fetchTimeline(issueIdRef.current)
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
      // A reporter or Support reply on a Needs info item sends it back to New
      // server-side (FR-19) — pick up the new status and its timeline event.
      if (localIssue?.status === 'needs_info' && !isInternal) {
        issuesApi.get(id).then(fresh => {
          setLocalIssue(prev => ({ ...prev, ...fresh.data }))
          onUpdate?.(fresh.data)
          fetchTimeline(id)
        }).catch(() => {})
      }
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

  // Apply a reaction toggle to one raw timeline item, returning the new
  // `reactions` array. Mirrors the backend summary shape so the optimistic
  // state and the server response are interchangeable.
  //
  // Reactions are mutually exclusive: adding one must also withdraw whatever
  // the user was holding, or the UI briefly shows two active pills before the
  // server response corrects it.
  const applyReactionToggle = (item, emojiKey) => {
    const existing = item.reactions || []
    const uid = currentUser?.id
    const sameUser = (id) => String(id) === String(uid)

    // Withdraw the user from every summary, dropping any that empty out.
    const withdrawn = existing.flatMap((r) => {
      if (!r.reacted_by_me) return [r]
      if (r.count <= 1) return []
      return [{
        ...r,
        count: r.count - 1,
        reacted_by_me: false,
        user_ids: (r.user_ids || []).filter(id => !sameUser(id)),
      }]
    })

    // Clicking the emoji you already hold just removes it.
    const wasMine = existing.some(r => r.emoji_key === emojiKey && r.reacted_by_me)
    if (wasMine) return withdrawn

    const target = withdrawn.find(r => r.emoji_key === emojiKey)
    if (target) {
      return withdrawn.map(r =>
        r.emoji_key === emojiKey
          ? { ...r, count: r.count + 1, reacted_by_me: true, user_ids: [...(r.user_ids || []), uid] }
          : r
      )
    }
    return [...withdrawn, { emoji_key: emojiKey, count: 1, user_ids: [uid], reacted_by_me: true }]
  }

  const toggleReaction = async (commentId, emojiKey) => {
    const id = issueIdRef.current
    const all = [...timelineBaseItems, ...extraItems]
    const target = all.find(item => item.id === commentId)
    if (!target) return

    const wasReacted = !!(target.reactions || []).find(
      r => r.emoji_key === emojiKey && r.reacted_by_me
    )
    const prevReactions = target.reactions || []

    // Optimistic — a reaction has to feel instant.
    const patch = (item) =>
      item.id === commentId ? { ...item, reactions: applyReactionToggle(item, emojiKey) } : item
    setTimelineBaseItems(prev => prev.map(patch))
    setExtraItems(prev => prev.map(patch))

    try {
      const res = wasReacted
        ? await timelineApi.removeReaction(id, commentId, emojiKey)
        : await timelineApi.addReaction(id, commentId, emojiKey)
      // Reconcile against the server's authoritative summary.
      const server = res?.data?.reactions
      if (server) {
        const sync = (item) => (item.id === commentId ? { ...item, reactions: server } : item)
        setTimelineBaseItems(prev => prev.map(sync))
        setExtraItems(prev => prev.map(sync))
      }
    } catch {
      const rollback = (item) =>
        item.id === commentId ? { ...item, reactions: prevReactions } : item
      setTimelineBaseItems(prev => prev.map(rollback))
      setExtraItems(prev => prev.map(rollback))
      toast({ title: 'Failed to update reaction' })
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

  const exportMarkdown = useCallback(() => {
    downloadIssueMarkdown(localIssue, comments)
  }, [localIssue, comments])

  return {
    localIssue,
    setLocalIssue,
    events,
    comments,
    timelineHasMore,
    timelineLoadingMore,
    teamUsers,
    assignableUsers,
    availableLabels,
    availableProjects,
    cycles,
    cycles,
    currentCycle,
    applyUpdate,
    sentBack,
    recurrenceReported,
    addComment,
    updateComment,
    deleteComment,
    toggleReaction,
    loadMoreTimeline,
    fetchAttachments,
    deleteIssue,
    exportMarkdown,
  }
}
