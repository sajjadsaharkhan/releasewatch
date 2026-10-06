import React, { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { Select, SelectItem } from '../ui/Select'
import { useContainers } from '../../hooks/useContainers'
import { useBacklogCategories } from '../../hooks/useBacklogCategories'
import { BacklogCategoryBadge } from '../common/BacklogCategoryBadge'
import { projectsApi } from '../../lib/api'
import { CONTAINER_KIND, RELEASE_STATUS } from '../../lib/constants'

const DEFAULT_CATEGORY = '__default__'
// Projects carry no colour of their own — a stable hue per id keeps the square recognisable.
const HUES = [212, 152, 32, 340, 268, 188, 12, 96]
const hueOf = (id) => HUES[Number(id) % HUES.length]

/** Where an item is now: `backlog`, `stream` or `release`. */
export function placementOf(issue) {
  if (issue.release_id == null) return 'backlog'
  return issue.container_kind === 'stream' ? 'stream' : 'release'
}

const currentPlace = (issue) => {
  if (issue.release_id == null) return 'backlog'
  return issue.container_kind === 'stream' ? 'stream' : `release:${issue.release_id}`
}

function ProjectSquare({ project, size = 18 }) {
  return (
    <span
      aria-hidden="true"
      className="inline-flex shrink-0 items-center justify-center rounded-[5px] text-[10px] font-semibold text-white"
      style={{ width: size, height: size, background: `hsl(${hueOf(project.id)} 60% 45%)` }}
    >
      {(project.name || '?').slice(0, 1).toUpperCase()}
    </span>
  )
}

/** Placement choices in the chosen project: Backlog (+category), Stream, open releases. */
function PlacementList({ projectId, placement, onPlacement, category, onCategory, exclude = null }) {
  const { streamId, openReleases, isLoading } = useContainers(projectId)
  const { categories } = useBacklogCategories(projectId)

  if (!projectId) {
    return (
      <div className="flex h-full min-h-[10rem] flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-border px-4 text-center">
        <Icon name="arrow-left" size={16} aria-hidden="true" className="text-muted-foreground" />
        <p className="text-[13px] text-muted-foreground">Pick a project first — its placements show up here.</p>
      </div>
    )
  }
  const rows = [
    { id: 'backlog', releaseId: null, icon: CONTAINER_KIND.backlog.icon, label: 'Backlog', hint: 'not planned yet' },
    streamId != null && { id: 'stream', releaseId: streamId, icon: CONTAINER_KIND.stream.icon, label: 'Stream', hint: 'ships when Done' },
  ].filter((c) => c && c.id !== exclude)
  const releases = openReleases.filter((r) => `release:${r.id}` !== exclude).map((r) => ({
    id: `release:${r.id}`, releaseId: r.id, icon: CONTAINER_KIND.release.icon, label: r.version,
    hint: RELEASE_STATUS[r.status]?.label, mono: true,
  }))

  const Row = ({ c }) => {
    const on = placement?.id === c.id
    return (
      <button
        type="button"
        role="radio"
        aria-checked={on}
        onClick={() => onPlacement(c)}
        className={cn(
          'flex w-full items-center gap-2.5 px-3 py-2 text-left text-[13px] hover:bg-muted',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
          on && 'bg-blue-50 dark:bg-blue-950/30',
        )}
      >
        <Icon name={on ? 'circle-dot' : 'circle'} size={14} aria-hidden="true" className={on ? 'text-blue-600 dark:text-blue-400' : 'text-muted-foreground'} />
        <Icon name={c.icon} size={14} aria-hidden="true" className="text-muted-foreground" />
        <span className={cn(c.mono && 'font-mono')}>{c.label}</span>
        <span className="ml-auto text-[11px] text-muted-foreground">{c.hint}</span>
      </button>
    )
  }

  return (
    <div className="space-y-3">
      <div role="radiogroup" aria-label="Placement" className={cn('overflow-hidden rounded-lg border border-border', isLoading && 'opacity-60')}>
        {rows.length > 0 && <div className="divide-y divide-border">{rows.map((c) => <Row key={c.id} c={c} />)}</div>}
        <div role="group" aria-label="Releases" className={cn(rows.length > 0 && 'border-t border-border')}>
          <div className="bg-muted/40 px-3 pb-1 pt-2 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
            Releases <span className="font-normal normal-case tracking-normal">· open only</span>
          </div>
          {releases.length > 0
            ? <div className="divide-y divide-border border-t border-border">{releases.map((c) => <Row key={c.id} c={c} />)}</div>
            : <p className="border-t border-border px-3 py-2 text-[12px] text-muted-foreground">No open release in this project.</p>}
        </div>
      </div>
      {placement?.id === 'backlog' && (
        <div>
          <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
            Backlog category <span className="font-normal">(optional)</span>
          </label>
          <Select value={category} onChange={onCategory} className="h-9 text-[13px]">
            <SelectItem value={DEFAULT_CATEGORY}><span className="text-muted-foreground">Default</span></SelectItem>
            {categories.filter((c) => !c.is_default).map((c) => (
              <SelectItem key={c.id} value={String(c.id)}><BacklogCategoryBadge category={c} /></SelectItem>
            ))}
          </Select>
        </div>
      )}
    </div>
  )
}

function Summary({ issue, project, placement, category, categories }) {
  const cat = placement?.id === 'backlog' && category !== DEFAULT_CATEGORY
    ? categories.find((c) => String(c.id) === category)?.name : null
  return (
    <p className="flex min-w-0 items-center gap-1.5 text-[12px] text-muted-foreground" aria-live="polite">
      <span className="truncate">{issue.project_name}</span>
      <Icon name="arrow-right" size={12} aria-hidden="true" />
      {project
        ? <span className="truncate font-medium text-foreground">{project.name}{placement ? ` · ${placement.label}${cat ? ` · ${cat}` : ''}` : ''}</span>
        : <span>choose a destination</span>}
    </p>
  )
}

/**
 * **Move…** (the item page's ⋯ menu): re-place an open item, in its own project
 * by default — Backlog (with an optional category), the Stream, or another open
 * release. The Project field above is pre-filled with the current project;
 * picking another one swaps the list for that project's placements and moves
 * the item there (POST /move). `onMove(patch, message)` applies an in-project
 * PATCH and `onMoveProject(projectId, placement, message)` a cross-project move;
 * both resolve truthy on success.
 */
export function MoveDialog({ issue, open, onClose, onMove, onMoveProject }) {
  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list().then((r) => r.data?.projects || r.data || []),
    staleTime: 5 * 60 * 1000,
  })
  const [projectId, setProjectId] = useState(issue.project_id)
  const [placement, setPlacement] = useState(null)
  const [category, setCategory] = useState(DEFAULT_CATEGORY)
  const [saving, setSaving] = useState(false)
  const movable = projects.filter((p) => !p.archived_at)
  const project = projects.find((p) => p.id === projectId) ?? null
  const other = String(projectId) !== String(issue.project_id)
  const { categories } = useBacklogCategories(projectId)

  useEffect(() => {
    if (!open) return
    setProjectId(issue.project_id)
    setPlacement(null)
    setCategory(DEFAULT_CATEGORY)
  }, [open, issue.project_id])

  const pickProject = (id) => { setProjectId(id); setPlacement(null); setCategory(DEFAULT_CATEGORY) }
  const resetProject = () => pickProject(issue.project_id)

  async function submit() {
    if (!placement) return
    const isBacklog = placement.id === 'backlog'
    const chosen = isBacklog && category !== DEFAULT_CATEGORY
      ? categories.find((c) => String(c.id) === category)
      : null
    const where = `${placement.label}${chosen ? ` · ${chosen.name}` : ''}`
    setSaving(true)
    let ok
    if (other) {
      ok = await onMoveProject(
        projectId,
        { releaseId: placement.releaseId, backlogCategoryId: chosen?.id },
        `Moved to ${project?.name ?? 'the project'} · ${where}`,
      )
    } else {
      const defaultCategory = categories.find((c) => c.is_default)
      const target = chosen ?? defaultCategory
      const patch = isBacklog
        ? { release_id: null, ...(target ? { backlog_category_id: target.id } : {}) }
        : { release_id: placement.releaseId }
      ok = await onMove(patch, isBacklog ? `Moved to the backlog${chosen ? ` · ${chosen.name}` : ''}` : `Moved to ${placement.label}`)
    }
    setSaving(false)
    if (ok) onClose()
  }

  const leavingRelease = issue.is_release_blocker
    && (other || (placement && !placement.id.startsWith('release:')))

  return (
    <Dialog open={open} onClose={onClose} title={`Move ${issue.key}`} size="sm">
      <div className="space-y-3 px-5 pb-4 pt-3">
        <div>
          <label className="mb-1.5 flex items-center justify-between text-xs font-medium text-muted-foreground">
            Project
            {other && (
              <button type="button" onClick={resetProject} className="font-normal hover:text-foreground">
                Reset
              </button>
            )}
          </label>
          <Select value={String(projectId)} onChange={(v) => pickProject(Number(v))} className="h-9 text-[13px]">
            {movable.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                <span className="flex items-center gap-2">
                  <ProjectSquare project={p} size={16} />
                  {p.name}
                  {String(p.id) === String(issue.project_id) && (
                    <span className="text-[11px] text-muted-foreground">· current</span>
                  )}
                </span>
              </SelectItem>
            ))}
          </Select>
        </div>

        <PlacementList
          projectId={projectId}
          placement={placement}
          onPlacement={setPlacement}
          category={category}
          onCategory={setCategory}
          exclude={other ? null : currentPlace(issue)}
        />

        {leavingRelease && (
          <p className="text-[12px] text-muted-foreground">
            {other
              ? 'Changing project also clears the release-blocker flag and the backlog category.'
              : 'It stops being a release blocker when it leaves the release.'}
          </p>
        )}
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-3">
        <div className="min-w-0">
          <Summary issue={issue} project={project} placement={placement} category={category} categories={categories} />
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" disabled={!placement} loading={saving} onClick={submit}>Move</Button>
        </div>
      </div>
    </Dialog>
  )
}
