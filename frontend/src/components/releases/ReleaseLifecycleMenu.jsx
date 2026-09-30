import React, { useState } from 'react'
import { Dropdown, DropdownItem, DropdownLabel, DropdownSep } from '../ui/Dropdown'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { releasesApi } from '../../lib/api'
import { RELEASE_STATUS, releaseTransitionLabel } from '../../lib/constants'
import { ReleaseLifecycleBadge } from './ReleaseMarkers'

// The release's lifecycle badge as a menu of the moves the API allows
// (`allowed_transitions`, FR-50). Released is never here — that's Ship.
// Cancelling asks first: open items move to the backlog.
export function ReleaseLifecycleMenu({ release, onChanged, toast }) {
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [busy, setBusy] = useState(false)
  const moves = release.allowed_transitions ?? []
  const forward = moves.filter((s) => s !== 'cancelled')
  const openCount = release.open_issues ?? 0

  async function move(to) {
    setBusy(true)
    try {
      const res = to === 'cancelled'
        ? await releasesApi.cancel(release.id)
        : await releasesApi.setStatus(release.id, to)
      onChanged?.(res.data)
      toast?.({ title: `${release.version} is now ${RELEASE_STATUS[to]?.label ?? to}` })
      setConfirmCancel(false)
    } catch (err) {
      toast?.error(err.response?.data?.detail || 'Could not change the release status.')
    } finally {
      setBusy(false)
    }
  }

  if (moves.length === 0) return <ReleaseLifecycleBadge status={release.status} />

  return (
    <>
      <Dropdown
        width={240}
        trigger={
          <button
            type="button"
            aria-label={`Status: ${RELEASE_STATUS[release.status]?.label}. Change status`}
            className="inline-flex items-center gap-1 rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            disabled={busy}
          >
            <ReleaseLifecycleBadge status={release.status} />
            <Icon name="chevron-down" size={12} className="text-muted-foreground" />
          </button>
        }
      >
        {({ close }) => (
          <>
            <DropdownLabel>Move release</DropdownLabel>
            {forward.map((to) => (
              <DropdownItem key={to} onClick={() => { close(); move(to) }}>
                <span className="flex flex-1 items-center justify-between gap-2">
                  {releaseTransitionLabel(release.status, to)}
                  <ReleaseLifecycleBadge status={to} size="sm" />
                </span>
              </DropdownItem>
            ))}
            {moves.includes('cancelled') && (
              <>
                {forward.length > 0 && <DropdownSep />}
                <DropdownItem destructive onClick={() => { close(); setConfirmCancel(true) }}>
                  <span className="flex items-center gap-2"><Icon name="ban" size={14} /> Cancel release…</span>
                </DropdownItem>
              </>
            )}
          </>
        )}
      </Dropdown>

      <Dialog open={confirmCancel} onClose={busy ? undefined : () => setConfirmCancel(false)} title={`Cancel ${release.version}?`} size="sm">
        <div className="p-5 space-y-4 text-sm">
          <p>
            A cancelled release is final and won’t ship.
            {openCount > 0
              ? <> Its <b>{openCount}</b> open item{openCount === 1 ? '' : 's'} move to the backlog as To do, keeping their assignees.</>
              : ' It has no open items.'}
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirmCancel(false)} disabled={busy}>Keep it</Button>
            <Button variant="destructive" loading={busy} onClick={() => move('cancelled')}>Cancel release</Button>
          </div>
        </div>
      </Dialog>
    </>
  )
}
