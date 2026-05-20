import React from 'react'
import { cn } from '../../lib/cn'
import { Avatar } from '../ui/Avatar'
import { userById } from '../../data/mockData'
import { relTime, fullTime } from '../../lib/relTime'
import { renderMarkdown } from '../../lib/markdown'

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

function EventDot({ type }) {
  const style = EVENT_STYLES[type] ?? { dot: 'bg-zinc-300' }
  return <span className={cn('h-2 w-2 rounded-full shrink-0 mt-1.5', style.dot)} />
}

function getLabel(event) {
  const style = EVENT_STYLES[event.type]
  if (!style) return event.type
  if (typeof style.label === 'function') return style.label(event.detail)
  return style.label
}

export function IssueTimeline({ events = [], comments = [], issue }) {
  // Merge events and comments, sort by time
  const items = [
    ...events.map((e) => ({ ...e, _kind: 'event' })),
    ...comments.map((c) => ({ ...c, _kind: 'comment', type: 'comment' })),
  ].sort((a, b) => new Date(a.timestamp ?? a.createdAt) - new Date(b.timestamp ?? b.createdAt))

  if (items.length === 0) {
    return <p className="text-xs text-muted-foreground py-4">No activity yet.</p>
  }

  return (
    <div className="space-y-1">
      {items.map((item, idx) => {
        const isComment = item._kind === 'comment'
        const actorId = item.actor ?? item.author
        const actor = userById(actorId)
        const time = item.timestamp ?? item.createdAt

        if (isComment) {
          return (
            <div key={item.id ?? idx} className="flex gap-3 py-3">
              <Avatar user={actor} size={28} className="shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm font-medium">{actor?.name ?? actorId}</span>
                  {item.isInternal && (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                      Internal note
                    </span>
                  )}
                  <span
                    className="ml-auto text-xs text-muted-foreground shrink-0"
                    title={fullTime(time)}
                  >
                    {relTime(time)}
                  </span>
                </div>
                <div
                  className={cn(
                    'rounded-lg border border-border p-4 text-sm',
                    item.isInternal && 'bg-amber-50 border-amber-200 dark:bg-amber-900/10 dark:border-amber-800/30'
                  )}
                >
                  {renderMarkdown(item.body)}
                </div>
              </div>
            </div>
          )
        }

        // Plain event row
        return (
          <div key={item.id ?? idx} className="flex items-start gap-3 py-1.5">
            <div className="flex w-7 justify-center pt-1.5">
              <EventDot type={item.type} />
            </div>
            <p className="flex-1 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{actor?.name ?? actorId}</span>
              {' '}{getLabel(item)}
            </p>
            <span className="text-xs text-muted-foreground shrink-0" title={fullTime(time)}>
              {relTime(time)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
