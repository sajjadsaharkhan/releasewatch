import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { Switch } from '../components/ui/Switch'
import { Avatar } from '../components/ui/Avatar'
import { SeverityBadge, StatusBadge } from '../components/ui/Badge'
import { Icon } from '../components/ui/Icon'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { MediaPreview } from '../components/common/MediaPreview'
import { SEVERITY } from '../lib/constants'
import { issuesApi, teamApi, labelsApi, attachmentsApi } from '../lib/api'
import { useToast } from '../components/ui/Toast'
import { renderMarkdown } from '../lib/markdown'
import { Dialog } from '../components/ui/Dialog'
import { useApp } from '../context/AppContext'

const SORT_OPTIONS = [
  { value: 'oldest', label: 'Oldest first' },
  { value: 'newest', label: 'Newest first' },
  { value: 'severity', label: 'Severity' },
]

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

function normalizeAttachment(a) {
  const mimeType = a.mime_type || ''
  const type = mimeType.startsWith('image/') ? 'image' : mimeType.startsWith('video/') ? 'video' : 'file'
  return {
    id: a.id,
    name: a.file_name,
    type,
    url: a.download_url || a.public_url || '#',
    size: a.file_size_bytes || 0,
    createdAt: a.created_at,
  }
}

export default function TriagePage() {
  const [issues, setIssues] = useState([])
  const [team, setTeam] = useState([])
  const [labelsData, setLabelsData] = useState([])
  const [attachments, setAttachments] = useState([])
  const [loading, setLoading] = useState(true)

  const [sort, setSort] = useState('oldest')
  const [selectedId, setSelectedId] = useState(null)
  const [assignee, setAssignee] = useState(null)
  const [severity, setSeverity] = useState('major')
  const [labels, setLabels] = useState([])
  const [blocker, setBlocker] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [clarifyOpen, setClarifyOpen] = useState(false)
  const [clarifyMsg, setClarifyMsg] = useState('')
  const [clarifying, setClarifying] = useState(false)
  const { toast } = useToast()
  const { activeProjectId, activeReleaseId } = useApp()

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const issueParams = { status: 'new', sort }
        if (activeProjectId) issueParams.project_id = activeProjectId
        if (activeReleaseId) issueParams.release_id = activeReleaseId
        const [issuesRes, teamRes, labelsRes] = await Promise.all([
          issuesApi.list(issueParams),
          teamApi.list(),
          labelsApi.list(),
        ])
        setIssues(issuesRes.data.items)
        setTeam(teamRes.data)
        setLabelsData(labelsRes.data)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [activeProjectId, activeReleaseId, sort])

  useEffect(() => {
    if (!selectedId) { setAttachments([]); return }
    attachmentsApi.list(selectedId)
      .then(r => setAttachments(r.data.map(normalizeAttachment)))
      .catch(() => setAttachments([]))
  }, [selectedId])

  const userById = useCallback((id) => team.find(u => String(u.id) === String(id)), [team])

  const queue = useMemo(() => {
    return issues.map(i => ({ ...i, age: calculateAge(i.created_at) }))
  }, [issues])
  const selected = queue.find(i => String(i.id) === String(selectedId))

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

  async function handleTriage() {
    if (!assignee) return
    setSubmitting(true)
    try {
      await issuesApi.triage(selected.id, {
        assignee_id: assignee,
        severity,
        labels,
        is_release_blocker: blocker,
      })
      const assigneeName = userById(assignee)?.name || 'assignee'
      const reloadParams = { status: 'new', sort }
      if (activeProjectId) reloadParams.project_id = activeProjectId
      if (activeReleaseId) reloadParams.release_id = activeReleaseId
      const res = await issuesApi.list(reloadParams)
      const updated = res.data.items
      setIssues(updated)
      const next = updated.find(i => String(i.id) !== String(selected.id))
      setSelectedId(next ? next.id : null)
      setAssignee(null)
      toast({ title: 'Issue triaged', body: `Assigned to ${assigneeName} and marked as triaged.` })
    } finally {
      setSubmitting(false)
    }
  }

  function handleNeedsClarification() {
    setClarifyMsg('')
    setClarifyOpen(true)
  }

  async function handleClarifySend() {
    setClarifying(true)
    try {
      await issuesApi.needsClarification(selected.id, { message: clarifyMsg || undefined })
      const reporterName = userById(selected.reporter_id)?.name || 'reporter'
      const reloadParams = { status: 'new', sort }
      if (activeProjectId) reloadParams.project_id = activeProjectId
      if (activeReleaseId) reloadParams.release_id = activeReleaseId
      const res = await issuesApi.list(reloadParams)
      const updated = res.data.items
      setIssues(updated)
      const next = updated.find(i => String(i.id) !== String(selected.id))
      setSelectedId(next ? next.id : null)
      setClarifyOpen(false)
      setAssignee(null)
      toast({ title: 'Clarification requested', body: `${reporterName} has been notified.` })
    } finally {
      setClarifying(false)
    }
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading triage queue…</p>
      </div>
    )
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
  const reporter = userById(selected.reporter_id)

  return (
    <>
    <div className="grid grid-cols-[1fr_440px] h-full min-h-0">
      {/* Left: issue list */}
      <div className="border-r border-border overflow-y-auto">
        <div className="px-7 py-4 border-b border-border sticky top-0 bg-background/95 backdrop-blur z-10">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h1 className="text-lg font-semibold text-foreground">Triage queue</h1>
              <p className="text-[12px] text-muted-foreground">{queue.length} unassigned</p>
            </div>
            <Dropdown width={148}
              trigger={
                <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-border bg-background hover:bg-muted text-[12px]">
                  <Icon name="arrow-up-down" size={12} className="text-muted-foreground" />
                  <span className="font-medium text-foreground">{SORT_OPTIONS.find(s => s.value === sort)?.label}</span>
                  <ChevronDown className="h-3 w-3 text-muted-foreground" />
                </button>
              }
            >
              {({ close }) => SORT_OPTIONS.map(opt => (
                <DropdownItem key={opt.value} onClick={() => { setSort(opt.value); close() }}>
                  {opt.label}
                </DropdownItem>
              ))}
            </Dropdown>
          </div>
        </div>
        <ul>
          {queue.map(i => {
            const r = userById(i.reporter_id)
            const issueHours = i.age?.endsWith('h') ? parseFloat(i.age) : parseFloat(i.age) * 24 || 0
            const issueSla = slaColor(issueHours)
            return (
              <li key={i.id}>
                <button onClick={() => setSelectedId(i.id)}
                  className={cn('w-full text-left px-7 py-3 border-b border-border hover:bg-muted/50 transition-colors',
                    String(selectedId) === String(i.id) && 'bg-muted/80')}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <SeverityBadge severity={i.severity} dot />
                    <span className="font-mono text-[11px] text-muted-foreground">issue-{i.issue_number}</span>
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
            <span className="font-mono text-[12px] text-muted-foreground">issue-{selected.issue_number}</span>
            <SeverityBadge severity={selected.severity} dot />
            <StatusBadge status={selected.status} />
          </div>
          <h2 className="text-[17px] font-semibold leading-snug text-foreground">{selected.title}</h2>

          <div className="mt-3 text-[13px] text-foreground/90 leading-relaxed prose-sm max-w-none">
            {selected.description
              ? renderMarkdown(selected.description)
              : <span className="text-muted-foreground">No description provided.</span>}
          </div>

          {attachments.length > 0 && <MediaPreview attachments={attachments} readonly />}
          {attachments.length === 0 && (
            <div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground/60">
              <Icon name="paperclip" size={11} />
              <span>No attachments</span>
            </div>
          )}

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
              {team.map(u => (
                <button key={u.id} onClick={() => setAssignee(u.id)}
                  className={cn('flex items-center gap-2 px-2.5 h-9 rounded-md border text-[12.5px] transition-colors',
                    String(assignee) === String(u.id)
                      ? 'border-foreground bg-muted dark:border-foreground dark:bg-muted'
                      : 'border-border hover:bg-muted dark:border-border dark:hover:bg-muted')}>
                  <Avatar user={u} size={22} />
                  <span className="font-medium text-foreground">{u.name}</span>
                  <span className="text-[10.5px] text-muted-foreground font-mono ml-1">{u.telegram_handle || ''}</span>
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
                {labelsData.map(l => (
                  <button key={l.id} onClick={() => setLabels(L => L.includes(l.name) ? L.filter(x => x !== l.name) : [...L, l.name])}
                    className={cn('inline-flex items-center rounded px-1.5 py-0.5 text-[11px]',
                      labels.includes(l.name)
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
                  {blocker ? 'Blocks release' : 'Not a blocker'}
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
              <Icon name="send" size={11} className="text-blue-500" /> Will Telegram-ping {userById(assignee)?.telegram_handle || ''}
            </div>
          )}
        </div>
      </div>
    </div>
    <Dialog open={clarifyOpen} onClose={() => setClarifyOpen(false)} title="Needs clarification" size="sm">
      <div className="px-5 py-4 flex flex-col gap-3">
        <p className="text-[13px] text-muted-foreground">
          Describe what additional information you need from the reporter. This is optional — you can send without a message.
        </p>
        <textarea
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-ring"
          rows={4}
          placeholder="e.g. Please share the exact error message and steps to reproduce on staging…"
          value={clarifyMsg}
          onChange={e => setClarifyMsg(e.target.value)}
        />
        <div className="flex gap-2 justify-end">
          <Button variant="outline" onClick={() => setClarifyOpen(false)} disabled={clarifying}>
            Cancel
          </Button>
          <Button onClick={handleClarifySend} loading={clarifying}>
            <Icon name="send" size={13} /> Send to reporter
          </Button>
        </div>
      </div>
    </Dialog>
    </>
  )
}
