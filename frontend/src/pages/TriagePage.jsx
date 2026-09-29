import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '../lib/cn'
import { Avatar } from '../components/ui/Avatar'
import { PriorityBadge, StatusBadge, RoleBadge } from '../components/ui/Badge'
import { Icon } from '../components/ui/Icon'
import { Tabs } from '../components/ui/Tabs'
import { Empty } from '../components/ui/Empty'
import { Dropdown, DropdownItem, DropdownLabel } from '../components/ui/Dropdown'
import { MediaPreview } from '../components/common/MediaPreview'
import { SourceBadge } from '../components/common/SourceBadge'
import { ReportedCount } from '../components/common/ReportedCount'
import { TriageOutcomePanel } from '../components/triage'
import { issuesApi, teamApi, attachmentsApi } from '../lib/api'
import { issueKey } from '../lib/issueSlug'
import { relTime, fullTime } from '../lib/relTime'
import { useToast } from '../components/ui/Toast'
import { renderMarkdown } from '../lib/markdown'
import { useApp } from '../context/AppContext'

const SORT_OPTIONS = [
  { value: 'oldest', label: 'Oldest first' },
  { value: 'newest', label: 'Newest first' },
  { value: 'priority', label: 'Priority' },
]

const TRIAGE_STATUSES = ['new', 'needs_info']

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

function QueueSkeleton() {
  return (
    <ul aria-hidden="true">
      {[0, 1, 2, 3, 4].map(i => (
        <li key={i} className="px-7 py-3 border-b border-border">
          <div className="h-3 w-24 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse" />
          <div className="mt-2 h-3.5 w-3/4 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse" />
          <div className="mt-2 h-3 w-32 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse" />
        </li>
      ))}
    </ul>
  )
}

export default function TriagePage() {
  const [issues, setIssues] = useState([])
  const [assignable, setAssignable] = useState([])
  const [attachments, setAttachments] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('new')
  const [sort, setSort] = useState('oldest')
  const [selectedId, setSelectedId] = useState(null)
  const { toast } = useToast()
  const { activeProjectId, projects } = useApp()

  const loadQueue = useCallback(async () => {
    const params = { statuses: TRIAGE_STATUSES.join(','), sort, size: 500 }
    if (activeProjectId) params.project_id = activeProjectId
    const res = await issuesApi.list(params)
    setIssues(res.data.items)
  }, [activeProjectId, sort])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([loadQueue(), teamApi.listAssignable().then(r => { if (!cancelled) setAssignable(r.data) })])
      .catch(() => toast.error('Failed to load the triage queue'))
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [loadQueue, toast])

  const counts = useMemo(() => ({
    new: issues.filter(i => i.status === 'new').length,
    needs_info: issues.filter(i => i.status === 'needs_info').length,
  }), [issues])
  const queue = useMemo(() => issues.filter(i => i.status === tab), [issues, tab])
  const selected = queue.find(i => i.id === selectedId) ?? null
  const project = projects.find(p => String(p.id) === String(selected?.project_id))

  // Keep a selection inside the current tab.
  useEffect(() => {
    if (!queue.some(i => i.id === selectedId)) setSelectedId(queue[0]?.id ?? null)
  }, [queue, selectedId])

  useEffect(() => {
    if (!selected) { setAttachments([]); return }
    attachmentsApi.list(selected.id)
      .then(r => setAttachments(r.data.map(normalizeAttachment)))
      .catch(() => setAttachments([]))
  }, [selected?.id])

  function handleDone(updated) {
    setIssues(prev => TRIAGE_STATUSES.includes(updated.status)
      ? prev.map(i => (i.id === updated.id ? updated : i))
      : prev.filter(i => i.id !== updated.id))
  }

  async function handleMove(target) {
    try {
      const res = await issuesApi.move(selected.id, target.id)
      toast({ title: `${issueKey(selected)} moved to ${target.name}`, body: "It's in that project's triage queue now." })
      if (activeProjectId && String(activeProjectId) !== String(target.id)) {
        setIssues(prev => prev.filter(i => i.id !== selected.id))
      } else {
        setIssues(prev => prev.map(i => (i.id === res.data.id ? res.data : i)))
      }
    } catch (err) {
      const detail = err?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'Failed to move the bug')
    }
  }

  const moveTargets = projects.filter(p => !p.archived_at && String(p.id) !== String(selected?.project_id))
  const canMove = selected && selected.release_id == null

  return (
    <div className="grid grid-cols-[1fr_440px] h-full min-h-0">
      {/* Left: the queue */}
      <div className="border-r border-border overflow-y-auto">
        <div className="px-7 pt-4 border-b border-border sticky top-0 bg-background/95 backdrop-blur z-10">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h1 className="text-lg font-semibold text-foreground">Triage queue</h1>
              <p className="text-[12px] text-muted-foreground">
                {activeProjectId ? (projects.find(p => String(p.id) === String(activeProjectId))?.name ?? 'This project') : 'All projects'}
              </p>
            </div>
            <Dropdown width={148}
              trigger={
                <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-border bg-background hover:bg-muted text-[12px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
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
          <Tabs
            className="mt-2 border-b-0"
            value={tab}
            onValueChange={setTab}
            options={[
              { value: 'new', label: 'New', badge: counts.new },
              { value: 'needs_info', label: 'Needs info', badge: counts.needs_info },
            ]}
          />
        </div>

        {loading ? <QueueSkeleton /> : queue.length === 0 ? (
          tab === 'new'
            ? <Empty icon="check-check" title="Triage zero" body="No new bugs are waiting for a decision." />
            : <Empty icon="help-circle" title="Nothing waiting on reporters" body="Bugs you ask for more information land here until the reporter replies." />
        ) : (
          <ul data-testid="triage-queue">
            {queue.map(i => {
              const r = i.reporter_user
              return (
                <li key={i.id}>
                  <button onClick={() => setSelectedId(i.id)}
                    aria-current={selectedId === i.id ? 'true' : undefined}
                    className={cn('w-full text-left px-7 py-3 border-b border-border hover:bg-muted/50 transition-colors',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
                      selectedId === i.id && 'bg-muted/80')}>
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="font-mono text-[11px] text-muted-foreground">{issueKey(i)}</span>
                      <SourceBadge source={i.source} />
                      <ReportedCount count={i.recurrence_count} />
                      <span className="ml-auto text-[11px] text-muted-foreground" title={fullTime(i.created_at)}>
                        filed {relTime(i.created_at)}
                      </span>
                    </div>
                    <div className="text-[13.5px] font-medium text-foreground leading-snug">{i.title}</div>
                    <div className="mt-1.5 flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                      <Avatar user={r} size={14} />
                      <span>{r?.name ?? 'Unknown reporter'}</span>
                      {/* A Support reporter is already said by the source badge. */}
                      {r?.role && !(r.role === 'support' && i.source === 'support') && <RoleBadge role={r.role} />}
                      {!activeProjectId && i.project_name && <span className="ml-auto truncate">{i.project_name}</span>}
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {/* Right: the selected bug and its outcomes */}
      <div className="overflow-y-auto bg-muted/40">
        {!selected ? (
          !loading && <Empty icon="inbox" title="No bug selected" body="Pick a bug from the queue to triage it." />
        ) : (
          <div className="px-5 py-5" data-testid="triage-detail">
            <div className="flex items-center gap-2 mb-2">
              <a href={`#/issue/${issueKey(selected).toLowerCase()}`} className="font-mono text-[12px] text-muted-foreground hover:underline">
                {issueKey(selected)}
              </a>
              <SourceBadge source={selected.source} />
              <PriorityBadge priority={selected.priority} />
              <StatusBadge status={selected.status} />
              <div className="ml-auto">
                <Dropdown align="end" width={220}
                  trigger={
                    <button disabled={!canMove}
                      title={canMove ? undefined : 'A bug in a release can’t change project'}
                      className="inline-flex items-center gap-1.5 h-7 px-2 rounded-md border border-border bg-background hover:bg-muted text-[11.5px] disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                      <Icon name="folder-input" size={12} aria-hidden="true" /> Move to project
                    </button>
                  }
                >
                  {({ close }) => (
                    <>
                      <DropdownLabel>Move to</DropdownLabel>
                      {moveTargets.length === 0 && (
                        <div className="px-3 py-2 text-[12px] text-muted-foreground">No other projects</div>
                      )}
                      {moveTargets.map(p => (
                        <DropdownItem key={p.id} onClick={() => { close(); handleMove(p) }}>{p.name}</DropdownItem>
                      ))}
                    </>
                  )}
                </Dropdown>
              </div>
            </div>
            <h2 className="text-[17px] font-semibold leading-snug text-foreground">{selected.title}</h2>
            <div className="mt-1 flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
              <Avatar user={selected.reporter_user} size={14} />
              <span>{selected.reporter_user?.name ?? 'Unknown reporter'}</span>
              <span aria-hidden="true">·</span>
              <span title={fullTime(selected.created_at)}>{relTime(selected.created_at)}</span>
              {selected.recurrence_count > 1 && (
                <>
                  <span aria-hidden="true">·</span>
                  <span>Reported {selected.recurrence_count} times</span>
                </>
              )}
            </div>

            <div className="mt-3 text-[13px] text-foreground/90 leading-relaxed prose-sm max-w-none">
              {selected.description
                ? renderMarkdown(selected.description)
                : <span className="text-muted-foreground">No description provided.</span>}
            </div>

            {attachments.length > 0
              ? <MediaPreview key={selected.id} attachments={attachments} readonly />
              : (
                <div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground/60">
                  <Icon name="paperclip" size={11} />
                  <span>No attachments</span>
                </div>
              )}

            <TriageOutcomePanel
              issue={selected}
              assignable={assignable}
              onDone={handleDone}
              toast={toast}
            />
          </div>
        )}
      </div>
    </div>
  )
}
