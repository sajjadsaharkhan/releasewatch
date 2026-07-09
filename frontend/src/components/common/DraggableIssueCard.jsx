import React from 'react'
import { useDraggable } from '@dnd-kit/core'
import { RefreshCw } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Avatar, UserHoverCard } from '../ui'
import { LabelChip } from './LabelChip'
import { SeverityBadge } from '../ui/Badge'

export function DraggableIssueCard({ issue, assignee, labels, onOpen }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: issue.id,
    data: {
      issue,
      currentStatus: issue.status,
    },
  })

  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
      }
    : undefined

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "w-full text-left rounded-lg border border-border bg-card p-3 cursor-grab active:cursor-grabbing touch-none",
        "transition-all duration-200 ease-out",
        isDragging && "opacity-50 shadow-xl rotate-1 scale-105 z-50"
      )}
    >
      <button
        onClick={() => onOpen(issue)}
        className="w-full text-left outline-none"
        {...listeners}
        {...attributes}
      >
        <div className="flex items-center justify-between mb-1.5">
          <span className="font-mono text-[10.5px] text-zinc-500">issue-{issue.issue_number}</span>
          <SeverityBadge severity={issue.severity} size="sm" />
        </div>
        <div className="text-[12.5px] font-medium text-zinc-900 dark:text-zinc-100 leading-snug mb-2">{issue.title}</div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            {labels.slice(0, 2).map(l => <LabelChip key={l.id} label={l} />)}
          </div>
          {assignee && (
            <UserHoverCard user={assignee} size={18}>
              <Avatar user={assignee} size={18} />
            </UserHoverCard>
          )}
        </div>
        {(issue.regression_count ?? 0) > 0 && (
          <div className="mt-1.5 text-[10.5px] text-red-600 dark:text-red-400 inline-flex items-center gap-0.5">
            <RefreshCw className="h-3 w-3" /> regressed {issue.regression_count}×
          </div>
        )}
      </button>
    </div>
  )
}
