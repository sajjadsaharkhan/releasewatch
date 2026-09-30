import React from 'react'
import { DndContext, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { DroppableColumn } from './DroppableColumn'
import { StatusBadge } from '../ui/Badge'
import { BOARD_COLUMNS, BOARD_COLUMN_OF } from '../../lib/constants'

const CARD_TITLE_WIDTHS = [
  ['w-full', 'w-3/4'],
  ['w-5/6', 'w-1/2'],
  ['w-full', 'w-2/3'],
]

function SkeletonCard({ index }) {
  const pulse = 'bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse'
  const [line1, line2] = CARD_TITLE_WIDTHS[index % CARD_TITLE_WIDTHS.length]
  return (
    <div className="w-full rounded-lg border border-border bg-card p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className={`h-2.5 w-14 ${pulse}`} />
        <div className={`h-4 w-12 rounded ${pulse}`} />
      </div>
      <div className={`h-3 ${line1} ${pulse}`} />
      <div className={`h-3 ${line2} ${pulse}`} />
      <div className="flex items-center justify-between pt-0.5">
        <div className={`h-4 w-12 rounded ${pulse}`} />
        <div className={`h-[18px] w-[18px] rounded-full ${pulse}`} />
      </div>
    </div>
  )
}

function SkeletonColumn({ cards = 3 }) {
  const pulse = 'bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse'
  return (
    <div className="flex flex-col min-h-0">
      <div className="px-1 pb-2 flex items-center gap-1.5">
        <div className={`h-5 w-20 rounded-full ${pulse}`} />
        <div className={`h-3 w-4 ${pulse}`} />
      </div>
      <div className="flex-1 space-y-2 min-h-[120px] rounded-lg p-2 bg-zinc-50 dark:bg-zinc-900/40">
        {Array.from({ length: cards }, (_, i) => (
          <SkeletonCard key={i} index={i} />
        ))}
      </div>
    </div>
  )
}

export function IssueBoardSkeleton({ cardsPerColumn = 3 }) {
  return (
    <div className="px-7 py-5 grid gap-3" style={{ gridTemplateColumns: `repeat(${BOARD_COLUMNS.length}, minmax(220px, 1fr))` }}>
      {BOARD_COLUMNS.map(col => (
        <SkeletonColumn key={col} cards={cardsPerColumn} />
      ))}
    </div>
  )
}

// The column a card sits in — a Rejected card is on top of To do (09a).
const columnOf = (issue) => BOARD_COLUMN_OF[issue.status] ?? issue.status

// `readOnly` (a Released release, FR-54) turns off dragging. `columnHeaderExtra`
// and `emptyText` are per-status (e.g. the Stream's Done-range note).
export function IssueBoard({ issues = [], onOpen, onStatusChange, readOnly = false, columnHeaderExtra = {}, emptyText = {} }) {
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    })
  )

  const handleDragEnd = (event) => {
    const { active, over } = event
    if (!over) return
    const issue = issues.find(i => i.id === active.id)
    if (!issue) return
    // A Rejected card already sits in To do — dropping it there changes nothing.
    if (columnOf(issue) !== over.id) {
      onStatusChange?.(issue, over.id)
    }
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div className="px-7 py-5 grid gap-3" style={{ gridTemplateColumns: `repeat(${BOARD_COLUMNS.length}, minmax(220px, 1fr))` }}>
        {BOARD_COLUMNS.map(status => (
          <DroppableColumn
            key={status}
            status={status}
            issues={issues.filter(i => columnOf(i) === status)}
            onOpen={onOpen}
            readOnly={readOnly}
            headerExtra={columnHeaderExtra[status] ?? null}
            emptyText={emptyText[status] ?? 'No issues'}
          />
        ))}
      </div>
    </DndContext>
  )
}
