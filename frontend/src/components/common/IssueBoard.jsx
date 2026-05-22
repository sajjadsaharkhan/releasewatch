import React, { useMemo } from 'react'
import { DndContext, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { userById, MOCK_LABELS } from '../../data/mockData'
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

  const assigneeMap = useMemo(() => {
    const map = new Map()
    issues.forEach(issue => {
      if (issue.assignee && !map.has(issue.assignee)) {
        map.set(issue.assignee, userById(issue.assignee))
      }
    })
    return map
  }, [issues])

  const labelMap = useMemo(() => {
    const map = new Map()
    MOCK_LABELS.forEach(label => {
      map.set(label.id, label)
    })
    return map
  }, [])

  const handleDragEnd = (event) => {
    const { active, over } = event

    if (!over) return

    const issueId = active.id
    const newStatus = over.id

    const issue = issues.find(i => i.id === issueId)
    if (!issue) return

    if (issue.status !== newStatus) {
      onStatusChange?.(issue, newStatus)
    }
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div className="px-7 py-5 grid gap-3" style={{ gridTemplateColumns: `repeat(${COLUMNS.length}, minmax(220px, 1fr))` }}>
        {COLUMNS.map(status => {
          const columnIssues = issues.filter(i => i.status === status)
          return (
            <DroppableColumn
              key={status}
              status={status}
              issues={columnIssues}
              onOpen={onOpen}
              assigneeMap={assigneeMap}
              labelMap={labelMap}
            />
          )
        })}
      </div>
    </DndContext>
  )
}
