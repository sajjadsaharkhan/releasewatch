import React from 'react'
import { useDroppable } from '@dnd-kit/core'
import { cn } from '../../lib/cn'
import { StatusBadge } from '../ui/Badge'
import { DraggableIssueCard } from './DraggableIssueCard'

export function DroppableColumn({ status, issues, onOpen }) {
  const { setNodeRef, isOver } = useDroppable({ id: status })

  return (
    <div className="flex flex-col min-h-0">
      <div className="px-1 pb-2 flex items-center gap-1.5">
        <StatusBadge status={status} size="sm" />
        <span className="text-[11px] text-zinc-500 tabular-nums">{issues.length}</span>
      </div>
      <div
        ref={setNodeRef}
        className={cn(
          "flex-1 space-y-2 min-h-[120px] rounded-lg p-2",
          "transition-all duration-200 ease-in-out",
          isOver
            ? "bg-zinc-200/60 dark:bg-zinc-800/70 ring-2 ring-blue-400 dark:ring-blue-500 scale-[1.02]"
            : "bg-zinc-50 dark:bg-zinc-900/40"
        )}
      >
        {issues.map((issue) => (
          <DraggableIssueCard
            key={issue.id}
            issue={issue}
            assignee={issue.assignee_user}
            labels={issue.labels_detail ?? []}
            onOpen={onOpen}
          />
        ))}
        {issues.length === 0 && !isOver && (
          <div className="h-16 flex items-center justify-center text-[11px] text-zinc-400 dark:text-zinc-600 italic">
            No issues
          </div>
        )}
      </div>
    </div>
  )
}
