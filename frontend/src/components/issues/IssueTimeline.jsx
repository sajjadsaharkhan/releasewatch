import React, { useState } from 'react'
import { MessageSquare, MoreVertical, Trash2, Edit3 } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'
import { StatusBadge, RoleBadge } from '../ui/Badge'
import { Dropdown, DropdownItem, DropdownSep } from '../ui/Dropdown'
import { userById } from '../../data/mockData'
import { relTime, fullTime, formatEventTime } from '../../lib/relTime'
import { renderMarkdown } from '../../lib/markdown'
import { CommentComposer } from './CommentComposer'

// Current user ID - in a real app this would come from auth context
const CURRENT_USER_ID = 'u-1'

const EVENT_STYLES = {
  filed: { dot: 'bg-blue-500', label: 'filed this issue' },
  status_changed: { dot: 'bg-zinc-400', label: (detail) => `changed status to ${detail}` },
  assigned: { dot: 'bg-violet-500', label: (detail) => `assigned to ${userById(detail)?.name ?? detail}` },
  fixed: { dot: 'bg-green-500', label: 'marked as fixed' },
  regression: { dot: 'bg-red-500', label: 'marked as regression' },
  verified: { dot: 'bg-teal-500', label: 'verified the fix' },
  reopened: { dot: 'bg-amber-500', label: 'reopened this issue' },
  comment: { dot: 'bg-zinc-400', label: 'commented' },
}

const EVENT_ICONS = {
  filed: 'file-plus',
  assigned: 'user-plus',
  severity_changed: 'arrow-up-down',
  status_changed: 'git-pull-request',
  label_added: 'tag',
  label_removed: 'tag',
  fixed: 'check',
  verified: 'shield-check',
  regression: 'refresh-ccw',
  blocker_flagged: 'octagon-alert',
  duplicate_linked: 'copy',
}

function EventDot({ type }) {
  const style = EVENT_STYLES[type] ?? { dot: 'bg-zinc-300' }
  const iconName = EVENT_ICONS[type] ?? 'circle'
  return (
    <span className={cn('absolute left-[8px] top-2.5 h-4 w-4 rounded-full ring-4 ring-white dark:ring-zinc-950 flex items-center justify-center text-white', style.dot)}>
      <Icon name={iconName} size={9} strokeWidth={2.6} />
    </span>
  )
}

function getLabel(event) {
  const style = EVENT_STYLES[event.type]
  if (!style) return event.type

  // Handle status_changed with from/to for proper display like prototype
  if (event.type === 'status_changed' && event.from && event.to) {
    return (
      <>
        changed status <StatusBadge status={event.from} size="sm" />
        <Icon name="arrow-right" size={11} className="inline mx-0.5 text-zinc-400" />
        <StatusBadge status={event.to} size="sm" />
      </>
    )
  }

  if (typeof style.label === 'function') return style.label(event.detail)
  return style.label
}

export function IssueTimeline({ events = [], comments = [], issue, onAddComment, onUpdateComment, onDeleteComment }) {
  const [editingCommentId, setEditingCommentId] = useState(null)

  // Merge events and comments, sort by time
  const items = [
    ...events.map((e) => ({ ...e, _kind: 'event' })),
    ...comments.map((c) => ({ ...c, _kind: 'comment', type: 'comment' })),
  ].sort((a, b) => new Date(a.timestamp ?? a.createdAt) - new Date(b.timestamp ?? b.createdAt))

  const handleSubmitComment = (body, isInternal) => {
    onAddComment?.(body, isInternal)
  }

  const handleEditComment = (body, isInternal) => {
    onUpdateComment?.(editingCommentId, body, isInternal, new Date().toISOString())
    setEditingCommentId(null)
  }

  const handleDeleteComment = (commentId) => {
    onDeleteComment?.(commentId)
  }

  const isOwnComment = (comment) => {
    const authorId = comment.actor ?? comment.author
    return authorId === CURRENT_USER_ID
  }

  return (
    <div>
      {/* Timeline header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 flex items-center gap-2">
          <MessageSquare size={14} /> Activity & comments
        </h3>
        <span className="text-xs text-zinc-400 dark:text-zinc-500">{items.length} {items.length === 1 ? 'item' : 'items'}</span>
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">No activity yet.</p>
      ) : (
        <ol className="relative space-y-0.5 mb-6 before:content-[''] before:absolute before:left-[15px] before:top-0 before:bottom-0 before:w-px before:bg-zinc-200 dark:before:bg-zinc-800">
          {items.map((item, idx) => {
            const isComment = item._kind === 'comment'
            const actorId = item.actor ?? item.author
            const actor = userById(actorId)
            const time = item.timestamp ?? item.createdAt

            if (isComment) {
              const isEditing = editingCommentId === item.id
              const ownComment = isOwnComment(item)

              return (
                <li key={item.id ?? idx} className="relative pl-10 pr-2 py-2">
                  <div className="absolute left-0 top-2">
                    <Avatar user={actor} size={30} />
                  </div>

                  {isEditing ? (
                    <CommentComposer
                      initialValue={item.body}
                      initialInternal={item.isInternal}
                      mode="edit"
                      onSubmit={handleEditComment}
                      onCancelEdit={() => setEditingCommentId(null)}
                    />
                  ) : (
                    <div className={cn(
                      'rounded-lg border bg-white dark:bg-zinc-950 px-3.5 py-2.5 relative group',
                      item.isInternal
                        ? 'border-amber-200 bg-amber-50/60 dark:bg-amber-950/20 dark:border-amber-900/50'
                        : 'border-zinc-200 dark:border-zinc-800',
                    )}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[13px] font-semibold text-zinc-900 dark:text-zinc-100">{actor?.name ?? actorId}</span>
                        <RoleBadge role={actor?.role} />
                        {item.isInternal && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-700 dark:text-amber-300">
                            <Icon name="lock" size={10} /> Internal note
                          </span>
                        )}
                        <div className="ml-auto flex items-center gap-2">
                          <span className="text-[11px] text-zinc-400 dark:text-zinc-500" title={fullTime(time)}>
                            {formatEventTime(time)}
                            {item.editedAt && (
                              <span className="ml-1 text-zinc-400 dark:text-zinc-500 italic">(edited)</span>
                            )}
                          </span>
                          {ownComment && (
                            <Dropdown
                              align="end"
                              width={140}
                              trigger={
                                <button className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 p-0.5 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800">
                                  <MoreVertical size={13} />
                                </button>
                              }
                            >
                              {({ close }) => (
                                <>
                                  <DropdownItem onClick={() => { setEditingCommentId(item.id); close(); }}>
                                    <Edit3 size={12} /> Edit
                                  </DropdownItem>
                                  <DropdownSep />
                                  <DropdownItem destructive onClick={() => { handleDeleteComment(item.id); close(); }}>
                                    <Trash2 size={12} /> Delete
                                  </DropdownItem>
                                </>
                              )}
                            </Dropdown>
                          )}
                        </div>
                      </div>
                      <div className="text-[13.5px] text-zinc-700 dark:text-zinc-200 leading-relaxed">
                        {renderMarkdown(item.body)}
                      </div>
                    </div>
                  )}
                </li>
              )
            }

            // Plain event row
            return (
              <li key={item.id ?? idx} className="relative pl-10 pr-2 py-1.5 group rounded hover:bg-zinc-50 dark:hover:bg-zinc-900/40">
                <EventDot type={item.type} />
                <div className="flex items-baseline gap-1.5 text-[13px] flex-wrap text-zinc-500 dark:text-zinc-400">
                  <span className="font-medium text-zinc-700 dark:text-zinc-200">{actor?.name ?? actorId}</span>
                  <span>{getLabel(item)}</span>
                  <span className="text-zinc-400 dark:text-zinc-500 text-[11px] ml-auto" title={fullTime(time)}>
                    {formatEventTime(time)}
                  </span>
                </div>
              </li>
            )
          })}
        </ol>
      )}

      {/* Comment composer */}
      <div className="relative pl-10 mt-4">
        <div className="absolute left-0 top-1">
          <Avatar user={userById('u-1')} size={30} />
        </div>
        <CommentComposer
          onSubmit={handleSubmitComment}
          placeholder="Leave a comment… Use @ to mention someone."
        />
      </div>
    </div>
  )
}
