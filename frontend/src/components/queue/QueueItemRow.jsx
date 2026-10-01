import React from 'react'
import {
  DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors,
} from '@dnd-kit/core'
import {
  SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { cn } from '../../lib/cn'
import { PRIORITY } from '../../lib/constants'
import { relTime } from '../../lib/relTime'
import { Dropdown, DropdownItem, DropdownLabel, DropdownSep } from '../ui/Dropdown'
import { Icon } from '../ui/Icon'
import { StatusBadge } from '../ui/Badge'
import { Tooltip } from '../ui/Tooltip'
import {
  BlockerBadge, CyclesPill, DueTag, PIN_ICON, PlacementChip, RejectedTag, ReportsPill, TypeMark, ageOf,
} from './QueueMarks'

// One My Work row (slice 10, round 2 — docs/design.md §3 "My Work"): drag
// handle, position (or the pin), type + title + blocker, a quiet detail line
// (key, project, placement, reports, cycles, age, due), then status, the
// priority menu and the pin toggle. Pinned rows are soft yellow — the pin's
// own hue. A `done` row swaps the position for a check, "Finished …" for the
// due date, and has no handle, pin or priority menu.


/** One DndContext over the whole list; a drop across the pin line is the API's to refuse. */
export function SortableQueue({ items, enabled, onMove, children }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )
  if (!enabled) return children
  const onDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return
    const ids = items.map((i) => i.id)
    const down = ids.indexOf(over.id) > ids.indexOf(active.id)
    onMove(active.id, down ? { afterId: over.id } : { beforeId: over.id })
  }
  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
        {children}
      </SortableContext>
    </DndContext>
  )
}

/** The one inline edit: a priority pill that opens a menu. */
export function PriorityPicker({ item, onChange, disabled = false }) {
  const p = PRIORITY[item.priority]
  const pill = p?.pill ?? 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300'
  const label = `Priority: ${p?.label ?? 'Unrated'}`
  if (disabled || !onChange) {
    return (
      <span className={cn('inline-flex h-6 shrink-0 items-center gap-1 rounded-md px-2 text-[11.5px] font-medium', pill)}>
        <Icon name={p?.icon ?? 'minus'} size={12} strokeWidth={2.6} aria-hidden="true" />
        {p?.label ?? 'Unrated'}
      </span>
    )
  }
  return (
    <Dropdown
      width={184}
      align="right"
      trigger={
        <button
          type="button"
          aria-label={`${label}. Change priority`}
          className={cn(
            'inline-flex h-6 shrink-0 items-center gap-1 rounded-md px-2 text-[11.5px] font-medium transition-[filter] hover:brightness-95',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            pill,
          )}
        >
          <Icon name={p?.icon ?? 'minus'} size={12} strokeWidth={2.6} aria-hidden="true" />
          {p?.label ?? 'Unrated'}
          <Icon name="chevron-down" size={11} className="opacity-50" aria-hidden="true" />
        </button>
      }
    >
      <DropdownLabel>Priority</DropdownLabel>
      {Object.entries(PRIORITY).map(([key, v]) => (
        <DropdownItem key={key} onClick={() => onChange(item, key)}>
          <span className="flex w-full items-center gap-2">
            <Icon name={v.icon} size={13} strokeWidth={2.6} className={v.text} aria-hidden="true" />
            {v.label}
            {key === item.priority && <Icon name="check" size={13} className="ml-auto text-primary" aria-label="Current" />}
          </span>
        </DropdownItem>
      ))}
      <DropdownSep />
      <p className="px-3 pb-1.5 text-[11px] leading-snug text-muted-foreground">
        An unpinned item moves to its place by the default rule.
      </p>
    </Dropdown>
  )
}

/**
 * Pin / unpin. A locked pin (a CTO or Admin pinned someone else's queue) is
 * disabled for its owner with who pinned it as the reason; a full queue
 * disables Pin with the limit. Disabled buttons sit in a focusable wrapper so
 * the tooltip still opens.
 */
export function PinToggle({ item, pinsUsed, pinLimit, isOwner, onPin, onUnpin, busy = false }) {
  const locked = item.pinned && item.pin_locked && isOwner
  const full = !item.pinned && pinsUsed >= pinLimit
  const reason = locked
    ? `${item.pinned_by?.name ?? 'A CTO or Admin'} pinned this — only a CTO or Admin can unpin it.`
    : full ? `This queue already has ${pinLimit} pins — unpin one first.` : null
  const label = item.pinned ? (locked ? `${item.title} — locked pin` : `Unpin ${item.title}`) : `Pin ${item.title}`
  return (
    <Tooltip content={reason ?? (item.pinned ? 'Unpin' : 'Pin to the top')}>
      <span
        tabIndex={reason ? 0 : undefined}
        aria-label={reason ?? undefined}
        data-testid="pin-toggle"
        className="inline-flex rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <button
          type="button"
          disabled={Boolean(reason) || busy}
          aria-pressed={item.pinned}
          aria-label={label}
          onClick={(e) => { e.stopPropagation(); item.pinned ? onUnpin(item) : onPin(item) }}
          className={cn(
            'flex h-8 w-8 items-center justify-center rounded-md transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed',
            item.pinned
              ? cn(PIN_ICON, 'hover:bg-yellow-100 dark:hover:bg-yellow-900/40')
              : 'text-zinc-300 hover:bg-muted hover:text-foreground dark:text-zinc-600',
            full && 'opacity-40',
          )}
        >
          <Icon name={locked ? 'lock' : 'pin'} size={15} fill={item.pinned && !locked ? 'currentColor' : 'none'} aria-hidden="true" />
        </button>
      </span>
    </Tooltip>
  )
}

export function QueueItemRow({
  item, position, sortable = false, done = false, onOpen,
  onPriority, pin, // pin: { pinsUsed, pinLimit, isOwner, onPin, onUnpin, canPin, busy }
}) {
  const s = useSortable({ id: item.id, disabled: !sortable })
  const age = ageOf(item.created_at)
  return (
    <li
      ref={s.setNodeRef}
      style={{ transform: CSS.Transform.toString(s.transform), transition: s.transition }}
      data-testid="queue-row"
      data-item-id={item.id}
      data-pinned={item.pinned ? 'true' : undefined}
    >
      <div className={cn(
        'group relative flex items-center gap-3 rounded-xl border px-3 py-3 transition-[border-color,box-shadow]',
        item.pinned && !done
          ? 'border-yellow-200 bg-yellow-50/70 dark:border-yellow-900/60 dark:bg-yellow-950/20'
          : 'border-border bg-card hover:border-zinc-300 dark:hover:border-zinc-700',
        s.isDragging && 'z-10 shadow-xl',
      )}>
        {sortable ? (
          <button
            type="button"
            aria-label={`Reorder ${item.title}`}
            {...s.attributes}
            {...s.listeners}
            className="flex h-8 w-5 shrink-0 cursor-grab touch-none items-center justify-center rounded text-zinc-300 hover:text-zinc-600 active:cursor-grabbing focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-zinc-600 dark:hover:text-zinc-300"
          >
            <Icon name="grip-vertical" size={14} aria-hidden="true" />
          </button>
        ) : <span className="w-5 shrink-0" />}

        {done ? (
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-50 text-teal-600 dark:bg-teal-900/30 dark:text-teal-300">
            <Icon name="check" size={14} strokeWidth={2.6} aria-label="Done" />
          </span>
        ) : item.pinned ? (
          <span className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-yellow-100 dark:bg-yellow-900/40', PIN_ICON)}>
            <Icon name={item.pin_locked ? 'lock' : 'pin'} size={13} fill={item.pin_locked ? 'none' : 'currentColor'} aria-label={`Pinned, position ${position}`} />
          </span>
        ) : (
          <span className="w-7 shrink-0 text-center text-lg font-semibold tabular-nums text-zinc-300 dark:text-zinc-600" aria-label={`Position ${position}`}>
            {position}
          </span>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <TypeMark type={item.type} />
            <button
              type="button"
              onClick={() => onOpen(item)}
              className="truncate rounded text-left text-[13.5px] font-medium text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {item.title}
            </button>
            <BlockerBadge item={item} />
            <RejectedTag item={item} />
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11.5px] text-muted-foreground">
            <span className="font-mono">{item.key}</span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: item.project?.color }} aria-hidden="true" />
              {item.project?.name}
            </span>
            <PlacementChip container={item.container} />
            <ReportsPill item={item} />
            <CyclesPill item={item} />
            <span className="inline-flex items-center gap-1">
              <Icon name="clock" size={11} aria-hidden="true" />
              {age === 'today' ? 'Opened today' : `${age} old`}
            </span>
            {done && item.completed_at ? (
              <span className="inline-flex items-center gap-1 text-teal-700 dark:text-teal-300" title={new Date(item.completed_at).toLocaleString()}>
                <Icon name="circle-check-big" size={11} aria-hidden="true" />Finished {relTime(item.completed_at)}
              </span>
            ) : <DueTag item={item} />}
          </div>
        </div>

        <StatusBadge status={item.status} className="hidden lg:inline-flex" />
        <PriorityPicker item={item} onChange={onPriority} disabled={done} />
        {!done && pin?.canPin
          ? <PinToggle item={item} {...pin} />
          : <span className="w-8 shrink-0" />}
      </div>
    </li>
  )
}
