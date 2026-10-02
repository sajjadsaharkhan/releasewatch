import React from 'react'
import { Link } from 'react-router-dom'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { cn } from '../../lib/cn'
import { issueKey, issueSlug } from '../../lib/issueSlug'
import { fullTime } from '../../lib/relTime'
import { Avatar, Checkbox, Icon, Tooltip, UserHoverCard } from '../ui'
import { BacklogCategoryBadge, ReportedCount, TechDebtMarker } from '../common'
import { PriorityPicker } from '../queue/QueueItemRow'
import { TypeMark, ageOf } from '../queue/QueueMarks'

/**
 * One backlog item (slice 08; redesigned 2026-10-02 from prototype R2): grip
 * handle, a position that gives way to the checkbox on hover or once anything
 * is selected, then two lines — type, title and markers over key, category,
 * age and the stale note — then the priority menu and the assignee's hover
 * card. Rows sit in one panel and are divided by a line. The whole row opens
 * the item; the handle, checkbox, menu and hover card don't.
 *
 * `canManage` false disables the handle, checkbox and priority menu, with
 * `manageReason` as the tooltip (Policy's `manage_backlog` detail — never
 * re-derived here). `canDrag` is false while a filter hides part of the list.
 */
export function BacklogRow({
  item,
  rank,
  selected,
  anySelected,
  onSelect,
  canManage,
  canDrag,
  manageReason,
  stale,
  error,
  onOpen,
  onPriority,
  showCategory = true,
}) {
  const {
    attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging,
  } = useSortable({ id: item.id, disabled: !canDrag })

  const key = issueKey(item)
  const age = ageOf(item.created_at)
  const category = showCategory ? item.backlog_category : null

  const handle = (
    <button
      type="button"
      ref={setActivatorNodeRef}
      {...attributes}
      {...listeners}
      aria-label={`Reorder ${key}`}
      disabled={!canDrag}
      onClick={(e) => e.stopPropagation()}
      className={cn(
        'flex h-8 w-5 shrink-0 touch-none items-center justify-center rounded text-zinc-300 dark:text-zinc-600',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        canDrag
          ? 'cursor-grab hover:text-zinc-600 active:cursor-grabbing dark:hover:text-zinc-300'
          : 'cursor-not-allowed opacity-40',
      )}
    >
      <Icon name="grip-vertical" size={14} aria-hidden="true" />
    </button>
  )

  const checkbox = (
    <Checkbox
      checked={selected}
      disabled={!canManage}
      onCheckedChange={(next, e) => onSelect(item.id, next, e)}
      aria-label={`Select ${key}`}
    />
  )

  const showCheck = selected || anySelected

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      onClick={() => onOpen(item)}
      data-testid="backlog-row"
      className="border-b border-border last:border-b-0"
    >
      <div
        className={cn(
          'group relative flex cursor-pointer items-center gap-3 bg-card px-3 py-2.5 transition-colors hover:bg-muted/50',
          selected && 'bg-accent/70 hover:bg-accent',
          (selected || error) && 'before:absolute before:inset-y-0 before:left-0 before:w-0.5',
          selected && 'before:bg-primary',
          error && 'before:bg-red-500',
          isDragging && 'z-10 rounded-lg shadow-xl ring-1 ring-border hover:bg-card',
        )}
      >
        {handle}

        <span className="relative flex h-7 w-7 shrink-0 items-center justify-center">
          <span
            aria-label={`Position ${rank}`}
            className={cn(
              'text-center text-[12px] font-semibold tabular-nums text-zinc-300 dark:text-zinc-600',
              showCheck ? 'hidden' : 'group-focus-within:hidden group-hover:hidden',
            )}
          >
            {rank}
          </span>
          <span className={cn('items-center justify-center', showCheck ? 'flex' : 'hidden group-focus-within:flex group-hover:flex')}>
            {canManage ? checkbox : <Tooltip content={manageReason}>{checkbox}</Tooltip>}
          </span>
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <TypeMark type={item.type} />
            <Link
              to={`/issue/${issueSlug(item)}`}
              onClick={(e) => e.stopPropagation()}
              className="truncate rounded text-[13.5px] font-medium text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {item.title}
            </Link>
            <TechDebtMarker item={item} />
            <ReportedCount count={item.recurrence_count} />
            {error && (
              <Tooltip content={error}>
                <span className="inline-flex shrink-0 text-red-600 dark:text-red-400">
                  <Icon name="alert-circle" size={14} aria-hidden="true" />
                  <span className="sr-only">{error}</span>
                </span>
              </Tooltip>
            )}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11.5px] text-muted-foreground">
            <span className="font-mono">{key}</span>
            <BacklogCategoryBadge category={category} />
            <Tooltip content={`Created ${fullTime(item.created_at)}`}>
              <span className="inline-flex items-center gap-1">
                <Icon name="clock" size={11} aria-hidden="true" />
                {age === 'today' ? 'Opened today' : `${age} old`}
              </span>
            </Tooltip>
            {stale && (
              <Tooltip content={`Last updated ${fullTime(item.updated_at)}`}>
                <span className="inline-flex items-center gap-1 text-amber-700 dark:text-amber-400">
                  <Icon name="history" size={11} aria-hidden="true" />
                  Untouched for over 6 months
                </span>
              </Tooltip>
            )}
          </div>
        </div>

        <span className="shrink-0" onClick={(e) => e.stopPropagation()}>
          {canManage ? (
            <PriorityPicker item={item} onChange={onPriority} note={null} />
          ) : (
            <Tooltip content={manageReason}>
              <span><PriorityPicker item={item} disabled /></span>
            </Tooltip>
          )}
        </span>

        <span className="flex w-6 shrink-0 justify-center" onClick={(e) => e.stopPropagation()}>
          {item.assignee_user ? (
            <UserHoverCard user={item.assignee_user} size={22}>
              <Avatar user={item.assignee_user} size={22} />
            </UserHoverCard>
          ) : (
            <Tooltip content="Unassigned">
              <span className="block h-[22px] w-[22px] rounded-full border border-dashed border-muted-foreground/40">
                <span className="sr-only">Unassigned</span>
              </span>
            </Tooltip>
          )}
        </span>
      </div>
    </li>
  )
}

/** Skeleton rows mirroring BacklogRow's two lines. */
export function BacklogRowsSkeleton({ rows = 6 }) {
  const pulse = 'rounded bg-zinc-200 dark:bg-zinc-700 animate-pulse'
  const widths = ['w-56', 'w-72', 'w-48', 'w-64', 'w-40', 'w-60']
  return (
    <ul aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <li key={i} className="flex items-center gap-3 border-b border-border px-3 py-2.5 last:border-b-0">
          <span className="w-5" />
          <span className={cn('h-4 w-7', pulse)} />
          <span className="flex-1 space-y-2">
            <span className={cn('block h-3.5', widths[i % widths.length], pulse)} />
            <span className={cn('block h-3 w-32 opacity-60', pulse)} />
          </span>
          <span className={cn('h-6 w-20 rounded-md', pulse)} />
          <span className={cn('h-[22px] w-[22px] rounded-full', pulse)} />
        </li>
      ))}
    </ul>
  )
}
