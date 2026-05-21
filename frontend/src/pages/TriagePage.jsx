import React, { useState, useEffect, useMemo } from 'react'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { Switch } from '../components/ui/Switch'
import { Avatar } from '../components/ui/Avatar'
import { SeverityBadge, StatusBadge } from '../components/ui/Badge'
import { Icon } from '../components/ui/Icon'
import { MOCK_ISSUES, MOCK_TEAM, MOCK_LABELS, SEVERITY, STATUS, userById } from '../data/mockData'

function calculateAge(createdAt) {
  const now = new Date()
  const created = new Date(createdAt)
  const hours = Math.floor((now - created) / (1000 * 60 * 60))
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  return `${days}d`
}

function slaColor(hours) {
  if (hours < 4) return { dot: 'bg-emerald-500', text: 'text-emerald-600 dark:text-emerald-400' }
  if (hours < 8) return { dot: 'bg-amber-500', text: 'text-amber-600 dark:text-amber-400' }
  return { dot: 'bg-red-500', text: 'text-red-600 dark:text-red-400' }
}

function RoleBadge({ value }) {
  if (!value) return null
  const roleColors = {
    qa: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    developer: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
    triage_lead: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    cto: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400',
    admin: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
  }
  return (
    <span className={cn('text-[10px] px-1.5 py-0.5 rounded font-medium uppercase tracking-wide', roleColors[value] || 'bg-zinc-100 text-zinc-700')}>
      {value.replace('_', ' ')}
    </span>
  )
}

function FullscreenMediaOverlay({ media, onClose, onDownload }) {
  const [saved, setSaved] = useState(false)

  const handleDownload = () => {
    onDownload()
    setSaved(true)
    setTimeout(() => setSaved(false), 1400)
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative max-w-6xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-full bg-background/10 flex items-center justify-center">
              <Icon name={media.kind === 'image' ? 'image' : media.kind === 'video' ? 'play' : 'file-text'} size={16} className="text-white" />
            </div>
            <div>
              <div className="text-white font-medium">{media.label}</div>
              <div className="text-zinc-400 text-sm">{media.size} · {media.meta}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              className="h-9 px-4 rounded-lg bg-white text-black text-sm font-medium hover:bg-white/90 flex items-center gap-2">
              <Icon name={saved ? 'check' : 'download'} size={16} />
              {saved ? 'Saved' : 'Download'}
            </button>
            <button
              onClick={onClose}
              className="h-9 w-9 rounded-lg bg-white/10 text-white hover:bg-white/20 flex items-center justify-center">
              <Icon name="x" size={20} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 bg-background/5 rounded-lg overflow-hidden flex items-center justify-center min-h-[60vh]">
          <div className="w-full max-h-full">
            <MediaPreviewSurface media={media} fullscreen />
          </div>
        </div>

        {/* Footer info */}
        <div className="mt-4 text-center text-sm text-zinc-400">
          Press ESC to close
        </div>
      </div>
    </div>
  )
}

function TriageMediaPreview() {
  const [activeId, setActiveId] = useState('m1')
  const [saved, setSaved] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)

  const active = TRIAGE_MEDIA.find(m => m.id === activeId)

  const download = (e) => {
    e.stopPropagation()
    setSaved(true)
    setTimeout(() => setSaved(false), 1400)
  }

  const openFullscreen = () => {
    setIsFullscreen(true)
    document.body.style.overflow = 'hidden'
  }

  const closeFullscreen = () => {
    setIsFullscreen(false)
    document.body.style.overflow = ''
  }

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && isFullscreen) {
        closeFullscreen()
      }
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [isFullscreen])

  return (
    <div className="mt-3 rounded-lg border border-border overflow-hidden bg-background">
      {/* hero preview */}
      <div className="relative bg-muted border-b border-border">
        <MediaPreviewSurface media={active} />

        {/* overlay header */}
        <div className="absolute top-2 left-2 right-2 flex items-center gap-1.5 pointer-events-none">
          <div className="pointer-events-auto inline-flex items-center gap-1.5 h-6 px-2 rounded-md bg-background/95 border border-border backdrop-blur">
            <Icon name={active.kind === 'image' ? 'image' : active.kind === 'video' ? 'play' : 'file-text'} size={11} className="text-muted-foreground" />
            <span className="text-[11px] font-mono text-foreground max-w-[150px] truncate">{active.label}</span>
          </div>
          <div className="ml-auto flex items-center gap-1 pointer-events-auto">
            {(active.kind === 'image' || active.kind === 'video') && (
              <button
                onClick={openFullscreen}
                title="Open full"
                className="h-6 w-6 inline-flex items-center justify-center rounded-md bg-background/95 border border-border text-muted-foreground hover:text-foreground backdrop-blur">
                <Icon name="maximize-2" size={11} />
              </button>
            )}
            <button
              onClick={download}
              title={`Download ${active.label}`}
              className="inline-flex items-center gap-1 h-6 px-2 rounded-md bg-foreground text-background text-[11px] font-medium hover:bg-foreground/90 dark:bg-background dark:text-foreground dark:hover:bg-muted shadow-sm">
              <Icon name={saved ? 'check' : 'download'} size={11} />
              {saved ? 'Saved' : 'Download'}
            </button>
          </div>
        </div>
      </div>

      {/* meta strip */}
      <div className="flex items-center gap-2 px-3 py-1.5 text-[11px] text-muted-foreground border-b border-border">
        <span className="font-medium text-foreground">{active.size}</span>
        <span className="text-muted-foreground/60">·</span>
        <span>{active.meta}</span>
        <span className="text-muted-foreground/60">·</span>
        <span className="truncate">{active.captured}</span>
      </div>

      {/* thumbnail strip */}
      <div className="grid grid-cols-3 gap-1 p-1">
        {TRIAGE_MEDIA.map(m => (
          <button
            key={m.id}
            onClick={() => setActiveId(m.id)}
            className={cn(
              'group rounded-md p-1.5 flex items-center gap-2 text-left transition-colors min-w-0',
              activeId === m.id
                ? 'bg-muted'
                : 'hover:bg-muted/50'
            )}>
            <div className={cn(
              'h-7 w-7 rounded flex items-center justify-center shrink-0 border',
              activeId === m.id
                ? 'bg-background border-border text-foreground'
                : 'bg-muted border-border text-muted-foreground'
            )}>
              <Icon name={m.kind === 'image' ? 'image' : m.kind === 'video' ? 'play' : 'file-text'} size={12} />
            </div>
            <div className="min-w-0">
              <div className={cn(
                'text-[11.5px] font-medium truncate',
                activeId === m.id ? 'text-foreground' : 'text-muted-foreground'
              )}>{m.label}</div>
              <div className="text-[10px] text-muted-foreground truncate">{m.size}</div>
            </div>
          </button>
        ))}
      </div>

      {isFullscreen && (
        <FullscreenMediaOverlay
          media={active}
          onClose={closeFullscreen}
          onDownload={() => {
            setSaved(true)
            setTimeout(() => setSaved(false), 1400)
          }}
        />
      )}
    </div>
  )
}

function MediaPreviewSurface({ media, fullscreen = false }) {
  if (media.kind === 'image') {
    return (
      <div className={cn('relative overflow-hidden', fullscreen ? 'h-full w-full' : 'aspect-[16/9] w-full')}>
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-100 to-zinc-200 dark:from-zinc-900 dark:to-zinc-950">
          <div className="h-5 border-b border-zinc-300/70 dark:border-zinc-700/60 bg-white/60 dark:bg-zinc-900/60 flex items-center gap-1 px-2">
            <span className="h-1.5 w-1.5 rounded-full bg-red-400/80" />
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400/80" />
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400/80" />
            <div className="ml-2 h-2.5 rounded-sm bg-zinc-200 dark:bg-zinc-800 flex-1 max-w-[180px]" />
          </div>
          <div className={cn('rounded-md bg-white dark:bg-zinc-900 shadow-lg ring-1 ring-zinc-200 dark:ring-zinc-800 overflow-hidden', fullscreen ? 'w-[90%] h-[90%] mx-auto my-auto' : 'absolute left-1/2 top-[54%] -translate-x-1/2 -translate-y-1/2 w-[72%]')}>
            <div className="px-2.5 py-1.5 bg-red-50 dark:bg-red-950/40 border-b border-red-200/70 dark:border-red-900/50 flex items-center gap-1.5">
              <Icon name="triangle-alert" size={11} className="text-red-600 dark:text-red-400" />
              <span className="text-[10.5px] font-mono font-semibold text-red-700 dark:text-red-300">500 Internal Server Error</span>
              <span className="ml-auto text-[9.5px] font-mono text-red-500/80 hidden sm:inline">POST /wallet/transfer</span>
            </div>
            <div className="px-2.5 py-2 space-y-0.5 font-mono text-[9.5px] leading-snug text-zinc-700 dark:text-zinc-300">
              <div><span className="text-zinc-400">{'{'}</span></div>
              <div className="pl-3"><span className="text-blue-600 dark:text-blue-400">"error"</span>: <span className="text-emerald-600 dark:text-emerald-400">"balance_inconsistent"</span>,</div>
              <div className="pl-3"><span className="text-blue-600 dark:text-blue-400">"trace_id"</span>: <span className="text-emerald-600 dark:text-emerald-400">"wlt-7f4-aGc1z"</span>,</div>
              <div className="pl-3"><span className="text-blue-600 dark:text-blue-400">"debit_count"</span>: <span className="text-amber-600 dark:text-amber-400">2</span></div>
              <div><span className="text-zinc-400">{'}'}</span></div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (media.kind === 'video') {
    return (
      <div className={cn('relative bg-zinc-900 dark:bg-black overflow-hidden', fullscreen ? 'h-full w-full' : 'aspect-[16/9] w-full')}>
        <div className="absolute inset-0 opacity-70" style={{
          background: 'radial-gradient(ellipse at 30% 40%, rgba(99,102,241,0.4), transparent 60%), radial-gradient(ellipse at 70% 70%, rgba(244,63,94,0.28), transparent 55%)'
        }} />
        <div className="absolute inset-0 grid grid-cols-12 grid-rows-7 opacity-20">
          {Array.from({ length: 84 }).map((_, i) => <div key={i} className="border border-white/5" />)}
        </div>
        <div className="absolute inset-0 flex items-center justify-center">
          <button className="h-12 w-12 rounded-full bg-white/95 text-zinc-900 shadow-xl flex items-center justify-center hover:scale-105 transition-transform">
            <Icon name="play" size={20} className="ml-0.5" />
          </button>
        </div>
        <div className="absolute bottom-2 left-2 right-2 flex items-center gap-2 text-white">
          <span className="font-mono text-[10px] tabular-nums">0:00</span>
          <div className="flex-1 h-1 rounded-full bg-white/20 overflow-hidden">
            <div className="h-full w-[18%] bg-white rounded-full" />
          </div>
          <span className="font-mono text-[10px] tabular-nums opacity-70">1:12</span>
        </div>
      </div>
    )
  }

  // file (log)
  return (
    <div className={cn('relative overflow-hidden bg-zinc-950', fullscreen ? 'h-full w-full' : 'aspect-[16/9] w-full')}>
      <div className="absolute inset-0 p-3 pt-8 font-mono text-[9.5px] leading-[1.55] text-zinc-300 overflow-hidden">
        <div className="text-zinc-500">[11:00:14.221] <span className="text-blue-400">INFO</span>  wallet.transfer received id=tx_aGc1z amount=42.00</div>
        <div className="text-zinc-500">[11:00:14.224] <span className="text-blue-400">INFO</span>  wallet.transfer received id=tx_aGc1z amount=42.00 <span className="text-amber-400">// duplicate within 200ms</span></div>
        <div className="text-zinc-500">[11:00:14.238] <span className="text-blue-400">DEBUG</span> lock.acquire row=wallet:u_3142 ok</div>
        <div className="text-zinc-500">[11:00:14.239] <span className="text-blue-400">DEBUG</span> lock.acquire row=wallet:u_3142 <span className="text-red-400">MISS</span> — no pessimistic lock</div>
        <div className="text-zinc-500">[11:00:14.301] <span className="text-red-400">ERROR</span> balance_inconsistent debit_count=2 trace=wlt-7f4-aGc1z</div>
        <div className="text-zinc-500">[11:00:14.305] <span className="text-red-400">ERROR</span>   at wallet.svc.transfer (transfer.ts:142)</div>
        <div className="text-zinc-600">[11:00:14.401] <span className="text-blue-400">INFO</span>  500 returned to client in 187ms</div>
      </div>
      <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-zinc-950 to-transparent" />
    </div>
  )
}

const TRIAGE_MEDIA = [
  {
    id: 'm1', kind: 'image', label: '500-response.png',
    size: '248 KB', meta: '1284 × 812', captured: 'just now · staging-2',
  },
  {
    id: 'm2', kind: 'video', label: 'screen-rec.mp4',
    size: '4.1 MB', meta: '1m 12s · 1080p', captured: 'reporter · iPhone 14 Pro',
  },
  {
    id: 'm3', kind: 'file', label: 'trace.log',
    size: '32 KB', meta: '412 lines', captured: 'wallet-svc · pod-7f4',
  },
]

export default function TriagePage() {
  const [selectedId, setSelectedId] = useState(null)
  const [assignee, setAssignee] = useState(null)
  const [severity, setSeverity] = useState('major')
  const [labels, setLabels] = useState([])
  const [blocker, setBlocker] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const queue = useMemo(() => {
    const issues = MOCK_ISSUES.filter(i => !i.assignee)
    return issues.map(i => ({ ...i, age: calculateAge(i.createdAt) }))
  }, [])
  const selected = queue.find(i => i.id === selectedId)

  useEffect(() => {
    if (queue.length > 0 && !selectedId) {
      setSelectedId(queue[0].id)
    }
  }, [queue, selectedId])

  useEffect(() => {
    if (selected) {
      setSeverity(selected.severity || 'major')
      setLabels(selected.labels || [])
      setBlocker(selected.is_release_blocker || false)
      setAssignee(null)
    }
  }, [selected?.id])

  function handleTriage() {
    if (!assignee) return
    setSubmitting(true)
    setTimeout(() => {
      const next = queue.find(q => q.id !== selected.id)
      if (next) setSelectedId(next.id)
      setSubmitting(false)
      setAssignee(null)
    }, 600)
  }

  function handleNeedsClarification() {
    // Navigate to issue detail
    window.location.hash = `#/issue/${selected.id}`
  }

  if (queue.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">✓</div>
          <p className="text-lg font-medium text-foreground">Triage zero</p>
          <p className="text-sm text-muted-foreground mt-1">No unassigned issues right now.</p>
        </div>
      </div>
    )
  }

  if (!selected) return null

  const hours = selected.age?.endsWith('h') ? parseFloat(selected.age) : parseFloat(selected.age) * 24 || 0
  const sla = slaColor(hours)
  const reporter = userById(selected.reporter)
  const age = calculateAge(selected.createdAt)

  return (
    <div className="grid grid-cols-[1fr_440px] h-full min-h-0">
      {/* Left: issue list */}
      <div className="border-r border-border overflow-y-auto">
        <div className="px-7 py-4 border-b border-border sticky top-0 bg-background/95 backdrop-blur z-10">
          <h1 className="text-lg font-semibold text-foreground">Triage queue</h1>
          <p className="text-[12px] text-muted-foreground">{queue.length} unassigned · sorted by severity &amp; age</p>
        </div>
        <ul>
          {queue.map(i => {
            const r = userById(i.reporter)
            const issueHours = i.age?.endsWith('h') ? parseFloat(i.age) : parseFloat(i.age) * 24 || 0
            const issueSla = slaColor(issueHours)
            return (
              <li key={i.id}>
                <button onClick={() => setSelectedId(i.id)}
                  className={cn('w-full text-left px-7 py-3 border-b border-border hover:bg-muted/50 transition-colors',
                    selectedId === i.id && 'bg-muted/80')}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <SeverityBadge severity={i.severity} dot />
                    <span className="font-mono text-[11px] text-muted-foreground">{i.id}</span>
                    <span className="ml-auto inline-flex items-center gap-1 text-[11px]">
                      <span className={cn('h-1.5 w-1.5 rounded-full', issueSla.dot)} />
                      <span className={issueSla.text}>filed {i.age} ago</span>
                    </span>
                  </div>
                  <div className="text-[13.5px] font-medium text-foreground leading-snug">{i.title}</div>
                  <div className="mt-1.5 flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                    <Avatar user={r} size={14} />
                    <span>{r?.name}</span>
                    <RoleBadge value={r?.role} />
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
      </div>

      {/* Right: triage form */}
      <div className="overflow-y-auto bg-muted/40">
        <div className="px-5 py-5">
          <div className="flex items-center gap-2 mb-2">
            <span className="font-mono text-[12px] text-muted-foreground">{selected.id}</span>
            <SeverityBadge severity={selected.severity} dot />
            <StatusBadge status={selected.status} />
          </div>
          <h2 className="text-[17px] font-semibold leading-snug text-foreground">{selected.title}</h2>

          <div className="mt-3 text-[13px] text-muted-foreground leading-relaxed">
            {selected.description?.substring(0, 150) || 'No description provided.'}
            {selected.description?.length > 150 && (
              <button className="ml-1 text-[11.5px] text-blue-600 dark:text-blue-400">expand</button>
            )}
          </div>

          <TriageMediaPreview />

          <div className="mt-5">
            <div className="text-[10.5px] uppercase tracking-wide font-semibold text-muted-foreground mb-1.5">Severity</div>
            <div className="overflow-x-auto overflow-y-hidden -mx-1 px-1">
              <div className="flex gap-1.5 min-w-max pb-1">
                {Object.keys(SEVERITY).map(s => (
                  <button key={s} onClick={() => setSeverity(s)}
                    className={cn('h-8 px-2.5 rounded-md text-[11.5px] font-medium border transition-colors flex items-center gap-1.5 whitespace-nowrap',
                      severity === s
                        ? 'bg-foreground text-background border-foreground dark:bg-background dark:text-foreground dark:border-background'
                        : 'bg-background text-muted-foreground border-border hover:bg-muted dark:bg-background dark:text-muted-foreground dark:border-border dark:hover:bg-muted')}>
                    <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', SEVERITY[s].dot)} />
                    {SEVERITY[s].label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-4">
            <div className="text-[10.5px] uppercase tracking-wide font-semibold text-muted-foreground mb-1.5">Assign to</div>
            <div className="grid grid-cols-1 gap-1.5">
              {MOCK_TEAM.filter(u => ['developer', 'admin'].includes(u.role)).map(u => (
                <button key={u.id} onClick={() => setAssignee(u.id)}
                  className={cn('flex items-center gap-2 px-2.5 h-9 rounded-md border text-[12.5px] transition-colors',
                    assignee === u.id
                      ? 'border-foreground bg-muted dark:border-foreground dark:bg-muted'
                      : 'border-border hover:bg-muted dark:border-border dark:hover:bg-muted')}>
                  <Avatar user={u} size={22} />
                  <span className="font-medium text-foreground">{u.name}</span>
                  <span className="text-[10.5px] text-muted-foreground font-mono ml-1">{u.tgHandle || ''}</span>
                  {!u.tgConnected
                    ? <span className="ml-auto text-[10px] text-amber-600 inline-flex items-center gap-0.5"><Icon name="triangle-alert" size={9} /> not connected</span>
                    : <span className="ml-auto text-[10px] text-emerald-600 inline-flex items-center gap-0.5"><Icon name="check" size={9} /> reachable</span>}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <div className="text-[10.5px] uppercase tracking-wide font-semibold text-muted-foreground mb-1.5">Labels</div>
              <div className="flex flex-wrap gap-1">
                {MOCK_LABELS.map(l => (
                  <button key={l.id} onClick={() => setLabels(L => L.includes(l.id) ? L.filter(x => x !== l.id) : [...L, l.id])}
                    className={cn('inline-flex items-center rounded px-1.5 py-0.5 text-[11px]',
                      labels.includes(l.id)
                        ? 'bg-foreground text-background dark:bg-background dark:text-foreground'
                        : 'bg-muted text-muted-foreground dark:bg-muted dark:text-muted-foreground hover:bg-muted/70 dark:hover:bg-muted/70')}>
                    {l.name}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[10.5px] uppercase tracking-wide font-semibold text-muted-foreground mb-1.5">Release blocker</div>
              <button onClick={() => setBlocker(b => !b)}
                className={cn('flex items-center justify-between w-full h-9 px-3 rounded-md border',
                  blocker ? 'bg-red-50 border-red-200 dark:bg-red-950/40 dark:border-red-900' : 'border-border dark:border-border')}>
                <span className={cn('text-[12.5px] font-medium', blocker ? 'text-red-700 dark:text-red-300' : 'text-foreground')}>
                  {blocker ? 'Blocks v2.4.1' : 'Not a blocker'}
                </span>
                <Switch checked={blocker} onCheckedChange={setBlocker} />
              </button>
            </div>
          </div>

          <div className="mt-5 flex items-center gap-2">
            <Button onClick={handleTriage} disabled={!assignee} loading={submitting} className="flex-1">
              <Icon name="send" size={13} /> Assign &amp; triage
            </Button>
            <Button variant="outline" className="flex-1" onClick={handleNeedsClarification}>
              <Icon name="message-circle" size={13} /> Needs clarification
            </Button>
          </div>
          {assignee && (
            <div className="mt-2 text-[11px] text-muted-foreground inline-flex items-center gap-1">
              <Icon name="send" size={11} className="text-blue-500" /> Will Telegram-ping {userById(assignee)?.tgHandle || ''}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}