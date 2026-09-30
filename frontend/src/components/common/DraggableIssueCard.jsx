import React from 'react'
import { useDraggable } from '@dnd-kit/core'
import { cn } from '../../lib/cn'
import { WorkItemCard } from './WorkItemCard'

// A board card (Stream, release and personal boards): `WorkItemCard` made
// draggable between columns (slice 10, P3 — cards look the same everywhere).
export function DraggableIssueCard({ issue, onOpen, readOnly = false }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: issue.id,
    disabled: readOnly,
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
        "w-full text-left rounded-lg border border-border bg-card p-3",
        readOnly ? "cursor-pointer" : "cursor-grab active:cursor-grabbing touch-none",
        "transition-all duration-200 ease-out hover:border-zinc-300 dark:hover:border-zinc-600",
        isDragging && "opacity-50 shadow-xl rotate-1 scale-105 z-50"
      )}
    >
      <WorkItemCard
        item={issue}
        onOpen={onOpen}
        dragging={isDragging}
        buttonProps={{ ...listeners, ...attributes }}
      />
    </div>
  )
}
