import React from 'react'
import { DndContext, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { DroppableColumn } from './DroppableColumn'

const COLUMNS = ['new', 'triaged', 'in_progress', 'fixed', 'verified']

export function IssueBoard({ issues = [], onOpen, onStatusChange }) {
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
    if (issue.status !== over.id) {
      onStatusChange?.(issue, over.id)
    }
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div className="px-7 py-5 grid gap-3" style={{ gridTemplateColumns: `repeat(${COLUMNS.length}, minmax(220px, 1fr))` }}>
        {COLUMNS.map(status => (
          <DroppableColumn
            key={status}
            status={status}
            issues={issues.filter(i => i.status === status)}
            onOpen={onOpen}
          />
        ))}
      </div>
    </DndContext>
  )
}
