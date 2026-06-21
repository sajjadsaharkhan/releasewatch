import React, { useState, useRef, useEffect } from 'react'
import { MessageSquare, MoreVertical, Trash2, Edit3, Link2 } from 'lucide-react'
import { cn } from '../../lib/cn'
import { useToast } from '../../hooks/useToast'
import { Avatar, UserHoverCard } from '../ui'
import { Icon } from '../ui/Icon'
import { Badge, StatusBadge, SeverityBadge, RoleBadge } from '../ui/Badge'
import { ENVIRONMENT } from './DescriptionSection'
import { Dropdown, DropdownItem, DropdownSep } from '../ui/Dropdown'
import { relTime, fullTime, formatEventTime } from '../../lib/relTime'
import { renderMarkdown } from '../../lib/markdown'
import { CommentComposer } from './CommentComposer'

const EVENT_STYLES = {
  filed:               { dot: 'bg-blue-500',   label: 'filed this issue' },
  status_changed:      { dot: 'bg-zinc-400',   label: (e) => `changed status to ${e.detail ?? e.meta?.to ?? ''}` },
  assigned:            { dot: 'bg-violet-500', label: (e) => null },
  fixed:               { dot: 'bg-green-500',  label: 'marked as fixed' },
  regression:          { dot: 'bg-red-500',    label: 'marked as regression' },
  verified:            { dot: 'bg-teal-500',   label: 'verified the fix' },
  reopened:            { dot: 'bg-amber-500',  label: 'reopened this issue' },
  comment:             { dot: 'bg-zinc-400',   label: 'commented' },
  severity_changed:    { dot: 'bg-amber-500',  label: (e) => null },
  label_added:         { dot: 'bg-blue-500',   label: (e) => null },
  label_removed:       { dot: 'bg-zinc-400',   label: (e) => null },
  blocker_flagged:     { dot: 'bg-red-500',    label: (e) => null },
  blocker_cleared:     { dot: 'bg-green-500',  label: (e) => null },
  duplicate_linked:    { dot: 'bg-zinc-400',   label: (e) => `marked as duplicate of #${e.meta?.parent_number ?? ''}` },
  title_changed:       { dot: 'bg-zinc-400',   label: 'changed the title' },
  description_changed: { dot: 'bg-zinc-400',   label: 'updated the description' },
  steps_changed:       { dot: 'bg-zinc-400',   label: 'updated reproduction steps' },
  release_changed:     { dot: 'bg-sky-500',    label: (e) => `moved to release ${e.meta?.to_version ?? ''}` },
  project_changed:     { dot: 'bg-sky-500',    label: (e) => `moved to project ${e.meta?.to_name ?? ''}` },
  environment_changed: { dot: 'bg-amber-400',  label: (e) => null },
  needs_clarification: { dot: 'bg-orange-500', label: 'requested clarification from reporter' },
}

const EVENT_ICONS = {
  filed:               'file-plus',
  assigned:            'user-plus',
  severity_changed:    'arrow-up-down',
  status_changed:      'git-pull-request',
  label_added:         'tag',
  label_removed:       'tag',
  fixed:               'check',
  verified:            'shield-check',
  regression:          'refresh-ccw',
  blocker_flagged:     'octagon-alert',
  blocker_cleared:     'shield-check',
  duplicate_linked:    'copy',
  reopened:            'rotate-ccw',
  title_changed:       'pencil',
  description_changed: 'file-text',
  steps_changed:       'list',
  release_changed:     'package',
  project_changed:     'folder',
  environment_changed: 'monitor',
  comment:             'message-square',
  needs_clarification: 'help-circle',
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

export function IssueTimeline({ events = [], comments = [], issue, users = [], labels = [], currentUser, onAddComment, onUpdateComment, onDeleteComment, hasMore = false, loadingMore = false, onLoadMore }) {
  const [editingCommentId, setEditingCommentId] = useState(null)
  const { toast } = useToast()

  const handleCopyLink = (commentId) => {
    const url = `${window.location.origin}${window.location.pathname}#comment-${commentId}`
    navigator.clipboard.writeText(url)
    toast({ title: 'Link copied to clipboard' })
  }
  const sentinelRef = useRef(null)

  useEffect(() => {
    if (!sentinelRef.current || !hasMore || loadingMore) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) onLoadMore?.() },
      { threshold: 0.1 }
    )
    obs.observe(sentinelRef.current)
    return () => obs.disconnect()
  }, [hasMore, loadingMore, onLoadMore])

  function resolveUser(userOrId) {
    if (!userOrId) return null
    if (typeof userOrId === 'object' && userOrId.name) return userOrId
    return users.find(u => String(u.id) === String(userOrId)) ?? null
  }

  function getLabel(event) {
    const style = EVENT_STYLES[event.type]
    if (!style) return event.type

    const from = event.from ?? event.meta?.from
    const to = event.to ?? event.meta?.to

    if (event.type === 'status_changed' && from && to) {
      return (
        <>
          changed status <StatusBadge status={from} size="sm" />
          <Icon name="arrow-right" size={11} className="inline mx-0.5 text-zinc-400" />
          <StatusBadge status={to} size="sm" />
        </>
      )
    }

    if (event.type === 'severity_changed' && from && to) {
      return (
        <>
          changed severity <SeverityBadge severity={from} size="sm" dot />
          <Icon name="arrow-right" size={11} className="inline mx-0.5 text-zinc-400" />
          <SeverityBadge severity={to} size="sm" dot />
        </>
      )
    }

    if (event.type === 'assigned') {
      const assigneeId = event.detail ?? event.meta?.assignee_id
      const assignee = event.assignee_user ?? resolveUser(assigneeId)
      return (
        <>
          assigned to{' '}
          {assignee ? (
            <UserHoverCard user={assignee}>
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 text-[11px] font-medium align-middle cursor-pointer">
                <Avatar user={assignee} size={14} />
                {assignee.name}
              </span>
            </UserHoverCard>
          ) : (
            assigneeId ?? 'someone'
          )}
        </>
      )
    }

    if (event.type === 'label_added' || event.type === 'label_removed') {
      const name = event.meta?.label_name ?? ''
      const lbl = labels.find(l => l.name === name) ?? null
      const chip = lbl ? (
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium align-middle"
          style={{ backgroundColor: lbl.color + '22', color: lbl.color, border: `1px solid ${lbl.color}44` }}
        >
          <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: lbl.color }} />
          {name}
        </span>
      ) : (
        <code className="text-[11px] bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">{name}</code>
      )
      return event.type === 'label_added'
        ? <>{' added label '}{chip}</>
        : <>{' removed label '}{chip}</>
    }

    if (event.type === 'blocker_flagged') {
      return (
        <>
          flagged as{' '}
          <Badge tone="red" className="align-middle gap-1">
            <Icon name="octagon-alert" size={10} strokeWidth={2.5} />
            Release Blocker
          </Badge>
        </>
      )
    }
    if (event.type === 'blocker_cleared') {
      return (
        <>
          cleared the{' '}
          <Badge tone="green" className="align-middle gap-1">
            <Icon name="shield-check" size={10} strokeWidth={2.5} />
            Release Blocker
          </Badge>
        </>
      )
    }

    if (event.type === 'environment_changed' && to) {
      const fromEnv = from ? ENVIRONMENT[from] : null
      const toEnv = ENVIRONMENT[to]
      return (
        <>
          {fromEnv ? (
            <>
              changed environment{' '}
              <Badge tone={fromEnv.tone} className="align-middle">{fromEnv.label}</Badge>
              <Icon name="arrow-right" size={11} className="inline mx-0.5 text-zinc-400" />
              <Badge tone={toEnv?.tone ?? 'default'} className="align-middle">{toEnv?.label ?? to}</Badge>
            </>
          ) : (
            <>
              set environment to{' '}
              <Badge tone={toEnv?.tone ?? 'default'} className="align-middle">{toEnv?.label ?? to}</Badge>
            </>
          )}
        </>
      )
    }

    if (event.type === 'release_changed') {
      const toVersion = event.meta?.to_version ?? ''
      const fromVersion = event.meta?.from_version
      return (
        <>
          {fromVersion ? (
            <>
              moved release{' '}
              <Badge tone="blue" className="align-middle font-mono">{fromVersion}</Badge>
              <Icon name="arrow-right" size={11} className="inline mx-0.5 text-zinc-400" />
              <Badge tone="blue" className="align-middle font-mono">{toVersion}</Badge>
            </>
          ) : (
            <>
              moved to release{' '}
              <Badge tone="blue" className="align-middle font-mono">{toVersion}</Badge>
            </>
          )}
        </>
      )
    }

    if (typeof style.label === 'function') return style.label(event)
    return style.label
  }

  // Merge events and comments, sort by time
  const items = [
    ...events.map((e) => ({ ...e, _kind: 'event' })),
    ...comments.map((c) => ({ ...c, _kind: 'comment', type: 'comment' })),
  ].sort((a, b) => new Date(a.timestamp ?? a.createdAt) - new Date(b.timestamp ?? b.createdAt))

  const handleSubmitComment = (body, isInternal, mentionedUserIds) => {
    onAddComment?.(body, isInternal, mentionedUserIds)
  }

  const handleEditComment = (body, isInternal, mentionedUserIds) => {
    onUpdateComment?.(editingCommentId, body, isInternal, mentionedUserIds, new Date().toISOString())
    setEditingCommentId(null)
  }

  const handleDeleteComment = (commentId) => {
    onDeleteComment?.(commentId)
  }

  const isOwnComment = (comment) => {
    const authorId = comment.actor ?? comment.author
    return currentUser && String(authorId) === String(currentUser.id)
  }

  return (
    <div>
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
            const actor = item.actor_user ?? resolveUser(actorId)
            const time = item.timestamp ?? item.createdAt

            if (isComment) {
              const isEditing = editingCommentId === item.id
              const ownComment = isOwnComment(item)

              return (
                <li key={item.id ?? idx} id={`comment-${item.id}`} className="relative pl-10 pr-2 py-2">
                  <div className="absolute left-0 top-2">
                    <UserHoverCard user={actor} size={30}>
                      <Avatar user={actor} size={30} />
                    </UserHoverCard>
                  </div>

                  {isEditing ? (
                    <CommentComposer
                      initialValue={item.body}
                      initialInternal={item.isInternal}
                      initialMentionedUsers={item.mentionedUsers || []}
                      mode="edit"
                      onSubmit={handleEditComment}
                      onCancelEdit={() => setEditingCommentId(null)}
                      users={users}
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
                          <Dropdown
                            align="end"
                            width={150}
                            trigger={
                              <button className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 p-0.5 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800">
                                <MoreVertical size={13} />
                              </button>
                            }
                          >
                            {({ close }) => (
                              <>
                                <DropdownItem onClick={() => { handleCopyLink(item.id); close(); }}>
                                  <Link2 size={12} /> Copy link
                                </DropdownItem>
                                {ownComment && (
                                  <>
                                    <DropdownSep />
                                    <DropdownItem onClick={() => { setEditingCommentId(item.id); close(); }}>
                                      <Edit3 size={12} /> Edit
                                    </DropdownItem>
                                    <DropdownSep />
                                    <DropdownItem destructive onClick={() => { handleDeleteComment(item.id); close(); }}>
                                      <Trash2 size={12} /> Delete
                                    </DropdownItem>
                                  </>
                                )}
                              </>
                            )}
                          </Dropdown>
                        </div>
                      </div>
                      <div dir="auto" className="text-[13.5px] text-zinc-700 dark:text-zinc-200 leading-relaxed">
                        {renderMarkdown(item.body)}
                      </div>

                      {item.mentionedUsers && item.mentionedUsers.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-zinc-100 dark:border-zinc-800 flex items-center gap-1.5 flex-wrap">
                          <span className="text-xs text-muted-foreground flex items-center gap-1">
                            <Icon name="at-sign" size={11} />
                            Mentioned:
                          </span>
                          {item.mentionedUsers.map(userId => {
                            const user = resolveUser(userId)
                            if (!user) return null
                            return (
                              <UserHoverCard key={String(userId)} user={user}>
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-[11px] font-medium cursor-pointer border border-blue-200 dark:border-blue-800 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors">
                                  <Avatar user={user} size={14} />
                                  {user.name}
                                </span>
                              </UserHoverCard>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </li>
              )
            }

            // Plain event row
            const hasBody = item.type === 'needs_clarification' && item.body
            const handleCopyEventLink = () => {
              const url = `${window.location.origin}${window.location.pathname}#event-${item.id}`
              navigator.clipboard.writeText(url)
              toast({ title: 'Link copied to clipboard' })
            }
            return (
              <li key={item.id ?? idx} id={`event-${item.id ?? idx}`} className="relative pl-10 pr-2 py-1.5 group rounded hover:bg-zinc-50 dark:hover:bg-zinc-900/40">
                <EventDot type={item.type} />
                <div className="flex items-baseline gap-1.5 text-[13px] flex-wrap text-zinc-500 dark:text-zinc-400">
                  <span className="font-medium text-zinc-700 dark:text-zinc-200">{actor?.name ?? actorId}</span>
                  <span>{getLabel(item)}</span>
                  <span className="text-zinc-400 dark:text-zinc-500 text-[11px] ml-auto" title={fullTime(time)}>
                    {formatEventTime(time)}
                  </span>
                  {item.type === 'needs_clarification' && (
                    <Dropdown
                      align="end"
                      width={150}
                      trigger={
                        <button className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 p-0.5 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800">
                          <MoreVertical size={13} />
                        </button>
                      }
                    >
                      {({ close }) => (
                        <DropdownItem onClick={() => { handleCopyEventLink(); close() }}>
                          <Link2 size={12} /> Copy link
                        </DropdownItem>
                      )}
                    </Dropdown>
                  )}
                </div>
                {hasBody && (
                  <div className="mt-1.5 rounded-md border border-orange-200 dark:border-orange-900/50 bg-orange-50/60 dark:bg-orange-950/20 px-3 py-2 text-[13px] text-zinc-700 dark:text-zinc-300 leading-relaxed prose-sm max-w-none">
                    {renderMarkdown(item.body)}
                  </div>
                )}
              </li>
            )
          })}
        </ol>
      )}

      {/* Infinite scroll sentinel */}
      {hasMore && <div ref={sentinelRef} className="h-1" />}
      {loadingMore && (
        <div className="flex items-center justify-center py-3 text-xs text-zinc-400 gap-2">
          <svg className="animate-spin h-3.5 w-3.5 text-zinc-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          Loading more…
        </div>
      )}

      {/* Comment composer */}
      <div className="relative pl-10 mt-4">
        <div className="absolute left-0 top-1">
          <UserHoverCard user={currentUser} size={30}>
            <Avatar user={currentUser} size={30} />
          </UserHoverCard>
        </div>
        <CommentComposer
          onSubmit={handleSubmitComment}
          placeholder="Leave a comment…"
          users={users}
        />
      </div>
    </div>
  )
}
