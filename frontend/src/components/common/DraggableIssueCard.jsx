import React from 'react'
import { useDraggable } from '@dnd-kit/core'
import { cn } from '../../lib/cn'
import { WorkItemCard } from './WorkItemCard'

// A board card (Stream, release and personal boards): `WorkItemCard` made
// draggable between columns (slice 10, P3 — cards look the same everywhere).
export function DraggableIssueCard({ issue, onOpen, readOnly = false }) {
  // Only the pointer listeners go on the card's link: the board has no keyboard
  // drag, and dnd-kit's attributes (role="button" and its instructions) would
  // hide that the card is a link.
  const { listeners, setNodeRef, isDragging } = useDraggable({
    id: issue.id,
    disabled: readOnly,
    data: {
      issue,
      currentStatus: issue.status,
    },
  })


  return (
    <div
      ref={setNodeRef}
      className={cn(
        "w-full text-left rounded-lg border border-border bg-card p-3",
        readOnly ? "cursor-pointer" : "cursor-grab active:cursor-grabbing touch-none",
        "transition-all duration-200 ease-out hover:border-zinc-300 dark:hover:border-zinc-600",
        // The moving copy is the board's DragOverlay (above every column, locked
        // or not); what stays behind is a faint placeholder.
        isDragging && "opacity-30"
      )}
    >
      <WorkItemCard
        item={issue}
        onOpen={onOpen}
        dragging={isDragging}
        linkProps={listeners}
      />
    </div>
  )
}

/** The card that follows the pointer: rendered by the board's `DragOverlay`, so it sits above every column. */
export function DragPreview({ issue }) {
  return (
    <div className="w-full cursor-grabbing rounded-lg border border-border bg-card p-3 shadow-xl rotate-1 scale-105">
      <WorkItemCard item={issue} dragging />
    </div>
  )
}
