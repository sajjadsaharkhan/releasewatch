import React, { useState } from 'react'
import { Avatar } from '../ui/Avatar'
import { RoleBadge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Tabs } from '../ui/Tabs'
import { Icon } from '../ui/Icon'
import { DescriptionSection } from './DescriptionSection'
import { AttachmentsSection } from './AttachmentsSection'
import { RegressionTimelineSection } from './RegressionTimelineSection'
import { IssueTimeline } from './IssueTimeline'
import { relTime } from '../../lib/relTime'

export function IssueMainContent({
  issue,
  setLocalIssue,
  events,
  comments,
  teamUsers,
  availableLabels,
  currentUser,
  regressions,
  applyUpdate,
  addComment,
  updateComment,
  deleteComment,
  timelineHasMore,
  timelineLoadingMore,
  loadMoreTimeline,
  fetchAttachments,
}) {
  const [tab, setTab] = useState('activity')
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [editedTitle, setEditedTitle] = useState('')

  const reporter = issue.reporter_user

  const saveTitle = () => {
    const trimmed = editedTitle.trim()
    setIsEditingTitle(false)
    if (!trimmed || trimmed === issue.title) return
    applyUpdate({ title: trimmed }, 'Title updated')
  }

  return (
    <div className="overflow-y-auto px-7 py-6 max-w-[820px] mx-auto w-full">
      {isEditingTitle ? (
        <div className="flex items-start gap-2">
          <input
            autoFocus
            className="flex-1 text-[22px] font-semibold leading-snug text-zinc-900 dark:text-zinc-100 bg-transparent border border-border rounded-md px-2 py-0.5 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
            value={editedTitle}
            onChange={e => setEditedTitle(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') saveTitle()
              if (e.key === 'Escape') setIsEditingTitle(false)
            }}
          />
          <Button size="sm" onClick={saveTitle} className="mt-1 shrink-0">Save</Button>
          <Button variant="outline" size="sm" onClick={() => setIsEditingTitle(false)} className="mt-1 shrink-0">Cancel</Button>
        </div>
      ) : (
        <div className="flex items-start gap-2 group">
          <h1 className="text-[22px] font-semibold leading-snug text-zinc-900 dark:text-zinc-100">{issue.title}</h1>
          <button
            onClick={() => { setEditedTitle(issue.title); setIsEditingTitle(true) }}
            className="opacity-0 group-hover:opacity-100 transition-opacity mt-1.5 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300 p-1 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800 shrink-0"
            title="Edit title"
          >
            <Icon name="pencil" size={13} />
          </button>
        </div>
      )}

      <div className="mt-1.5 flex items-center gap-2 text-[12px] text-zinc-500 flex-wrap">
        <span>Filed by</span>
        <Avatar user={reporter} size={16} />
        <span className="text-zinc-700 dark:text-zinc-200">{reporter?.name}</span>
        {reporter?.role && <RoleBadge role={reporter.role} />}
        <span>·</span>
        <span>{relTime(issue.created_at)}</span>
        <span>·</span>
        <span className="font-mono">{issue.release_version || '—'}</span>
      </div>

      <div className="mt-4">
        <Tabs
          value={tab}
          onValueChange={setTab}
          options={[
            { value: 'activity', label: 'Activity', icon: 'activity', badge: events.length + comments.length },
            { value: 'evidence', label: 'Attachments', icon: 'paperclip', badge: issue.attachments?.length || null },
            { value: 'regression', label: 'Regression history', icon: 'refresh-ccw', badge: regressions.length || null },
          ]}
        />
      </div>

      <div className="mt-5">
        {tab === 'activity' && (
          <>
            <DescriptionSection
              issue={issue}
              onDescriptionUpdate={(desc) => applyUpdate({ description: desc }, 'Description saved')}
              onCurlUpdate={(curl) => applyUpdate({ curl_command: curl }, 'cURL saved')}
              onStepsUpdate={(steps) => applyUpdate({
                reproduction_steps: steps.map((s, i) => ({ step_order: i + 1, description: s }))
              }, 'Steps saved')}
            />
            <div className="my-6 border-t border-border" />
            <IssueTimeline
              events={events}
              comments={comments}
              issue={issue}
              users={teamUsers}
              labels={availableLabels}
              currentUser={currentUser}
              onAddComment={addComment}
              onUpdateComment={updateComment}
              onDeleteComment={deleteComment}
              hasMore={timelineHasMore}
              loadingMore={timelineLoadingMore}
              onLoadMore={loadMoreTimeline}
            />
          </>
        )}
        {tab === 'evidence' && (
          <AttachmentsSection
            issue={issue}
            onAttachmentsChange={(atts) => setLocalIssue(prev => ({ ...prev, attachments: atts }))}
            issueId={issue.id}
            onUploadComplete={() => fetchAttachments?.(issue.id)}
          />
        )}
        {tab === 'regression' && <RegressionTimelineSection regressions={regressions} />}
      </div>
    </div>
  )
}
