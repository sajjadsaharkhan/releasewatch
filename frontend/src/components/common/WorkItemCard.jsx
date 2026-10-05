import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { cn } from '../../lib/cn'
import { timelineApi } from '../../lib/api'
import { issueKey } from '../../lib/issueSlug'
import { relTime, formatDay } from '../../lib/relTime'
import { CYCLE_REASON, PRIORITY, TECH_DEBT, TYPE } from '../../lib/constants'
import { Avatar } from '../ui/Avatar'
import { StatusBadge } from '../ui/Badge'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'
import { ReportedCount } from './ReportedCount'
import { TechDebtMarker } from './TechDebtMarker'
import { CycleBadge } from './CycleBadge'
import { LabelChip } from './LabelChip'
import { Assignee, BlockerPill, InlineLabels, PlacementChip } from './WorkItemMeta'

// Slice 10 (FR-42, P3): one card for every board and the personal queue. By
// default it shows only the title, the project and a priority glyph; compact
// markers appear only when they matter; hovering (or focusing) spells
// everything out. Reads `WorkItemCard` from the queue/board API, and the full
// `IssueResponse` on the Stream and release boards — `normalize` maps both.

const HOVER_WIDTH = 320
const HOVER_HEIGHT = 290
const DUE_SOON_DAYS = 2

/** `none` | `soon` (≤ 2 days away) | `overdue` — the server's rule, for payloads without it. */
function dueStateOf(due) {
  if (!due) return 'none'
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const day = new Date(`${due}T00:00:00`)
  const days = Math.round((day - today) / 86400000)
  if (days < 0) return 'overdue'
  return days <= DUE_SOON_DAYS ? 'soon' : 'none'
}

function normalize(i) {
  return {
    ...i,
    key: i.key ?? issueKey(i),
    project: i.project ?? (i.project_name
      ? { name: i.project_name, slug: i.project_slug, color: i.project_color } : null),
    dueState: i.due_state ?? dueStateOf(i.due_date),
    container: i.container !== undefined
      ? i.container
      : i.container_kind
        ? { kind: i.container_kind, name: i.release_version, status: i.release_status }
        : null,
    labels: (i.labels_detail ?? i.labels ?? []).map((l) => (typeof l === 'string' ? { name: l, color: '#6366f1' } : l)),
    reporter: i.reporter ?? i.reporter_user ?? null,
    assignee: i.assignee ?? i.assignee_user ?? null,
  }
}

const shortDay = (day) => new Date(`${day}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

function dueLabel(item) {
  if (item.dueState === 'overdue') return 'Overdue'
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const days = Math.round((new Date(`${item.due_date}T00:00:00`) - today) / 86400000)
  return days === 0 ? 'Due today' : days === 1 ? 'Due tomorrow' : `Due in ${days}d`
}

export function PriorityGlyph({ priority, className }) {
  const p = PRIORITY[priority]
  const label = p ? `${p.label} priority` : 'Unrated'
  return (
    <Tooltip content={label}>
      <span className={cn('inline-flex shrink-0', p?.text ?? 'text-zinc-400', className)}>
        <Icon name={p?.icon ?? 'minus'} size={14} strokeWidth={2.6} aria-hidden="true" />
        <span className="sr-only">{label}</span>
      </span>
    </Tooltip>
  )
}

export function ProjectChip({ project, className }) {
  if (!project) return null
  return (
    <span className={cn('inline-flex min-w-0 items-center gap-1 text-[11px] text-muted-foreground', className)}>
      <span
        className="h-2 w-2 shrink-0 rounded-sm"
        style={{ backgroundColor: project.color || '#a1a1aa' }}
        aria-hidden="true"
      />
      <span className="truncate">{project.name}</span>
    </span>
  )
}

function PinMarker({ item }) {
  if (!item.pinned) return null
  const label = item.pin_locked ? 'Pinned by a CTO or Admin — locked' : 'Pinned'
  return (
    <Tooltip content={label}>
      <span className="inline-flex shrink-0 items-center text-primary">
        <Icon name={item.pin_locked ? 'lock' : 'pin'} size={11} strokeWidth={2.4} aria-hidden="true" />
        <span className="sr-only">{label}</span>
      </span>
    </Tooltip>
  )
}

function RejectMarker({ item }) {
  if (item.status !== 'rejected') return null
  const reason = CYCLE_REASON[item.reject_reason] ?? CYCLE_REASON.review
  return (
    <Tooltip content={reason.label}>
      <span className={cn('inline-flex h-[18px] shrink-0 items-center rounded-full px-1', reason.pill)}>
        <Icon name={reason.icon} size={11} aria-hidden="true" />
        <span className="sr-only">{reason.label}</span>
      </span>
    </Tooltip>
  )
}

function DueMarker({ item }) {
  if (!item.due_date) return null
  const overdue = item.dueState === 'overdue'
  const far = item.dueState === 'none'
  const label = far ? 'Due' : dueLabel(item)
  return (
    <Tooltip content={`${label} · ${formatDay(item.due_date)}`}>
      <span
        className={cn(
          'inline-flex shrink-0 items-center gap-0.5 text-[10.5px] font-semibold',
          overdue ? 'text-red-600 dark:text-red-400'
            : far ? 'font-medium text-muted-foreground' : 'text-amber-700 dark:text-amber-300',
        )}
      >
        <Icon name={overdue ? 'calendar-x' : far ? 'calendar' : 'calendar-clock'} size={11} strokeWidth={2.4} aria-hidden="true" />
        <span>{overdue ? 'Overdue' : far ? shortDay(item.due_date) : label.replace('Due ', '')}</span>
      </span>
    </Tooltip>
  )
}

/** Markers shown only when they matter (FR-42, FR-63). */
function Markers({ item }) {
  return (
    <>
      <PinMarker item={item} />
      <RejectMarker item={item} />
      <CycleBadge item={item} compact />
      <ReportedCount count={item.recurrence_count} className="text-[10.5px]" />
      <DueMarker item={item} />
      <TechDebtMarker item={item} compact />
    </>
  )
}

function HoverRow({ icon, children }) {
  return (
    <div className="flex items-start gap-1.5 text-[11.5px] text-muted-foreground">
      <Icon name={icon} size={12} className="mt-[2px] shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}

function RejectComment({ item }) {
  const { data, isLoading } = useQuery({
    queryKey: ['timeline-event', item.id, item.reject_comment_id],
    queryFn: () => timelineApi.get(item.id, item.reject_comment_id).then((res) => res.data),
    enabled: !!item.reject_comment_id,
    staleTime: Infinity,
  })
  if (!item.reject_comment_id) return null
  if (isLoading) return <div className="h-3 w-40 animate-pulse rounded bg-zinc-200 dark:bg-zinc-700" />
  if (!data?.body) return null
  return (
    <p className="mt-0.5 line-clamp-3 border-l-2 border-border pl-2 italic text-foreground/80">{data.body}</p>
  )
}

/** Everything spelled out (FR-42, AC-44). */
function HoverDetails({ item }) {
  const reason = item.status === 'rejected' ? (CYCLE_REASON[item.reject_reason] ?? CYCLE_REASON.review) : null
  const type = TYPE[item.type] ?? TYPE.bug
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="inline-flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
          <Icon name={type.icon} size={11} aria-hidden="true" />
          {item.key}
        </span>
        <StatusBadge status={item.status} />
      </div>
      <p className="text-[13px] font-medium leading-snug text-foreground">{item.title}</p>
      <div className="space-y-1 pt-0.5">
        {item.pinned && (
          <HoverRow icon={item.pin_locked ? 'lock' : 'pin'}>
            {item.pin_locked ? 'Pinned by a CTO or Admin — only they can unpin it' : 'Pinned'}
          </HoverRow>
        )}
        {reason && (
          <HoverRow icon={reason.icon}>
            <span className="text-foreground">{reason.label}</span>
            <RejectComment item={item} />
          </HoverRow>
        )}
        {item.cycle_number >= 2 && <HoverRow icon="refresh-cw">Cycle {item.cycle_number}</HoverRow>}
        {item.recurrence_count > 1 && <HoverRow icon="repeat">Reported {item.recurrence_count} times</HoverRow>}
        {item.is_tech_debt && <HoverRow icon={TECH_DEBT.icon}>{TECH_DEBT.label}</HoverRow>}
        {item.due_date && (
          <HoverRow icon="calendar">
            Due {formatDay(item.due_date)}
            {item.dueState !== 'none' && (
              <span className={cn(item.dueState === 'overdue' ? 'text-red-600 dark:text-red-400' : 'text-amber-700 dark:text-amber-300')}>
                {' '}· {dueLabel(item).toLowerCase()}
              </span>
            )}
          </HoverRow>
        )}
        <HoverRow icon={item.container?.kind === 'stream' ? 'waves' : item.container ? 'package' : 'inbox'}>
          {item.project?.name}{' · '}{item.container ? item.container.name : 'Backlog'}
        </HoverRow>
        <HoverRow icon="user-check">
          {item.assignee ? (
            <span className="inline-flex items-center gap-1">
              Assigned to <Avatar user={item.assignee} size={14} /> {item.assignee.name}
            </span>
          ) : 'Unassigned'}
        </HoverRow>
        {item.reporter && (
          <HoverRow icon="user-pen">
            <span className="inline-flex items-center gap-1">
              Reported by <Avatar user={item.reporter} size={14} /> {item.reporter.name}
            </span>
          </HoverRow>
        )}
        {item.labels.length > 0 && (
          <HoverRow icon="tag">
            <span className="flex flex-wrap gap-1">
              {item.labels.map((l) => <LabelChip key={l.name} label={l} />)}
            </span>
          </HoverRow>
        )}
        {item.created_at && <HoverRow icon="clock">Opened {relTime(item.created_at)}</HoverRow>}
      </div>
    </div>
  )
}

/** Opens the details after a short hover or on keyboard focus; portaled, viewport-clamped. */
function useHoverDetails() {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const ref = useRef(null)
  const timer = useRef(null)

  const place = useCallback(() => {
    const rect = ref.current?.getBoundingClientRect()
    if (!rect) return
    const pad = 12
    const left = Math.max(pad, Math.min(rect.left, window.innerWidth - HOVER_WIDTH - pad))
    const below = window.innerHeight - rect.bottom - pad >= HOVER_HEIGHT
    setPos({ top: below ? rect.bottom + 6 : Math.max(pad, rect.top - HOVER_HEIGHT - 6), left })
  }, [])

  const show = useCallback(() => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => { place(); setOpen(true) }, 400)
  }, [place])
  const hide = useCallback(() => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setOpen(false), 120)
  }, [])
  const close = useCallback(() => { clearTimeout(timer.current); setOpen(false) }, [])

  useEffect(() => () => clearTimeout(timer.current), [])
  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  return { open, pos, ref, show, hide, close, keep: () => clearTimeout(timer.current) }
}

/** A board card. `dragging` suppresses the hover details. */
export function WorkItemCard({ item: raw, onOpen, dragging = false, className, buttonProps = {} }) {
  const item = normalize(raw)
  const hover = useHoverDetails()
  useEffect(() => { if (dragging) hover.close() }, [dragging]) // eslint-disable-line react-hooks/exhaustive-deps

  const details = hover.open && !dragging ? createPortal(
    <div
      role="tooltip"
      data-testid="work-item-details"
      className="fixed z-[9999] rounded-lg border border-border bg-card p-3.5 shadow-lg"
      style={{ top: hover.pos.top, left: hover.pos.left, width: HOVER_WIDTH }}
      onMouseEnter={hover.keep}
      onMouseLeave={hover.hide}
    >
      <HoverDetails item={item} />
    </div>,
    document.body,
  ) : null

  const open = () => { hover.close(); onOpen?.(raw) }
  const label = `${item.key} ${item.title}`

  return (
    <div
      ref={hover.ref}
      onMouseEnter={hover.show}
      onMouseLeave={hover.hide}
      className={cn('w-full', className)}
      data-testid="work-item"
      data-item-id={item.id}
    >
      <button
        type="button"
        onClick={open}
        onFocus={hover.show}
        onBlur={hover.hide}
        aria-label={label}
        className="w-full rounded text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
        {...buttonProps}
      >
        {(item.container || item.is_release_blocker) && (
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <PlacementChip placement={item.container} className="border-transparent bg-transparent px-0" />
            {item.is_release_blocker && <BlockerPill />}
          </div>
        )}
        <div className="mb-1.5 line-clamp-2 text-[12.5px] font-medium leading-snug text-zinc-900 dark:text-zinc-100">
          {item.title}
        </div>
        <InlineLabels labels={item.labels} className="mb-2" />
        <div className="flex items-center gap-2">
          <ProjectChip project={item.project} className="flex-1" />
          <span className="flex shrink-0 items-center gap-1.5">
            <Markers item={item} />
            <PriorityGlyph priority={item.priority} />
            <Assignee user={item.assignee} />
          </span>
        </div>
      </button>
      {details}
    </div>
  )
}
