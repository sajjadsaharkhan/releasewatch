import React, { useState } from 'react'
import { Copy, Check, ExternalLink } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { SeverityBadge, StatusBadge } from '../ui/Badge'
import { Avatar } from '../ui/Avatar'
import { Dropdown, DropdownItem } from '../ui/Dropdown'
import { IssueTimeline } from './IssueTimeline'
import { CommentComposer } from './CommentComposer'
import { AttachmentTile } from './AttachmentTile'
import { RegressionTimeline } from './RegressionTimeline'
import { LabelChip } from '../common/LabelChip'
import { renderMarkdown } from '../../lib/markdown'
import { relTime, formatDuration } from '../../lib/relTime'
import {
  userById, releaseById, MOCK_TEAM, MOCK_RELEASES, MOCK_LABELS, SEVERITY, STATUS,
} from '../../data/mockData'

function EnvTile({ label, value }) {
  if (!value) return null
  return (
    <div className="rounded-lg border border-border bg-muted/50 px-3 py-2">
      <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
      <p className="text-xs font-mono font-medium truncate">{value}</p>
    </div>
  )
}

function SidebarRow({ label, children }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
      <div>{children}</div>
    </div>
  )
}

export function IssueDetail({ issue, onUpdate }) {
  const [copied, setCopied] = useState(false)
  const [commentLoading, setCommentLoading] = useState(false)
  const [localIssue, setLocalIssue] = useState(issue)

  function update(patch) {
    const updated = { ...localIssue, ...patch }
    setLocalIssue(updated)
    onUpdate?.(updated)
  }

  function copyCurl() {
    navigator.clipboard.writeText(localIssue.curlCommand ?? '')
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function handleComment(body, isInternal) {
    setCommentLoading(true)
    setTimeout(() => {
      const newComment = {
        id: `cmt-${Date.now()}`,
        author: 'u-1',
        body,
        createdAt: new Date().toISOString(),
        isInternal,
      }
      update({ comments: [...(localIssue.comments ?? []), newComment] })
      setCommentLoading(false)
    }, 600)
  }

  const assignee = userById(localIssue.assignee)
  const reporter = userById(localIssue.reporter)
  const release = releaseById(localIssue.releaseId)
  const labels = (localIssue.labels ?? []).map((lId) => MOCK_LABELS.find((l) => l.id === lId)).filter(Boolean)

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
    <div className="flex gap-0 h-full">
      {/* ── Main content ── */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-6 space-y-6">
        {/* Issue header */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="font-mono text-sm text-muted-foreground">{localIssue.id}</span>
            {localIssue.is_regression && (
              <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                Regression
              </span>
            )}
            {localIssue.is_release_blocker && (
              <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700 dark:bg-orange-900/30 dark:text-orange-400">
                Release Blocker
              </span>
            )}
          </div>
          <h1 className="text-xl font-bold">{localIssue.title}</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Filed by {reporter?.name} · {relTime(localIssue.createdAt)}
          </p>
        </div>

        {/* Description */}
        <section>
          <h3 className="text-sm font-semibold mb-3">Description</h3>
          <div className="prose-sm">{renderMarkdown(localIssue.description)}</div>
        </section>

        {/* Environment */}
        {localIssue.environment && (
          <section>
            <h3 className="text-sm font-semibold mb-3">Environment</h3>
            <div className="grid grid-cols-2 gap-2">
              <EnvTile label="Browser" value={localIssue.environment.browser} />
              <EnvTile label="OS" value={localIssue.environment.os} />
              <EnvTile label="Build hash" value={localIssue.environment.build} />
              <EnvTile label="Staging URL" value={localIssue.environment.staging} />
            </div>
          </section>
        )}

        {/* cURL */}
        {localIssue.curlCommand && (
          <section>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold">cURL command</h3>
              <Button variant="ghost" size="sm" onClick={copyCurl}>
                {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? 'Copied' : 'Copy'}
              </Button>
            </div>
            <pre className="overflow-x-auto rounded-lg border border-border bg-zinc-950 p-4 text-xs text-zinc-100 font-mono scrollbar-thin">
              <code>{localIssue.curlCommand}</code>
            </pre>
          </section>
        )}

        {/* Steps */}
        {localIssue.steps && localIssue.steps.length > 0 && (
          <section>
            <h3 className="text-sm font-semibold mb-3">Steps to reproduce</h3>
            <ol className="list-decimal list-inside space-y-1.5">
              {localIssue.steps.map((step, idx) => (
                <li key={idx} className="text-sm text-foreground">{step}</li>
              ))}
            </ol>
          </section>
        )}

        {/* Attachments */}
        {localIssue.attachments && localIssue.attachments.length > 0 && (
          <section>
            <h3 className="text-sm font-semibold mb-3">Attachments</h3>
            <div className="grid grid-cols-2 gap-3">
              {localIssue.attachments.map((att) => (
                <AttachmentTile key={att.id} attachment={att} />
              ))}
            </div>
          </section>
        )}

        {/* Timeline */}
        <section>
          <h3 className="text-sm font-semibold mb-4">Activity</h3>
          <IssueTimeline events={localIssue.events ?? []} comments={localIssue.comments ?? []} issue={localIssue} />
        </section>

        {/* Composer */}
        <CommentComposer onSubmit={handleComment} loading={commentLoading} />
      </div>

      {/* ── Sidebar ── */}
      <aside className="w-72 shrink-0 border-l border-border overflow-y-auto scrollbar-thin p-4 space-y-5">
        {/* Status */}
        <SidebarRow label="Status">
          <Dropdown
            trigger={<StatusBadge status={localIssue.status} className="cursor-pointer" />}
          >
            {Object.entries(STATUS).map(([k, v]) => (
              <DropdownItem key={k} onClick={() => update({ status: k })}>
                <StatusBadge status={k} />
              </DropdownItem>
            ))}
          </Dropdown>
        </SidebarRow>

        {/* Severity */}
        <SidebarRow label="Severity">
          <Dropdown
            trigger={<SeverityBadge severity={localIssue.severity} className="cursor-pointer" />}
          >
            {Object.entries(SEVERITY).map(([k]) => (
              <DropdownItem key={k} onClick={() => update({ severity: k })}>
                <SeverityBadge severity={k} />
              </DropdownItem>
            ))}
          </Dropdown>
        </SidebarRow>

        {/* Assignee */}
        <SidebarRow label="Assignee">
          <Dropdown
            trigger={
              <button className="flex items-center gap-2 text-sm hover:text-primary transition-colors">
                {assignee ? (
                  <>
                    <Avatar user={assignee} size={20} />
                    <span>{assignee.name}</span>
                  </>
                ) : (
                  <span className="text-muted-foreground">Unassigned</span>
                )}
              </button>
            }
          >
            <DropdownItem onClick={() => update({ assignee: null })}>Unassigned</DropdownItem>
            {MOCK_TEAM.map((u) => (
              <DropdownItem key={u.id} onClick={() => update({ assignee: u.id })}>
                <Avatar user={u} size={18} />
                {u.name}
              </DropdownItem>
            ))}
          </Dropdown>
        </SidebarRow>

        {/* Release */}
        <SidebarRow label="Release">
          <Dropdown
            trigger={
              <button className="text-sm font-mono hover:text-primary transition-colors">
                {release?.version ?? <span className="text-muted-foreground">None</span>}
              </button>
            }
          >
            <DropdownItem onClick={() => update({ releaseId: null })}>None</DropdownItem>
            {MOCK_RELEASES.map((r) => (
              <DropdownItem key={r.id} onClick={() => update({ releaseId: r.id })}>
                {r.version}
              </DropdownItem>
            ))}
          </Dropdown>
        </SidebarRow>

        {/* Labels */}
        <SidebarRow label="Labels">
          <div className="flex flex-wrap gap-1.5">
            {labels.map((l) => <LabelChip key={l.id} label={l} />)}
            {labels.length === 0 && <span className="text-xs text-muted-foreground">None</span>}
          </div>
        </SidebarRow>

        {/* Time metrics */}
        {(ttTriage !== null || ttFix !== null) && (
          <SidebarRow label="Time metrics">
            <div className="space-y-1.5">
              {ttTriage !== null && (
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Time to triage</span>
                  <span className="font-medium">{formatDuration(ttTriage)}</span>
                </div>
              )}
              {ttFix !== null && (
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Time to fix</span>
                  <span className="font-medium">{formatDuration(ttFix)}</span>
                </div>
              )}
              {ttVerify !== null && (
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Time to verify</span>
                  <span className="font-medium">{formatDuration(ttVerify)}</span>
                </div>
              )}
            </div>
          </SidebarRow>
        )}

        {/* Actions */}
        <SidebarRow label="Actions">
          <div className="flex flex-col gap-1.5">
            {localIssue.status !== 'fixed' && localIssue.status !== 'verified' && (
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
                onClick={() => update({ status: 'fixed', fixedAt: new Date().toISOString() })}
              >
                Mark Fixed
              </Button>
            )}
            {localIssue.status === 'fixed' && (
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start text-green-600 border-green-300 hover:bg-green-50 dark:hover:bg-green-900/10"
                onClick={() => update({ status: 'verified', verifiedAt: new Date().toISOString() })}
              >
                Verify Fix
              </Button>
            )}
            {!localIssue.is_regression && (
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start text-amber-600 border-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/10"
                onClick={() => update({ status: 'regression', is_regression: true })}
              >
                Mark Regression
              </Button>
            )}
            {(localIssue.status === 'fixed' || localIssue.status === 'closed') && (
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
                onClick={() => update({ status: 'new', fixedAt: null, verifiedAt: null })}
              >
                Reopen
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start text-muted-foreground"
              onClick={() => {}}
            >
              Link Duplicate…
            </Button>
          </div>
        </SidebarRow>

        {/* Regression timeline */}
        {localIssue.is_regression && localIssue.regressionHistory && (
          <SidebarRow label="">
            <RegressionTimeline regressionHistory={localIssue.regressionHistory} />
          </SidebarRow>
        )}
      </aside>
    </div>
  )
}
