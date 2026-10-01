import React, { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { cn } from '../../lib/cn'
import { teamApi } from '../../lib/api'
import { ROLE } from '../../lib/constants'
import { issueSlug } from '../../lib/issueSlug'
import { TECH_ROLES } from '../../lib/roles'
import { useApp } from '../../hooks/useApp'
import { Avatar } from '../ui/Avatar'
import { RoleBadge } from '../ui/Badge'
import { Empty } from '../ui/Empty'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'
import { useToast } from '../ui/Toast'
import { FilterDropdown } from '../common/FilterDropdown'
import { PriorityGlyph } from '../common/WorkItemCard'
import { BlockerBadge, DueTag, PIN_ICON, TypeMark } from '../queue/QueueMarks'

// The Team page's Workload view (slice 11, FR-43) — CTO and Admin only. A card
// per active assignable person, in name order (chosen from prototype variant C,
// 2026-10-01): header with open/pinned counts, what they have In progress
// ("Now"), the next three queue items, and how much more is waiting. A card
// opens their board (/u/:username/work), where reorder and pin live. People are
// never ranked or scored (PRD non-goal) — the copy only describes.

// `relative` is load-bearing: the cards' `sr-only` labels are absolutely
// positioned, and without a positioned ancestor inside <main> they escape its
// overflow and make the whole document scroll.
const CARD = 'relative flex flex-col rounded-xl border border-border bg-card shadow-sm'
const LABEL = 'mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide'

function ItemLink({ item, className }) {
  return (
    <Link
      to={`/issue/${issueSlug(item)}`}
      onClick={(e) => e.stopPropagation()}
      title={`${item.key} · ${item.title} · ${item.project.name}`}
      className={cn('min-w-0 truncate rounded text-[13px] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', className)}
    >
      {item.title}
    </Link>
  )
}

function PinOrNumber({ item, n }) {
  if (!item.pinned) {
    return <span className="w-4 shrink-0 text-center text-xs font-semibold tabular-nums text-zinc-400 dark:text-zinc-500">{n}</span>
  }
  return (
    <Tooltip content={item.pin_locked ? 'Pinned by a CTO or Admin — locked' : 'Pinned'}>
      <span className={cn('flex w-4 shrink-0 justify-center', PIN_ICON)}>
        <Icon name={item.pin_locked ? 'lock' : 'pin'} size={12} fill={item.pin_locked ? 'none' : 'currentColor'} aria-label={item.pin_locked ? 'Pinned, locked' : 'Pinned'} />
      </span>
    </Tooltip>
  )
}

function NowList({ items }) {
  const busy = items.length > 0
  return (
    <div className="px-4 pt-3" data-testid="workload-in-progress">
      <p className={cn(LABEL, 'text-indigo-600 dark:text-indigo-400')}>
        <span className="relative flex h-1.5 w-1.5" aria-hidden="true">
          {busy && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-60 motion-reduce:hidden" />}
          <span className={cn('relative inline-flex h-1.5 w-1.5 rounded-full', busy ? 'bg-indigo-500' : 'bg-zinc-300 dark:bg-zinc-600')} />
        </span>
        Now
      </p>
      {busy ? (
        <ul className="space-y-1.5 border-l-2 border-indigo-200 pl-2.5 dark:border-indigo-900">
          {items.map((item) => (
            <li key={item.id} className="relative flex min-w-0 items-center gap-1.5">
              <TypeMark type={item.type} />
              <ItemLink item={item} className="font-medium text-foreground" />
              <BlockerBadge item={item} />
              <PriorityGlyph priority={item.priority} className="ml-auto" />
            </li>
          ))}
        </ul>
      ) : <p className="text-[12.5px] italic text-muted-foreground">Nothing in progress</p>}
    </div>
  )
}

function NextList({ items }) {
  return (
    <div className="flex-1 px-4 pb-3 pt-3" data-testid="workload-next">
      <p className={cn(LABEL, 'text-muted-foreground')}>Up next</p>
      {items.length > 0 ? (
        <ul className="space-y-1.5">
          {items.map((item, i) => (
            <li key={item.id} className="relative flex min-w-0 items-center gap-1.5">
              <PinOrNumber item={item} n={i + 1} />
              <TypeMark type={item.type} />
              <ItemLink item={item} className="text-foreground/90" />
              {item.due_state !== 'none' && <span className="shrink-0 whitespace-nowrap"><DueTag item={item} /></span>}
              <PriorityGlyph priority={item.priority} className="ml-auto" />
            </li>
          ))}
        </ul>
      ) : <p className="text-[12.5px] italic text-muted-foreground">Queue is empty</p>}
    </div>
  )
}

function PersonCard({ row }) {
  const navigate = useNavigate()
  const { user, counts } = row
  const board = `/u/${user.username}/work`
  const more = Math.max(0, counts.open - row.in_progress.length - row.next.length)
  return (
    <li
      data-testid="workload-row"
      data-user-id={user.id}
      onClick={() => navigate(board)}
      className={cn(CARD, 'cursor-pointer transition-[border-color,box-shadow] hover:border-zinc-300 hover:shadow dark:hover:border-zinc-700')}
    >
      <div className="flex items-center gap-3 px-4 pt-4">
        <Avatar user={user} size={36} />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center justify-between gap-2">
            <Link
              to={board}
              onClick={(e) => e.stopPropagation()}
              className="min-w-0 truncate rounded text-sm font-semibold hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`Open ${user.name}’s board`}
            >
              {user.name}
            </Link>
            <RoleBadge role={user.role} className="shrink-0" />
          </div>
          <p className="flex items-center gap-1.5 whitespace-nowrap text-xs text-muted-foreground" data-testid="workload-counts">
            <span><span className="font-semibold tabular-nums text-foreground">{counts.open}</span> open</span>
            <span aria-hidden="true">·</span>
            <span className="inline-flex items-center gap-1">
              <Icon name="pin" size={11} className={counts.pinned ? PIN_ICON : undefined} aria-hidden="true" />
              <span className="font-semibold tabular-nums text-foreground">{counts.pinned}</span> pinned
            </span>
          </p>
        </div>
      </div>
      <NowList items={row.in_progress} />
      <NextList items={row.next} />
      <div className="flex items-center justify-between border-t border-border px-4 py-2 text-xs text-muted-foreground">
        <span>{more > 0 ? `+${more} more in queue` : counts.open > 0 ? 'That’s the whole queue' : 'Nothing assigned'}</span>
        <span className="inline-flex items-center gap-1 font-medium text-foreground">
          Open board <Icon name="arrow-right" size={12} aria-hidden="true" />
        </span>
      </div>
    </li>
  )
}

const BAR = 'rounded bg-zinc-200 animate-pulse dark:bg-zinc-700'

function CardSkeleton() {
  return (
    <li className={cn(CARD, 'gap-4 p-4')}>
      <div className="flex items-center gap-3">
        <div className={cn(BAR, 'h-9 w-9 rounded-full')} />
        <div className="space-y-2">
          <div className={cn(BAR, 'h-3.5 w-28')} />
          <div className={cn(BAR, 'h-3 w-20')} />
        </div>
      </div>
      {[0, 1].map((k) => (
        <div key={k} className="space-y-2">
          <div className={cn(BAR, 'h-2.5 w-16')} />
          <div className={cn(BAR, 'h-3 w-full')} />
          <div className={cn(BAR, 'h-3 w-2/3')} />
        </div>
      ))}
    </li>
  )
}

const GRID = 'grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3'

/** `role` / `project` are URL-backed filters owned by the page. */
export function WorkloadView({ role, project, onFilter }) {
  const { projects = [] } = useApp()
  const { toast } = useToast()
  const query = useQuery({
    queryKey: ['team-workload', role || null, project || null],
    queryFn: () => teamApi.workload({ role: role || undefined, project_id: project || undefined })
      .then((res) => res.data ?? []),
  })
  useEffect(() => {
    if (query.isError) toast.error('Failed to load workload')
  }, [query.isError]) // eslint-disable-line react-hooks/exhaustive-deps
  const rows = query.isPending ? null : (query.data ?? [])

  const roleOptions = [{ value: '', label: 'All roles' }, ...TECH_ROLES.map((r) => ({ value: r, label: ROLE[r]?.label ?? r }))]
  const projectOptions = [{ value: '', label: 'All projects' }, ...projects.map((p) => ({ value: String(p.id), label: p.name }))]
  const roleLabel = roleOptions.find((o) => o.value === (role || ''))?.label ?? 'All roles'
  const projectLabel = projectOptions.find((o) => o.value === String(project || ''))?.label ?? `Project #${project}`
  const filtered = Boolean(role || project)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <FilterDropdown icon="user-round" label="Role" value={roleLabel} options={roleOptions} onChange={(v) => onFilter({ role: v })} />
        <FilterDropdown icon="folder" label="Working in" value={projectLabel} options={projectOptions} width={240} onChange={(v) => onFilter({ project: v })} />
        {filtered && (
          <button
            type="button"
            onClick={() => onFilter({ role: '', project: '' })}
            className="h-8 rounded-md px-2 text-[12px] text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Clear filters
          </button>
        )}
        <p className="ml-auto text-xs text-muted-foreground">Open someone’s board to reorder or pin.</p>
      </div>

      {rows === null ? (
        <ul className={GRID} aria-busy="true">
          {[0, 1, 2].map((k) => <CardSkeleton key={k} />)}
        </ul>
      ) : rows.length === 0 ? (
        filtered
          ? <p className="py-12 text-center text-sm text-muted-foreground">No one matches these filters.</p>
          : <Empty icon="users" title="No one to show" body="Active team members who can be assigned work appear here." />
      ) : (
        <ul className={GRID}>
          {rows.map((row) => <PersonCard key={row.user.id} row={row} />)}
        </ul>
      )}
    </div>
  )
}
