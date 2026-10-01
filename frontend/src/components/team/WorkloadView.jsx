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
import { PriorityGlyph, ProjectChip } from '../common/WorkItemCard'
import { PIN_ICON, TypeMark } from '../queue/QueueMarks'

// The Team page's Workload view (slice 11, FR-43) — CTO and Admin only. One row
// per active assignable person, in name order: what they have In progress, the
// next three items in their queue, and open/pinned counts. A row opens their
// board (/u/:username/work), where reorder and pin live. People are never
// ranked or scored (PRD non-goal) — the copy only describes.

// Person · In progress · Up next — shared by the rows and their skeletons.
const ROW_GRID = 'grid grid-cols-1 gap-4 rounded-xl border border-border bg-card p-4 lg:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_minmax(0,1fr)]'

function ItemLine({ item, index }) {
  return (
    <li className="flex min-w-0 items-center gap-2">
      {index !== undefined && (
        item.pinned ? (
          <Tooltip content={item.pin_locked ? 'Pinned by a CTO or Admin — locked' : 'Pinned'}>
            <span className={cn('flex w-4 shrink-0 justify-center', PIN_ICON)}>
              <Icon name={item.pin_locked ? 'lock' : 'pin'} size={12} fill={item.pin_locked ? 'none' : 'currentColor'} aria-label={item.pin_locked ? 'Pinned, locked' : 'Pinned'} />
            </span>
          </Tooltip>
        ) : (
          <span className="w-4 shrink-0 text-center text-xs font-semibold tabular-nums text-zinc-400 dark:text-zinc-500">
            {index + 1}
          </span>
        )
      )}
      <TypeMark type={item.type} />
      <Link
        to={`/issue/${issueSlug(item)}`}
        onClick={(e) => e.stopPropagation()}
        className="min-w-0 truncate rounded text-[13px] text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        title={item.title}
      >
        {item.title}
      </Link>
      <span className="hidden shrink-0 font-mono text-[11px] text-muted-foreground xl:inline">{item.key}</span>
      <ProjectChip project={item.project} className="ml-auto hidden max-w-[9rem] shrink-0 sm:inline-flex" />
      <PriorityGlyph priority={item.priority} />
    </li>
  )
}

function ItemList({ title, items, empty, numbered = false, testId }) {
  return (
    <div className="min-w-0" data-testid={testId}>
      <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      {items.length === 0 ? (
        <p className="text-[13px] italic text-muted-foreground">{empty}</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((item, i) => <ItemLine key={item.id} item={item} index={numbered ? i : undefined} />)}
        </ul>
      )}
    </div>
  )
}

function PersonRow({ row }) {
  const navigate = useNavigate()
  const { user, counts } = row
  const board = `/u/${user.username}/work`
  return (
    <li
      data-testid="workload-row"
      data-user-id={user.id}
      onClick={() => navigate(board)}
      className={cn(ROW_GRID, 'cursor-pointer shadow-sm transition-[border-color,box-shadow] hover:border-zinc-300 hover:shadow dark:hover:border-zinc-700')}
    >
      <div className="flex min-w-0 items-start gap-3">
        <Avatar user={user} size={36} />
        <div className="min-w-0 space-y-1.5">
          <Link
            to={board}
            onClick={(e) => e.stopPropagation()}
            className="block truncate rounded text-sm font-semibold hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={`Open ${user.name}’s board`}
          >
            {user.name}
          </Link>
          <RoleBadge role={user.role} />
          <p className="flex items-center gap-2 text-xs text-muted-foreground" data-testid="workload-counts">
            <span><span className="font-semibold tabular-nums text-foreground">{counts.open}</span> open</span>
            <span aria-hidden="true">·</span>
            <span className="inline-flex items-center gap-1">
              <Icon name="pin" size={11} className={counts.pinned ? PIN_ICON : undefined} aria-hidden="true" />
              <span className="font-semibold tabular-nums text-foreground">{counts.pinned}</span> pinned
            </span>
          </p>
        </div>
      </div>
      <ItemList title="In progress" items={row.in_progress} empty="Nothing in progress" testId="workload-in-progress" />
      <ItemList title="Up next" items={row.next} empty="Queue is empty" numbered testId="workload-next" />
    </li>
  )
}

function RowSkeleton() {
  return (
    <li className={ROW_GRID}>
      <div className="flex gap-3">
        <div className="h-9 w-9 rounded-full bg-zinc-200 animate-pulse dark:bg-zinc-700" />
        <div className="space-y-2">
          <div className="h-3.5 w-28 rounded bg-zinc-200 animate-pulse dark:bg-zinc-700" />
          <div className="h-3 w-16 rounded bg-zinc-200 animate-pulse dark:bg-zinc-700" />
        </div>
      </div>
      {[0, 1].map((k) => (
        <div key={k} className="space-y-2">
          <div className="h-2.5 w-20 rounded bg-zinc-200 animate-pulse dark:bg-zinc-700" />
          <div className="h-3 w-full rounded bg-zinc-200 animate-pulse dark:bg-zinc-700" />
          <div className="h-3 w-2/3 rounded bg-zinc-200 animate-pulse dark:bg-zinc-700" />
        </div>
      ))}
    </li>
  )
}

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
        <ul className="space-y-3" aria-busy="true">
          {[0, 1, 2].map((k) => <RowSkeleton key={k} />)}
        </ul>
      ) : rows.length === 0 ? (
        filtered
          ? <p className="py-12 text-center text-sm text-muted-foreground">No one matches these filters.</p>
          : <Empty icon="users" title="No one to show" body="Active team members who can be assigned work appear here." />
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => <PersonRow key={row.user.id} row={row} />)}
        </ul>
      )}
    </div>
  )
}
