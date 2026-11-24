import React, { useEffect, useState } from 'react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { STATUS } from '../../lib/constants'
import { releasesApi } from '../../lib/api'
import { GoNogoBadge } from './GoNogoPanel'

// FR-53 — the ship notice, built from GET /ship-preview: the go/no-go decision,
// two lines — what goes to production (every Verified item becomes Done, BR-67)
// and what goes to the backlog, by status — and a confirm button that says what moves.
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
      onShipped?.(res.data, { production: preview?.to_production ?? 0, backlog: preview?.total_to_backlog ?? 0 })
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not ship this release.')
    } finally {
      setShipping(false)
    }
  }

  const moving = preview?.total_to_backlog ?? 0
  const toProduction = preview?.to_production ?? 0
  // The server's order (FR-53: "2 To do, 1 In review, 1 Rejected").
  const toBacklog = Object.entries(preview?.to_backlog ?? {}).filter(([, n]) => n > 0)
  const items = (n) => `${n} item${n === 1 ? '' : 's'}`
  const label = moving === 0
    ? `Ship ${release?.version ?? ''}`
    : `Ship and move ${items(moving)} to the backlog`

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
                A no-go is on record. Shipping is still possible — make sure that’s intended.
              </p>
            )}

            <div className="space-y-2.5">
              <p className="font-medium" data-testid="ship-to-production">
                <span className="tabular-nums">{items(toProduction)}</span> go{toProduction === 1 ? 'es' : ''} to production
                {toProduction > 0 && <span className="font-normal text-muted-foreground"> — Verified items become Done.</span>}
              </p>
              {moving === 0 ? (
                <p className="text-muted-foreground" data-testid="ship-to-backlog">Nothing goes to the backlog.</p>
              ) : (
                <div data-testid="ship-to-backlog">
                  <p className="font-medium">
                    <span className="tabular-nums">{items(moving)}</span> go{moving === 1 ? 'es' : ''} to the backlog
                    <span className="font-normal text-muted-foreground">
                      {' '}({toBacklog.map(([st, n]) => `${n} ${STATUS[st]?.label ?? st}`).join(', ')})
                    </span>
                  </p>
                  <p className="mt-1 text-muted-foreground">
                    They land as <b>To do</b> in category <b>Default</b>, keeping their assignees. Their cycles are cleared.
                  </p>
                </div>
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
