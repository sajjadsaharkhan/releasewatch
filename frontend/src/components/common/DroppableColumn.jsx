import React, { useState } from 'react'
import { useDndContext, useDroppable } from '@dnd-kit/core'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
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

// A column that can't take drops (a release's Done, BR-67): while a card is being
// dragged it dims and says why, so the drop never ends in an error.
function LockedNote({ reason }) {
  const reduce = useReducedMotion()
  return (
    <motion.div
      role="note"
      data-testid="column-locked-note"
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 6 }}
      animate={reduce ? { opacity: 1 } : { opacity: 1, y: 0 }}
      exit={reduce ? { opacity: 0 } : { opacity: 0, y: 4 }}
      transition={{ duration: 0.16, ease: [0.23, 1, 0.32, 1] }}
      className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-1.5 rounded-lg px-3 text-center text-[12px] font-medium text-zinc-600 dark:text-zinc-300"
    >
      <Icon name="lock" size={14} aria-hidden="true" />
      {reason}
    </motion.div>
  )
}

export function DroppableColumn({ status, issues, onOpen, readOnly = false, emptyText = 'No issues', headerExtra = null, lockedReason = null }) {
  const locked = !!lockedReason
  const { setNodeRef, isOver } = useDroppable({ id: status, disabled: readOnly || locked })
  const { active } = useDndContext()
  const refusing = locked && !!active

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
          "relative flex-1 space-y-2 min-h-[120px] rounded-lg p-2",
          "transition-all duration-200 ease-in-out",
          refusing && "cursor-not-allowed border border-dashed border-zinc-300 bg-zinc-100/70 dark:border-zinc-700 dark:bg-zinc-900/70 [&>*:not([role=note])]:opacity-40",
          !refusing && isOver
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
        <AnimatePresence>{refusing && <LockedNote reason={lockedReason} />}</AnimatePresence>
      </div>
    </div>
  )
}
