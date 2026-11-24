import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import { cn } from '../lib/cn'
import { Avatar } from '../components/ui/Avatar'
import { RoleBadge } from '../components/ui/Badge'
import { Icon } from '../components/ui/Icon'
import { Tabs } from '../components/ui/Tabs'
import { Empty } from '../components/ui/Empty'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { SourceBadge } from '../components/common/SourceBadge'
import { ReportedCount } from '../components/common/ReportedCount'
import { PossibleDuplicates } from '../components/common/PossibleDuplicates'
import { AgentBadge, OriginFilter } from '../components/common'
import { TriageDetail, ReturnRequestDetail } from '../components/triage'
import { Requesters } from '../components/issues'
import { issuesApi, teamApi, attachmentsApi, returnRequestsApi } from '../lib/api'
import { issueKey } from '../lib/issueSlug'
import { normalizeAttachment } from '../lib/attachments'
import { relTime, fullTime } from '../lib/relTime'
import { useToast } from '../components/ui/Toast'
import { useApp } from '../context/AppContext'

const SORT_OPTIONS = [
  { value: 'oldest', label: 'Oldest first' },
  { value: 'newest', label: 'Newest first' },
  { value: 'priority', label: 'Priority' },
]

const TRIAGE_STATUSES = ['new', 'needs_info']

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

// The reports behind the selected return request (every Support user's entry, with its
// comment) — the queue row carries only the first.
function useReturnEntries(row) {
  const [entries, setEntries] = useState([])
  const requestId = row?.id
  const issueId = row?.issue?.id
  useEffect(() => {
    if (!requestId) { setEntries([]); return undefined }
    let cancelled = false
    returnRequestsApi.forIssue(issueId)
      .then(r => { if (!cancelled) setEntries(r.data.find(x => x.id === requestId)?.entries ?? []) })
      .catch(() => { if (!cancelled) setEntries([]) })
    return () => { cancelled = true }
  }, [requestId, issueId])
  return entries
}

export default function TriagePage() {
  const [issues, setIssues] = useState([])
  const [assignable, setAssignable] = useState([])
  const [attachments, setAttachments] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('new')
  const [sort, setSort] = useState('oldest')
  // All · Agent · People (slice 17, FR-M30) — '' is all.
  const [origin, setOrigin] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  // Pending return requests (slice 20) — a request isn't an issue, so it has its own list.
  const [returns, setReturns] = useState([])
  const [selectedReturnId, setSelectedReturnId] = useState(null)
  const location = useLocation()
  const navigate = useNavigate()
  const { toast } = useToast()
  const { activeProjectId, projects, setTriageCount } = useApp()

  const loadQueue = useCallback(async () => {
    const params = { statuses: TRIAGE_STATUSES.join(','), sort, size: 500 }
    if (activeProjectId) params.project_id = activeProjectId
    if (origin) params.origin = origin
    const [res, pending] = await Promise.all([
      issuesApi.list(params),
      returnRequestsApi.pending(activeProjectId).catch(() => ({ data: { items: [] } })),
    ])
    setIssues(res.data.items)
    setReturns(pending.data.items)
  }, [activeProjectId, sort, origin])

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
  // The sidebar count is the whole queue's — New plus pending return requests — so a filtered view leaves it alone.
  useEffect(() => {
    if (!loading && !origin) setTriageCount(counts.new + returns.length)
  }, [counts.new, returns.length, loading, origin, setTriageCount])
  const selectedReturn = returns.find(r => r.id === selectedReturnId) ?? returns[0] ?? null
  const returnEntries = useReturnEntries(selectedReturn)
  const queue = useMemo(() => issues.filter(i => i.status === tab), [issues, tab])
  const selected = queue.find(i => i.id === selectedId) ?? null
  const project = projects.find(p => String(p.id) === String(selected?.project_id))

  // Keep a selection inside the current tab.
  useEffect(() => {
    if (!queue.some(i => i.id === selectedId)) setSelectedId(queue[0]?.id ?? null)
  }, [queue, selectedId])

  // "Merge into this" on an item page's hints sends the reader here with the
  // item to select (slice 14); consume the hint once so it doesn't stick.
  useEffect(() => {
    const wanted = location.state?.selectIssueId
    if (wanted == null) return
    if (issues.some(i => i.id === wanted)) setSelectedId(wanted)
    navigate(location.pathname, { replace: true, state: null })
  }, [location.state, issues, navigate, location.pathname])

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
            <div className="flex items-center gap-2">
            <OriginFilter value={origin} onChange={setOrigin} />
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
          </div>
          <Tabs
            className="mt-2 border-b-0"
            value={tab}
            onValueChange={setTab}
            options={[
              { value: 'new', label: 'New', badge: counts.new },
              { value: 'needs_info', label: 'Needs info', badge: counts.needs_info },
              { value: 'returns', label: 'Return requests', badge: returns.length },
            ]}
          />
        </div>

        {loading ? <QueueSkeleton /> : tab === 'returns' ? (
          returns.length === 0 ? (
            <Empty icon="rotate-ccw" title="No return requests" body="When Support says a Done item's problem is back, it waits here for a decision." />
          ) : (
            <ul data-testid="return-requests-queue">
              {returns.map(r => (
                <li key={r.id}>
                  <button onClick={() => setSelectedReturnId(r.id)}
                    aria-current={selectedReturn?.id === r.id ? 'true' : undefined}
                    className={cn('w-full text-left px-7 py-3 border-b border-border hover:bg-muted/50 transition-colors',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
                      selectedReturn?.id === r.id && 'bg-muted/80')}>
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="font-mono text-[11px] text-muted-foreground">{r.issue.key}</span>
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10.5px] font-semibold leading-none text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                        <Icon name="rotate-ccw" size={10} strokeWidth={2.5} aria-hidden="true" />
                        {r.entry_count === 1 ? 'Problem is back' : `${r.entry_count} reports`}
                      </span>
                      <span className="ml-auto text-[11px] text-muted-foreground" title={fullTime(r.requested_at)}>
                        asked {relTime(r.requested_at)}
                      </span>
                    </div>
                    <div className="text-[13.5px] font-medium text-foreground leading-snug">{r.issue.title}</div>
                    {r.first_comment?.body && (
                      <p className="mt-1 line-clamp-2 text-[12.5px] text-muted-foreground">{r.first_comment.body}</p>
                    )}
                    <div className="mt-1.5 flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                      <Requesters users={r.requesters} />
                      <span>·</span>
                      <span title={r.issue.done_at ? fullTime(r.issue.done_at) : undefined}>
                        Done {r.issue.done_at ? relTime(r.issue.done_at) : ''}
                      </span>
                      <span>·</span>
                      <span>{r.issue.container_kind === 'stream' ? 'Stream' : r.issue.release_version}</span>
                      {!activeProjectId && r.issue.project_name && <span className="ml-auto truncate">{r.issue.project_name}</span>}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : queue.length === 0 ? (
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
                      <PossibleDuplicates count={i.possible_duplicates_count} top={i.possible_duplicates_top} />
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
                      <AgentBadge show={i.via_agent} />
                      {!activeProjectId && i.project_name && <span className="ml-auto truncate">{i.project_name}</span>}
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {/* Right: the selected bug, its possible duplicates, and its outcomes */}
      <div className="min-h-0 bg-muted/40">
        {tab === 'returns' ? (
          selectedReturn
            ? <ReturnRequestDetail key={selectedReturn.id} row={selectedReturn} entries={returnEntries} onDecided={() => loadQueue()} />
            : !loading && <Empty icon="inbox" title="No request selected" body="Pick a return request from the queue to decide it." />
        ) : !selected ? (
          !loading && <Empty icon="inbox" title="No bug selected" body="Pick a bug from the queue to triage it." />
        ) : (
          <TriageDetail
            issue={selected}
            attachments={attachments}
            assignable={assignable}
            moveTargets={moveTargets}
            canMove={canMove}
            onMove={handleMove}
            onDone={handleDone}
            onDismissed={() => loadQueue()}
            onComputed={() => loadQueue()}
            toast={toast}
            showProject={!activeProjectId}
          />
        )}
      </div>
    </div>
  )
}
