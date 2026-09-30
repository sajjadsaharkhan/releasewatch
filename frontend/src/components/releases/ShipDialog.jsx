import React, { useEffect, useState } from 'react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { StatusBadge } from '../ui/Badge'
import { releasesApi } from '../../lib/api'
import { GoNogoBadge } from './GoNogoPanel'

// FR-53 — the ship notice, built from GET /ship-preview: the go/no-go decision,
// what isn't Done by status, and a confirm button that says what will move.
export function ShipDialog({ open, release, onClose, onShipped }) {
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [shipping, setShipping] = useState(false)

  useEffect(() => {
    if (!open || !release) return
    setPreview(null); setError(null); setLoading(true)
    releasesApi.shipPreview(release.id)
      .then((res) => setPreview(res.data))
      .catch((err) => setError(err.response?.data?.detail || 'Could not load the ship notice.'))
      .finally(() => setLoading(false))
  }, [open, release])

  async function ship() {
    setShipping(true); setError(null)
    try {
      const res = await releasesApi.ship(release.id)
      onShipped?.(res.data, preview?.total_not_done ?? 0)
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not ship this release.')
    } finally {
      setShipping(false)
    }
  }

  const moving = preview?.total_not_done ?? 0
  // The server's order (FR-53: "3 To do, 1 In progress, 1 In review").
  const notDone = Object.entries(preview?.not_done ?? {}).filter(([, n]) => n > 0)
  const label = moving === 0
    ? `Ship ${release?.version ?? ''}`
    : `Ship and move ${moving} item${moving === 1 ? '' : 's'} to the backlog`

  return (
    <Dialog open={open} onClose={shipping ? undefined : onClose} title={`Ship ${release?.version ?? ''}`} size="md">
      <div className="p-5 space-y-4 text-sm">
        {loading && (
          <div className="flex items-center gap-2 text-muted-foreground" role="status">
            <Icon name="loader-2" size={14} className="animate-spin" /> Loading the ship notice…
          </div>
        )}
        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400">
            {error}
          </div>
        )}
        {preview && (
          <>
            <div className="flex items-center justify-between rounded-lg border border-border p-3">
              <div>
                <p className="text-xs text-muted-foreground">Go / no-go</p>
                {preview.go_nogo.note && (
                  <p className="mt-0.5 text-[13px] italic text-muted-foreground">“{preview.go_nogo.note}”</p>
                )}
              </div>
              <GoNogoBadge status={preview.go_nogo.status} />
            </div>
            {preview.go_nogo.status === 'blocked' && (
              <p className="flex items-start gap-2 rounded-lg bg-red-50 p-3 text-red-700 dark:bg-red-950/30 dark:text-red-400">
                <Icon name="alert-triangle" size={14} className="mt-0.5 shrink-0" />
                The CTO recorded a no-go. Shipping is still possible — make sure that’s intended.
              </p>
            )}

            <div>
              <p className="font-medium">
                {preview.done} Done item{preview.done === 1 ? '' : 's'} will be on production.
              </p>
              {moving === 0 ? (
                <p className="mt-1 text-muted-foreground">Every item is Done — nothing moves.</p>
              ) : (
                <>
                  <p className="mt-1 text-muted-foreground">
                    These aren’t Done and will move to the backlog as <b>To do</b> in category <b>Default</b>,
                    keeping their assignees. Their cycles are cleared.
                  </p>
                  <ul className="mt-2 flex flex-wrap gap-2" aria-label="Items that aren’t Done, by status">
                    {notDone.map(([s, n]) => (
                      <li key={s} className="inline-flex items-center gap-1.5">
                        <span className="tabular-nums font-semibold">{n}</span>
                        <StatusBadge status={s} />
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </>
        )}
        <div className="flex justify-end gap-2 pt-2 border-t border-border -mx-5 px-5 pt-4">
          <Button variant="outline" onClick={onClose} disabled={shipping}>Not yet</Button>
          <Button onClick={ship} loading={shipping} disabled={!preview}>
            <Icon name="rocket" size={14} />
            {label}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
