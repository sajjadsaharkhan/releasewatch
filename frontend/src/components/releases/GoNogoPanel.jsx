import React, { useState } from 'react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { Textarea } from '../ui/Textarea'
import { releasesApi } from '../../lib/api'
import { relTime } from '../../lib/relTime'

const GO_NOGO = {
  pending: { label: 'Pending', icon: 'circle-dashed', pill: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400' },
  approved: { label: 'Go', icon: 'thumbs-up', pill: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' },
  blocked: { label: 'No-go', icon: 'thumbs-down', pill: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' },
}

export function GoNogoBadge({ status, className }) {
  const t = GO_NOGO[status] ?? GO_NOGO.pending
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold', t.pill, className)}>
      <Icon name={t.icon} size={12} aria-hidden />
      {t.label}
    </span>
  )
}

// FR-52 — the decision on record, and (CTO/Admin, `go_nogo` in allowed_actions)
// a Go / No-go control with an optional note.
// `bare` drops the card frame, for use inside another surface (the release Details menu).
export function GoNogoPanel({ release, deciderName, onChange, toast, bare = false }) {
  const [deciding, setDeciding] = useState(null) // 'approved' | 'blocked'
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const canDecide = release.allowed_actions?.includes('go_nogo')

  async function save() {
    setSaving(true)
    try {
      const res = await releasesApi.goNogo(release.id, deciding, note.trim())
      onChange?.(res.data)
      toast?.({ title: deciding === 'approved' ? 'Recorded: go' : 'Recorded: no-go' })
      setDeciding(null); setNote('')
    } catch (err) {
      toast?.error(err.response?.data?.detail || 'Could not record the decision.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className={cn(!bare && 'rounded-xl border border-border bg-card p-4')} aria-labelledby="gonogo-title">
      <div className="flex items-center justify-between gap-2">
        <h3 id="gonogo-title" className="text-sm font-semibold">Go / no-go</h3>
        <GoNogoBadge status={release.go_nogo_status} />
      </div>
      {release.go_nogo_status !== 'pending' ? (
        <div className="mt-2 text-xs text-muted-foreground">
          {deciderName ? `${deciderName} · ` : ''}{release.go_nogo_at ? relTime(release.go_nogo_at) : ''}
          {release.go_nogo_note && (
            <p className="mt-1.5 text-[13px] text-foreground border-l-2 border-border pl-2">{release.go_nogo_note}</p>
          )}
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">No decision yet. Ship doesn’t require one.</p>
      )}

      {canDecide && !deciding && (
        <div className="mt-3 flex gap-2">
          <Button size="sm" variant="outline" className="flex-1" onClick={() => setDeciding('approved')}>
            <Icon name="thumbs-up" size={13} /> Go
          </Button>
          <Button size="sm" variant="outline" className="flex-1" onClick={() => setDeciding('blocked')}>
            <Icon name="thumbs-down" size={13} /> No-go
          </Button>
        </div>
      )}
      {deciding && (
        <form className="mt-3 space-y-2" onSubmit={(e) => { e.preventDefault(); save() }}>
          <label className="block text-xs font-medium text-muted-foreground" htmlFor="gonogo-note">
            Note <span className="font-normal">(optional)</span>
          </label>
          <Textarea
            id="gonogo-note"
            rows={2}
            autoFocus
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={deciding === 'approved' ? 'Anything to watch after the ship?' : 'What has to change first?'}
          />
          <div className="flex justify-end gap-2">
            <Button type="button" size="sm" variant="ghost" onClick={() => setDeciding(null)} disabled={saving}>Cancel</Button>
            <Button type="submit" size="sm" loading={saving} variant={deciding === 'blocked' ? 'destructive' : 'default'}>
              Record {deciding === 'approved' ? 'go' : 'no-go'}
            </Button>
          </div>
        </form>
      )}
    </section>
  )
}
