import React, { useState, useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { cn } from '../../lib/cn'
import { useApp } from '../../hooks/useApp'
import { useIssueDetail, canDeleteIssue } from '../../hooks/useIssueDetail'
import { IssueHeader } from './IssueHeader'
import { IssueMainContent } from './IssueMainContent'
import { IssueSidebar } from './IssueSidebar'

export function IssueDetail({ issue, onUpdate, onClose, onNavigate, adjacent }) {
  const { user: currentUser } = useApp()
  const location = useLocation()
  const { commentId } = location.state ?? {}
  const hashTarget = location.hash?.slice(1) // e.g. "event-42" or "comment-7"
  const scrolledRef = useRef(false)

  const {
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
    currentCycle,
    applyUpdate,
    addComment,
    updateComment,
    deleteComment,
    loadMoreTimeline,
    fetchAttachments,
    deleteIssue,
  } = useIssueDetail(issue, { onUpdate })

  const [pendingChange, setPendingChange] = useState(null)
  const [labelPickerOpen, setLabelPickerOpen] = useState(false)

  useEffect(() => {
    if (scrolledRef.current) return
    const targetId = commentId ? `comment-${commentId}` : hashTarget
    if (!targetId) return
    // Wait for the first page to arrive
    if (!comments.length && !events.length) return
    const el = document.getElementById(targetId)
    if (el) {
      scrolledRef.current = true
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('timeline-highlighted')
      return
    }
    // Element not in DOM yet — keep loading pages until it appears or we run out
    if (timelineHasMore && !timelineLoadingMore) {
      loadMoreTimeline()
    }
  }, [commentId, hashTarget, comments, events, timelineHasMore, timelineLoadingMore, loadMoreTimeline])

  function confirm({ title, body, confirmLabel = 'Confirm', tone = 'default', onConfirm }) {
    setPendingChange({ title, body, confirmLabel, tone, onConfirm })
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <IssueHeader
        issue={localIssue}
        onClose={onClose}
        onNavigate={onNavigate}
        adjacent={adjacent}
        canDelete={canDeleteIssue(currentUser, localIssue)}
        onDelete={() => confirm({
          title: 'Delete issue',
          body: 'This will permanently delete the issue and all its activity. This cannot be undone.',
          confirmLabel: 'Delete',
          tone: 'destructive',
          onConfirm: () => deleteIssue(onClose),
        })}
      />

      <div className="flex-1 min-h-0 grid grid-cols-[1fr_320px]">
        <IssueMainContent
          issue={localIssue}
          setLocalIssue={setLocalIssue}
          events={events}
          comments={comments}
          teamUsers={teamUsers}
          availableLabels={availableLabels}
          currentUser={currentUser}
          regressions={regressions}
          applyUpdate={applyUpdate}
          addComment={addComment}
          updateComment={updateComment}
          deleteComment={deleteComment}
          timelineHasMore={timelineHasMore}
          timelineLoadingMore={timelineLoadingMore}
          loadMoreTimeline={loadMoreTimeline}
          fetchAttachments={fetchAttachments}
        />

        <IssueSidebar
          issue={localIssue}
          currentCycle={currentCycle}
          teamUsers={teamUsers}
          availableLabels={availableLabels}
          availableReleases={availableReleases}
          applyUpdate={applyUpdate}
          onConfirm={confirm}
          onOpenLabelPicker={() => setLabelPickerOpen(true)}
        />
      </div>

      {/* Confirmation dialog */}
      <Dialog open={!!pendingChange} onClose={() => setPendingChange(null)} title={pendingChange?.title ?? ''} size="sm">
        <div className="px-5 pt-2 pb-5 space-y-4">
          <p className="text-sm text-zinc-600 dark:text-zinc-300">{pendingChange?.body}</p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setPendingChange(null)}>Cancel</Button>
            <Button
              size="sm"
              variant={pendingChange?.tone === 'destructive' ? 'destructive' : 'default'}
              onClick={() => { pendingChange?.onConfirm(); setPendingChange(null) }}
            >
              {pendingChange?.confirmLabel ?? 'Confirm'}
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Label picker dialog */}
      <Dialog open={labelPickerOpen} onClose={() => setLabelPickerOpen(false)} title="Add label" size="sm">
        <div className="p-4 space-y-1">
          {availableLabels.map(label => {
            const isAdded = (localIssue.labels || []).includes(label.name)
            return (
              <button
                key={label.id}
                onClick={() => {
                  if (!isAdded) {
                    applyUpdate({ labels: [...(localIssue.labels || []), label.name] })
                    setLabelPickerOpen(false)
                  }
                }}
                disabled={isAdded}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors',
                  'border border-border',
                  'hover:bg-zinc-50 dark:hover:bg-zinc-900',
                  isAdded && 'opacity-50 cursor-not-allowed hover:bg-transparent'
                )}
              >
                <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: label.color }} />
                <span className="text-sm font-medium text-zinc-700 dark:text-zinc-200">{label.name}</span>
                {isAdded && <span className="ml-auto text-xs text-zinc-400">Added</span>}
              </button>
            )
          })}
          {availableLabels.length === 0 && (
            <p className="text-sm text-zinc-400 text-center py-2">No labels found</p>
          )}
        </div>
      </Dialog>
    </div>
  )
}
