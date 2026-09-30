import React, { useState } from 'react'
import { useDroppable } from '@dnd-kit/core'
import { cn } from '../../lib/cn'
import { StatusBadge } from '../ui/Badge'
import { Icon } from '../ui/Icon'
import { TODO_AREAS } from '../../lib/constants'
import { DraggableIssueCard } from './DraggableIssueCard'

function Cards({ issues, onOpen, readOnly }) {
  return issues.map((issue) => (
    <DraggableIssueCard key={issue.id} issue={issue} onOpen={onOpen} readOnly={readOnly} />
  ))
}

/**
 * The To do column's areas (09a): Rejected, Returned, then To do — each a
 * collapsible group with a count. Only drawn when something came back; a
 * column of plain To do cards stays a plain list.
 */
function TodoAreas({ groups, onOpen, readOnly }) {
  const [collapsed, setCollapsed] = useState({})
  return groups.map(({ area, issues }) => {
    const open = !collapsed[area.key]
    const id = `todo-area-${area.key}`
    return (
      <div key={area.key} className="space-y-2" data-testid={id}>
        <button
          type="button"
          onClick={() => setCollapsed((c) => ({ ...c, [area.key]: open }))}
          aria-expanded={open}
          aria-controls={`${id}-cards`}
          title={area.hint}
          className={cn(
            'w-full flex items-center gap-1.5 rounded-md px-1.5 py-1 text-[12px] font-medium hover:bg-muted',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            area.text,
          )}
        >
          <Icon name={open ? 'chevron-down' : 'chevron-right'} size={12} aria-hidden="true" />
          <Icon name={area.icon} size={12} aria-hidden="true" />
          {area.label}
          <span className="ml-auto rounded-full bg-muted px-1.5 text-[10.5px] tabular-nums text-muted-foreground">
            {issues.length}
          </span>
        </button>
        {open && (
          <div id={`${id}-cards`} className="space-y-2">
            <Cards issues={issues} onOpen={onOpen} readOnly={readOnly} />
          </div>
        )}
      </div>
    )
  })
}

export function DroppableColumn({ status, issues, onOpen, readOnly = false, emptyText = 'No issues', headerExtra = null }) {
  const { setNodeRef, isOver } = useDroppable({ id: status, disabled: readOnly })

  const groups = status === 'todo'
    ? TODO_AREAS.map((area) => ({ area, issues: issues.filter(area.match) })).filter((g) => g.issues.length)
    : []
  const cameBack = groups.filter((g) => g.area.key !== 'todo')

  return (
    <div className="flex flex-col min-h-0" data-testid={`board-column-${status}`}>
      <div className="px-1 pb-2 flex items-center gap-1.5">
        <StatusBadge status={status} size="sm" />
        <span className="text-[11px] text-zinc-500 tabular-nums">{issues.length}</span>
        {cameBack.length > 0 && (
          <span className="text-[10.5px] text-muted-foreground">
            · {cameBack.map((g) => `${g.issues.length} ${g.area.label.toLowerCase()}`).join(' · ')}
          </span>
        )}
        {headerExtra}
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
        {cameBack.length > 0
          ? <TodoAreas groups={groups} onOpen={onOpen} readOnly={readOnly} />
          : <Cards issues={issues} onOpen={onOpen} readOnly={readOnly} />}
        {issues.length === 0 && !isOver && (
          <div className="h-16 flex items-center justify-center text-[11px] text-zinc-400 dark:text-zinc-600 italic">
            {emptyText}
          </div>
        )}
      </div>
    </div>
  )
}
