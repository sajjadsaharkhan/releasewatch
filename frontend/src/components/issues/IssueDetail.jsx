import React, { useState, useEffect, useMemo } from 'react'
import { ChevronLeft, ChevronUp, ChevronDown, Link as LinkIcon, Check, MoreVertical, CheckCircle, Shield, Undo2, RefreshCw } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { SeverityBadge, StatusBadge, Badge, RoleBadge } from '../ui/Badge'
import { Avatar } from '../ui/Avatar'
import { Dropdown, DropdownItem, DropdownLabel, DropdownSep } from '../ui/Dropdown'
import { Dialog } from '../ui/Dialog'
import { Switch } from '../ui/Switch'
import { Icon } from '../ui/Icon'
import { Tabs } from '../ui/Tabs'
import { LabelChip } from '../common/LabelChip'
import { MetaRow } from './MetaRow'
import { TimeMetric } from './TimeMetric'
import { DescriptionSection } from './DescriptionSection'
import { AttachmentsSection } from './AttachmentsSection'
import { RegressionTimelineSection } from './RegressionTimelineSection'
import { IssueTimeline } from './IssueTimeline'
import { relTime } from '../../lib/relTime'
import { userById, MOCK_TEAM, MOCK_PROJECTS, MOCK_RELEASES, SEVERITY, STATUS, MOCK_LABELS } from '../../data/mockData'
import { teamApi } from '../../lib/api'
import { ENVIRONMENT } from './DescriptionSection'

export function IssueDetail({ issue, onUpdate, onClose, onNavigate }) {
  const [tab, setTab] = useState('activity')
  const [events, setEvents] = useState([])
  const [comments, setComments] = useState([])
  const [copied, setCopied] = useState(false)
  const [localIssue, setLocalIssue] = useState(issue)
  const [labelPickerOpen, setLabelPickerOpen] = useState(false)
  const [teamUsers, setTeamUsers] = useState([])

  useEffect(() => {
    teamApi.list().then(res => setTeamUsers(res.data || [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (!localIssue) return
    // Use the actual events and comments from the issue data
    setEvents(localIssue.events || [])
    setComments(localIssue.comments || [])
    setTab('activity')
  }, [localIssue?.id, localIssue?.events, localIssue?.comments])

  useEffect(() => {
    setLocalIssue(issue)
  }, [issue])

  function update(patch) {
    const updated = { ...localIssue, ...patch }
    setLocalIssue(updated)
    onUpdate?.(updated)
  }

  const addComment = (body, isInternal, mentionedUserIds) => {
    const next = {
      id: 'c' + Math.random().toString(36).slice(2, 7),
      author: 'u-1', // Current user (Sajjad)
      body: body,
      createdAt: new Date().toISOString(),
      isInternal: isInternal,
      mentionedUsers: mentionedUserIds || [],
    }
    setComments(c => [...c, next])
  }

  const changeStatus = (newStatus) => {
    const newEvent = {
      id: 'e' + Math.random().toString(36).slice(2, 7),
      type: 'status_changed',
      actor: 'u-1',
      timestamp: new Date().toISOString(),
      from: localIssue.status,
      to: newStatus,
    }
    setEvents(e => [...e, newEvent])
    update({ status: newStatus })
  }

  const changeAssignee = (uId) => {
    const newEvent = {
      id: 'a' + Math.random().toString(36).slice(2, 7),
      type: 'assigned',
      actor: 'u-1',
      timestamp: new Date().toISOString(),
      detail: uId,
    }
    setEvents(e => [...e, newEvent])
    update({ assignee: uId })
  }

  const copyLink = () => {
    const url = window.location.origin + window.location.pathname + '#/issue/issue-' + localIssue.issue_number
    navigator.clipboard?.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 1400)
  }

  const assignee = userById(localIssue.assignee)
  const reporter = userById(localIssue.reporter)
  const release = MOCK_RELEASES.find(r => r.id === localIssue.releaseId)
  const project = MOCK_PROJECTS.find(p => p.id === localIssue.projectId)
  const labels = (localIssue.labels || []).map(labelIdOrName => {
    const label = MOCK_LABELS.find(l => l.id === labelIdOrName || l.name === labelIdOrName)
    return label || { id: labelIdOrName, name: labelIdOrName, color: '#6366f1' }
  })

  // Compute time metrics
  const ttTriage = localIssue.triagedAt
    ? (new Date(localIssue.triagedAt) - new Date(localIssue.createdAt)) / 36e5
    : null
  const ttFix = localIssue.fixedAt
    ? (new Date(localIssue.fixedAt) - new Date(localIssue.createdAt)) / 36e5
    : null
  const ttVerify = localIssue.verifiedAt && localIssue.fixedAt
    ? (new Date(localIssue.verifiedAt) - new Date(localIssue.fixedAt)) / 36e5
    : null

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header bar */}
      <div className="h-14 px-7 border-b border-zinc-200 dark:border-zinc-800 flex items-center gap-3 shrink-0 bg-white dark:bg-zinc-950">
        <button onClick={onClose} className="inline-flex items-center gap-1 text-[12px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 -ml-2 px-2 h-8 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800">
          <ChevronLeft size={13} /> Back to issues
        </button>
        <div className="h-5 w-px bg-zinc-200 dark:bg-zinc-800" />
        <div className="font-mono text-[12px] text-zinc-500">issue-{localIssue.issue_number}</div>
        <div className="flex items-center gap-1.5">
          <SeverityBadge severity={localIssue.severity} dot />
          <StatusBadge status={localIssue.status} />
          {localIssue.is_regression && (
            <Badge tone="red">
              <RefreshCw size={10} />
              {' '}Regression
            </Badge>
          )}
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <Button variant="outline" size="sm" onClick={copyLink}>
            {copied ? <Check size={12} className="text-green-500" /> : <LinkIcon size={12} />} {copied ? 'Copied' : 'Share'}
          </Button>
          <Button variant="ghost" size="icon" onClick={() => onNavigate?.('prev')} title="Previous issue">
            <ChevronUp size={15} />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => onNavigate?.('next')} title="Next issue">
            <ChevronDown size={15} />
          </Button>
          <Dropdown align="right" trigger={<Button variant="ghost" size="icon"><MoreVertical size={15} /></Button>}>
            <DropdownItem>Mark duplicate…</DropdownItem>
            <DropdownItem>Archive</DropdownItem>
            <DropdownSep />
            <DropdownItem destructive>Delete</DropdownItem>
          </Dropdown>
        </div>
      </div>

      {/* Body — two columns */}
      <div className="flex-1 min-h-0 grid grid-cols-[1fr_320px]">
        {/* Left main */}
        <div className="overflow-y-auto px-7 py-6 max-w-[820px] mx-auto w-full">
          <h1 className="text-[22px] font-semibold leading-snug text-zinc-900 dark:text-zinc-100">{localIssue.title}</h1>
          <div className="mt-1.5 flex items-center gap-2 text-[12px] text-zinc-500 flex-wrap">
            <span>Filed by</span>
            <Avatar user={reporter} size={16} /> <span className="text-zinc-700 dark:text-zinc-200">{reporter?.name}</span>
            {localIssue.reporterRole && <RoleBadge role={localIssue.reporterRole} />}
            <span>·</span>
            <span>{relTime(localIssue.createdAt)}</span>
            <span>·</span>
            <span className="font-mono">{release?.version || localIssue.release}</span>
          </div>

          <div className="mt-4">
            <Tabs
              value={tab}
              onValueChange={setTab}
              options={[
                { value: 'activity', label: 'Activity', icon: 'activity', badge: events.length + comments.length },
                { value: 'evidence', label: 'Attachments', icon: 'paperclip', badge: localIssue.attachments?.length || null },
                { value: 'regression', label: 'Regression history', icon: 'refresh-ccw', badge: localIssue.regressionHistory?.length || null },
              ]}
            />
          </div>

          <div className="mt-5">
            {tab === 'activity' && (
              <>
                <DescriptionSection
                  issue={localIssue}
                  onDescriptionUpdate={(desc) => update({ description: desc })}
                  onCurlUpdate={(curl) => update({ curlCommand: curl })}
                  onStepsUpdate={(steps) => update({ steps: steps })}
                />
                <div className="my-6 border-t border-zinc-200 dark:border-zinc-800" />
                <IssueTimeline
                  events={events}
                  comments={comments}
                  issue={localIssue}
                  users={teamUsers}
                  onAddComment={addComment}
                  onUpdateComment={(commentId, body, isInternal, mentionedUserIds, editedAt) => {
                    setComments(c => c.map(cm => cm.id === commentId ? { ...cm, body, isInternal, mentionedUsers: mentionedUserIds || [], editedAt } : cm))
                  }}
                  onDeleteComment={(commentId) => {
                    setComments(c => c.filter(cm => cm.id !== commentId))
                  }}
                />
              </>
            )}
            {tab === 'evidence' && <AttachmentsSection issue={localIssue} onAttachmentsChange={(atts) => update({ attachments: atts })} issueId={localIssue.id} />}
            {tab === 'regression' && <RegressionTimelineSection issue={localIssue} />}
          </div>
        </div>

        {/* Right metadata */}
        <aside className="border-l border-zinc-200 dark:border-zinc-800 overflow-y-auto bg-zinc-50/60 dark:bg-zinc-900/40 px-4 py-5 text-[13px]">
          <MetaRow label="Status">
            <Dropdown width={170} trigger={<button className="w-full text-left"><StatusBadge status={localIssue.status} /></button>}>
              {({ close }) => (
                <>
                  {Object.keys(STATUS).map(s => (
                    <DropdownItem key={s} onClick={() => { changeStatus(s); close(); }}>
                      <StatusBadge status={s} size="sm" />
                    </DropdownItem>
                  ))}
                </>
              )}
            </Dropdown>
          </MetaRow>

          <MetaRow label="Severity">
            <Dropdown width={170} trigger={<button className="w-full text-left"><SeverityBadge severity={localIssue.severity} dot /></button>}>
              {({ close }) => (
                <>
                  {Object.keys(SEVERITY).map(s => (
                    <DropdownItem key={s} onClick={() => { update({ severity: s }); close(); }}>
                      <SeverityBadge severity={s} dot size="sm" />
                    </DropdownItem>
                  ))}
                </>
              )}
            </Dropdown>
          </MetaRow>

          <MetaRow label="Assignee">
            <Dropdown
              width={220}
              trigger={
                <button className="inline-flex items-center gap-2 text-zinc-800 dark:text-zinc-200">
                  {assignee
                    ? <><Avatar user={assignee} size={18} /><span>{assignee.name}</span></>
                    : <span className="text-zinc-400">Unassigned</span>}
                  <ChevronDown size={12} className="text-zinc-400 ml-1" />
                </button>
              }
            >
              {({ close }) => (
                <>
                  <DropdownLabel>Assign to</DropdownLabel>
                  {MOCK_TEAM.filter(u => u.role === 'developer').map(u => (
                    <DropdownItem key={u.id} onClick={() => { changeAssignee(u.id); close(); }}>
                      <Avatar user={u} size={18} />
                      <div className="flex-1 flex items-center justify-between">
                        <span>{u.name}</span>
                      </div>
                    </DropdownItem>
                  ))}
                </>
              )}
            </Dropdown>
          </MetaRow>

          <MetaRow label="Reporter">
            <div className="inline-flex items-center gap-2">
              <Avatar user={reporter} size={18} />
              <span className="text-zinc-700 dark:text-zinc-200">{reporter?.name}</span>
              {localIssue.reporterRole && <RoleBadge role={localIssue.reporterRole} />}
            </div>
          </MetaRow>

          <MetaRow label="Release">
            <span className="font-mono text-zinc-800 dark:text-zinc-200">{release?.version || localIssue.release || '—'}</span>
          </MetaRow>

          <MetaRow label="Project">
            <span className="text-zinc-700 dark:text-zinc-200">{project?.name || '—'}</span>
          </MetaRow>

          <MetaRow label="Environment">
            <Dropdown width={160} trigger={
              <button className="w-full text-left">
                <Badge tone={ENVIRONMENT[localIssue.environmentName]?.tone || 'default'}>
                  {ENVIRONMENT[localIssue.environmentName]?.label || localIssue.environmentName || '—'}
                </Badge>
              </button>
            }>
              {({ close }) => (
                <>
                  {Object.values(ENVIRONMENT).map(env => (
                    <DropdownItem key={env.value} onClick={() => { update({ environmentName: env.value }); close(); }}>
                      <Badge tone={env.tone} size="sm">{env.label}</Badge>
                    </DropdownItem>
                  ))}
                </>
              )}
            </Dropdown>
          </MetaRow>

          <MetaRow label="Labels">
            <div className="flex flex-wrap gap-1">
              {labels.map(l => <LabelChip key={l.id} label={l} removable onRemove={() => {
                const updated = { ...localIssue, labels: (localIssue.labels || []).filter(lab => lab !== l.id && lab !== l.name) }
                update(updated)
              }} />)}
              <button
                onClick={() => setLabelPickerOpen(true)}
                className="inline-flex items-center rounded px-1.5 py-0.5 text-[11px] text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
              >
                <Icon name="plus" size={10} className="mr-0.5" /> Add
              </button>
            </div>
          </MetaRow>

          <MetaRow label="Regressions">
            <Badge tone={localIssue.regressionCount > 0 ? "red" : "default"}>
              <RefreshCw size={10} />
              {' '}{localIssue.regressionCount > 0 ? localIssue.regressionCount : 'None'}
            </Badge>
          </MetaRow>

          <MetaRow label="Release blocker">
            <Switch
              checked={localIssue.is_release_blocker}
              onCheckedChange={(v) => update({ is_release_blocker: v })}
            />
          </MetaRow>


          <div className="mt-4 pt-3 border-t border-zinc-200 dark:border-zinc-800 space-y-2">
            <TimeMetric label="Time in triage" value={ttTriage ? `${Math.round(ttTriage)}h ${Math.round((ttTriage % 1) * 60)}m` : '0h 0m'} tone="green" />
            <TimeMetric label="Time to fix" value={ttFix ? `${Math.round(ttFix)}h` : 'in-flight'} tone={ttFix ? 'default' : 'amber'} />
            <TimeMetric label="Time to verify" value={localIssue.status === 'verified' && ttVerify ? `${Math.round(ttVerify)}h` : '—'} />
          </div>

          <div className="mt-5 pt-3 border-t border-zinc-200 dark:border-zinc-800 space-y-2">
            {localIssue.status !== 'fixed' && localIssue.status !== 'verified' && (
              <Button className="w-full" onClick={() => changeStatus('fixed')}>
                <Check size={14} className="mr-1" /> Mark as Fixed
              </Button>
            )}
            {localIssue.status === 'fixed' && (
              <Button variant="success" className="w-full" onClick={() => changeStatus('verified')}>
                <Shield size={14} className="mr-1" /> Verify fix
              </Button>
            )}
            {(localIssue.status === 'fixed' || localIssue.status === 'verified' || localIssue.status === 'closed') && (
              <Button variant="outline" className="w-full" onClick={() => changeStatus('regression')}>
                <RefreshCw size={14} className="mr-1" /> Mark as Regression
              </Button>
            )}
            <Button variant="outline" className="w-full" onClick={() => changeStatus('new')}>
              <Undo2 size={14} className="mr-1" /> Re-open
            </Button>
          </div>
        </aside>
      </div>

      {/* Label Picker Dialog */}
      <Dialog open={labelPickerOpen} onClose={() => setLabelPickerOpen(false)} title="Add label" size="sm">
        <div className="p-4 space-y-1">
          {MOCK_LABELS.map(label => {
            const isAdded = localIssue.labels?.includes(label.id) || localIssue.labels?.includes(label.name)
            return (
              <button
                key={label.id}
                onClick={() => {
                  if (!isAdded) {
                    update({ labels: [...(localIssue.labels || []), label.id] })
                    setLabelPickerOpen(false)
                  }
                }}
                disabled={isAdded}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors',
                  'border border-zinc-200 dark:border-zinc-800',
                  'hover:bg-zinc-50 dark:hover:bg-zinc-900',
                  isAdded && 'opacity-50 cursor-not-allowed hover:bg-transparent'
                )}
              >
                <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: label.color }} />
                <span className="text-sm font-medium text-zinc-700 dark:text-zinc-200">{label.name}</span>
                {isAdded && <span className="ml-auto text-xs text-zinc-400">Added</span>}
              </button>
            )
          })}
        </div>
      </Dialog>
    </div>
  )
}
