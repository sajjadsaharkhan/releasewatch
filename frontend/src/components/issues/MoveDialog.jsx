import React, { useEffect, useState } from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { Select, SelectItem } from '../ui/Select'
import { useContainers } from '../../hooks/useContainers'
import { useBacklogCategories } from '../../hooks/useBacklogCategories'
import { BacklogCategoryBadge } from '../common/BacklogCategoryBadge'
import { CONTAINER_KIND, RELEASE_STATUS } from '../../lib/constants'

const DEFAULT_CATEGORY = '__default__'

/** Where an item is now: `backlog`, `stream` or `release`. */
export function placementOf(issue) {
  if (issue.release_id == null) return 'backlog'
  return issue.container_kind === 'stream' ? 'stream' : 'release'
}

function Choice({ choice, selected, onSelect }) {
  const on = selected === choice.id
  return (
    <button
      type="button"
      role="radio"
      aria-checked={on}
      onClick={() => onSelect(choice.id)}
      className={cn(
        'w-full flex items-center gap-2.5 px-3 py-2 text-left text-[13px] hover:bg-muted',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
        on && 'bg-blue-50 dark:bg-blue-950/30',
      )}
    >
      <Icon
        name={on ? 'circle-dot' : 'circle'}
        size={14}
        aria-hidden="true"
        className={on ? 'text-blue-600 dark:text-blue-400' : 'text-muted-foreground'}
      />
      <Icon name={choice.icon} size={14} aria-hidden="true" className="text-muted-foreground" />
      <span className={cn(choice.mono && 'font-mono')}>{choice.label}</span>
      <span className="ml-auto text-[11px] text-muted-foreground">{choice.hint}</span>
    </button>
  )
}

/**
 * **Move…** (the item page's ⋯ menu): send an open item to the backlog, the
 * Stream, or another open release — one grouped list of destinations, with the
 * item's current place left out. Backlog takes an optional category (none =
 * the project's Default). `onMove(patch, message)` applies the PATCH and
 * resolves truthy on success.
 */
export function MoveDialog({ issue, open, onClose, onMove }) {
  const { streamId, openReleases } = useContainers(issue.project_id)
  const { categories } = useBacklogCategories(issue.project_id)
  const [choice, setChoice] = useState(null)
  const [category, setCategory] = useState(DEFAULT_CATEGORY)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setChoice(null)
    setCategory(DEFAULT_CATEGORY)
  }, [open])

  const place = placementOf(issue)
  const general = [
    place !== 'backlog' && {
      id: 'backlog', icon: CONTAINER_KIND.backlog.icon, label: 'Backlog', hint: 'not planned yet',
    },
    place !== 'stream' && streamId != null && {
      id: 'stream', icon: CONTAINER_KIND.stream.icon, label: 'Stream', hint: 'ships when Done',
    },
  ].filter(Boolean)
  const releases = openReleases
    .filter((r) => r.id !== issue.release_id)
    .map((r) => ({
      id: `release:${r.id}`, releaseId: r.id, icon: CONTAINER_KIND.release.icon,
      label: r.version, hint: RELEASE_STATUS[r.status]?.label, mono: true,
    }))
  const all = [...general, ...releases]
  const defaultCategory = categories.find((c) => c.is_default)

  async function submit() {
    const picked = all.find((c) => c.id === choice)
    if (!picked) return
    let patch
    let message
    if (picked.id === 'backlog') {
      const chosen = category === DEFAULT_CATEGORY
        ? defaultCategory
        : categories.find((c) => String(c.id) === category)
      patch = { release_id: null, ...(chosen ? { backlog_category_id: chosen.id } : {}) }
      message = `Moved to the backlog${chosen ? ` · ${chosen.name}` : ''}`
    } else if (picked.id === 'stream') {
      patch = { release_id: streamId }
      message = 'Moved to the Stream'
    } else {
      patch = { release_id: picked.releaseId }
      message = `Moved to ${picked.label}`
    }
    setSaving(true)
    const ok = await onMove(patch, message)
    setSaving(false)
    if (ok) onClose()
  }

  return (
    <Dialog open={open} onClose={onClose} title={`Move ${issue.key}`} size="sm">
      <div className="px-5 pt-3 pb-5 space-y-3">
        <div role="radiogroup" aria-label="Destination" className="rounded-lg border border-border overflow-hidden">
          <div className="divide-y divide-border">
            {general.map((c) => <Choice key={c.id} choice={c} selected={choice} onSelect={setChoice} />)}
          </div>
          {releases.length > 0 ? (
            <div role="group" aria-label="Releases" className={cn(general.length > 0 && 'border-t border-border')}>
              <div className="flex items-center gap-1.5 px-3 pt-2 pb-1 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground bg-muted/40">
                Releases
                <span className="font-normal normal-case tracking-normal">· open only</span>
              </div>
              <div className="divide-y divide-border border-t border-border">
                {releases.map((c) => <Choice key={c.id} choice={c} selected={choice} onSelect={setChoice} />)}
              </div>
            </div>
          ) : (
            <p className={cn('px-3 py-2 text-[12px] text-muted-foreground', general.length > 0 && 'border-t border-border')}>
              No other open release in this project.
            </p>
          )}
        </div>

        {choice === 'backlog' && (
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Backlog category <span className="font-normal">(optional)</span>
            </label>
            <Select value={category} onChange={setCategory} className="h-9 text-[13px]">
              <SelectItem value={DEFAULT_CATEGORY}>
                <span className="text-muted-foreground">Default</span>
              </SelectItem>
              {categories.filter((c) => !c.is_default).map((c) => (
                <SelectItem key={c.id} value={String(c.id)}><BacklogCategoryBadge category={c} /></SelectItem>
              ))}
            </Select>
          </div>
        )}

        {issue.is_release_blocker && choice && !choice.startsWith('release:') && (
          <p className="text-[12px] text-muted-foreground">It stops being a release blocker when it leaves the release.</p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" disabled={!choice} loading={saving} onClick={submit}>Move</Button>
        </div>
      </div>
    </Dialog>
  )
}
