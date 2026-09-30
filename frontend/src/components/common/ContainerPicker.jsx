import React from 'react'
import { cn } from '../../lib/cn'
import { CONTAINER_KIND, RELEASE_STATUS } from '../../lib/constants'
import { useContainers } from '../../hooks/useContainers'
import { Icon } from '../ui/Icon'
import { Select, SelectItem } from '../ui/Select'

const BACKLOG = '__backlog__'

function Option({ icon, label, hint }) {
  return (
    <span className="inline-flex items-center gap-2 min-w-0">
      <Icon name={icon} size={14} className="text-muted-foreground shrink-0" />
      <span className="truncate">{label}</span>
      {hint && <span className="text-[11px] text-muted-foreground shrink-0">{hint}</span>}
    </span>
  )
}

/**
 * Where an item lives (08a, FR-03/FR-18/FR-25): the backlog, the project's
 * Stream, or one of its open Releases — one decision, one control. Used by
 * the create form, triage Accept, the item sidebar, and the backlog bulk bar.
 *
 * `value` is a container id or `null` for the backlog; `onChange` gets the same.
 * A current container that no longer takes items (a released or cancelled
 * release) is still listed so the control can show it. `allowBacklog={false}`
 * drops the backlog option (bulk move: the items are already there);
 * `allowStream={false}` too leaves releases only (the item sidebar, 2026-09-30).
 */
export function ContainerPicker({
  projectId,
  value,
  onChange,
  allowBacklog = true,
  allowStream = true,
  disabled = false,
  className,
  placeholder = 'Choose where it goes',
}) {
  const { streamId, releases, openReleases } = useContainers(projectId)

  const current = value != null ? releases.find((r) => r.id === value) : null
  const listed = current && !openReleases.includes(current) ? [...openReleases, current] : openReleases

  const selected = value == null ? (allowBacklog ? BACKLOG : null) : String(value)

  return (
    <Select
      value={selected}
      onChange={(v) => onChange(v === BACKLOG ? null : Number(v))}
      disabled={disabled || !projectId}
      placeholder={placeholder}
      className={cn('min-w-0', className)}
    >
      {allowBacklog && (
        <SelectItem value={BACKLOG}>
          <Option icon={CONTAINER_KIND.backlog.icon} label="Backlog" hint="not planned yet" />
        </SelectItem>
      )}
      {allowStream && streamId != null && (
        <SelectItem value={String(streamId)}>
          <Option icon={CONTAINER_KIND.stream.icon} label="Stream" hint="ships when Done" />
        </SelectItem>
      )}
      {listed.map((r) => (
        <SelectItem key={r.id} value={String(r.id)}>
          <Option icon={CONTAINER_KIND.release.icon} label={r.version} hint={RELEASE_STATUS[r.status]?.label} />
        </SelectItem>
      ))}
    </Select>
  )
}
