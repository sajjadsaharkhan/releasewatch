import React from 'react'
import { Link } from 'react-router-dom'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { AlertCircle, Clock, GripVertical } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Avatar, Checkbox, PriorityBadge, Tooltip, TypeIcon, UserHoverCard } from '../ui'
import { BacklogCategoryBadge, ReportedCount, TechDebtMarker } from '../common'
import { issueKey, issueSlug } from '../../lib/issueSlug'
import { fullTime, relTime } from '../../lib/relTime'

/**
 * One backlog item (slice 08): drag handle, checkbox, [rank], key, title with
 * its markers, category, priority, age, assignee. The whole row opens the
 * item; the handle, checkbox, and hover cards don't.
 *
 * `canManage` false disables the handle and checkbox with `manageReason` as
 * the tooltip (Policy's `manage_backlog` detail — never re-derived here).
 */
export function BacklogRow({
  item,
  rank,
  selected,
  onSelect,
  canManage,
  manageReason,
  stale,
  error,
  onOpen,
}) {
  const {
    attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging,
  } = useSortable({ id: item.id, disabled: !canManage })

  const key = issueKey(item)
  const assignee = item.assignee_user

  const handle = (
    <button
      type="button"
      ref={setActivatorNodeRef}
      {...attributes}
      {...listeners}
      aria-label={`Reorder ${key}`}
      disabled={!canManage}
      onClick={(e) => e.stopPropagation()}
      className={cn(
        'flex h-7 w-5 shrink-0 items-center justify-center rounded-md text-muted-foreground',
        'opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100',
        '[@media(hover:none)]:opacity-100',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        canManage ? 'cursor-grab active:cursor-grabbing hover:text-foreground' : 'cursor-not-allowed',
        isDragging && 'opacity-100'
      )}
    >
      <GripVertical className="h-3.5 w-3.5" aria-hidden="true" />
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

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      onClick={() => onOpen(item)}
      className={cn(
        'group relative flex h-10 cursor-pointer items-center gap-2 border-b border-border px-2 text-[13px] last:border-b-0',
        'bg-card transition-colors hover:bg-muted/50',
        selected && 'bg-accent/70 hover:bg-accent',
        (selected || error) && 'before:absolute before:inset-y-0 before:left-0 before:w-0.5',
        selected && 'before:bg-primary',
        error && 'before:bg-red-500',
        isDragging && 'z-10 rounded-lg shadow-lg ring-1 ring-border hover:bg-card'
      )}
    >
      {canManage ? handle : <Tooltip content={manageReason}>{handle}</Tooltip>}
      <span className="flex w-5 shrink-0 justify-center">
        {canManage ? checkbox : <Tooltip content={manageReason}>{checkbox}</Tooltip>}
      </span>

      {rank != null && (
        <span className="w-6 shrink-0 text-right text-[11px] tabular-nums text-muted-foreground">
          {rank}
        </span>
      )}

      <span className="inline-flex w-[92px] shrink-0 items-center gap-1 font-mono text-[11.5px] text-muted-foreground">
        <TypeIcon type={item.type} />
        {key}
      </span>

      <span className="flex min-w-0 flex-1 items-center gap-1.5">
        <Link
          to={`/issue/${issueSlug(item)}`}
          onClick={(e) => e.stopPropagation()}
          className="truncate font-medium text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
        >
          {item.title}
        </Link>
        <TechDebtMarker item={item} />
        <ReportedCount count={item.recurrence_count} />
        {error && (
          <Tooltip content={error}>
            <span className="inline-flex shrink-0 text-red-600 dark:text-red-400">
              <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="sr-only">{error}</span>
            </span>
          </Tooltip>
        )}
      </span>

      {/* Default is where most items sit — a badge on every row would be noise. */}
      {!item.backlog_category?.is_default && (
        <BacklogCategoryBadge category={item.backlog_category} className="hidden md:inline-flex" />
      )}

      <span className="hidden w-[84px] shrink-0 sm:flex">
        <PriorityBadge priority={item.priority} />
      </span>

      <span className="flex w-[70px] shrink-0 items-center justify-end gap-1 text-[12px] tabular-nums text-muted-foreground">
        {stale && (
          <Tooltip content={`Untouched for over 6 months — last updated ${fullTime(item.updated_at)}`}>
            <span className="inline-flex">
              <Clock className="h-3 w-3 text-amber-500" aria-hidden="true" />
              <span className="sr-only">Untouched for over 6 months</span>
            </span>
          </Tooltip>
        )}
        <Tooltip content={`Created ${fullTime(item.created_at)}`}>
          <span>{relTime(item.created_at)}</span>
        </Tooltip>
      </span>

      <span className="flex w-7 shrink-0 justify-center" onClick={(e) => e.stopPropagation()}>
        {assignee ? (
          <UserHoverCard user={assignee} size={22}>
            <Avatar user={assignee} size={22} />
          </UserHoverCard>
        ) : (
          <Tooltip content="Unassigned">
            <span className="block h-[22px] w-[22px] rounded-full border border-dashed border-muted-foreground/40">
              <span className="sr-only">Unassigned</span>
            </span>
          </Tooltip>
        )}
      </span>
    </li>
  )
}

/** Skeleton rows mirroring BacklogRow's columns. */
export function BacklogRowsSkeleton({ rows = 8 }) {
  const pulse = 'rounded bg-zinc-200 dark:bg-zinc-700 animate-pulse'
  const widths = ['w-56', 'w-72', 'w-48', 'w-64', 'w-40', 'w-60']
  return (
    <ul aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <li key={i} className="flex h-10 items-center gap-2 border-b border-border px-2 last:border-b-0">
          <span className="w-5" />
          <span className={cn('h-4 w-4', pulse)} />
          <span className={cn('ml-1 h-3 w-16', pulse)} />
          <span className="flex-1"><span className={cn('block h-3', widths[i % widths.length], pulse)} /></span>
          <span className={cn('hidden h-5 w-24 rounded-full md:block', pulse)} />
          <span className={cn('hidden h-5 w-16 rounded-full sm:block', pulse)} />
          <span className={cn('h-3 w-10', pulse)} />
          <span className={cn('h-[22px] w-[22px] rounded-full', pulse)} />
        </li>
      ))}
    </ul>
  )
}
