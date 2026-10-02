import React, { useEffect, useState } from 'react'
import { Avatar } from '../ui/Avatar'
import { PriorityBadge, StatusBadge, RoleBadge } from '../ui/Badge'
import { Icon } from '../ui/Icon'
import { Tabs } from '../ui/Tabs'
import { Dropdown, DropdownItem, DropdownLabel } from '../ui/Dropdown'
import { cn } from '../../lib/cn'
import { MediaPreview } from '../common/MediaPreview'
import { SourceBadge } from '../common/SourceBadge'
import { useDuplicateHints } from '../../hooks/useDuplicateHints'
import { issueKey } from '../../lib/issueSlug'
import { relTime, fullTime } from '../../lib/relTime'
import { renderMarkdown } from '../../lib/markdown'
import { TriageOutcomePanel } from './TriageOutcomePanel'
import { DuplicateCandidateCard } from './DuplicateCandidateCard'
import { DuplicateCompareDialog } from './DuplicateCompareDialog'

/**
 * The right-hand pane of the triage page (slice 06, 14): a sticky header
 * (key, badges, Move to project, title, reporter), a **Details** / **Duplicates**
 * tab pair, and the outcome panel pinned at the bottom so a decision is always
 * one click away. The Duplicates tab exists for New bugs while Jev is on and
 * leads with the best match's similarity.
 */
export function TriageDetail({
  issue, attachments, assignable, moveTargets, canMove, onMove, onDone, onDismissed, onComputed, toast, showProject,
}) {
  const [tab, setTab] = useState('details')
  const [compare, setCompare] = useState(null)
  // A candidate's Merge opens the Duplicate outcome with it preselected (FR-S14).
  const [preset, setPreset] = useState(null)
  const hints = useDuplicateHints(issue, { onDismissed, onComputed })
  const top = hints.hints[0]
  const reporter = issue.reporter_user

  useEffect(() => { setTab('details'); setCompare(null) }, [issue.id])
  // The tab disappears with Jev or when the bug leaves New.
  useEffect(() => { if (tab === 'duplicates' && !hints.eligible) setTab('details') }, [tab, hints.eligible])

  const merge = (candidate) => setPreset({ issueId: issue.id, candidate })

  return (
    <div className="relative flex h-full min-h-0 flex-col" data-testid="triage-detail">
      <header className="shrink-0 border-b border-border bg-card px-5 py-3">
        <div className="flex items-center gap-2 mb-1.5">
          <a href={`/issue/${issueKey(issue).toLowerCase()}`} className="font-mono text-[12px] text-muted-foreground hover:underline">
            {issueKey(issue)}
          </a>
          <SourceBadge source={issue.source} />
          <PriorityBadge priority={issue.priority} />
          <StatusBadge status={issue.status} />
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
                    <DropdownItem key={p.id} onClick={() => { close(); onMove(p) }}>{p.name}</DropdownItem>
                  ))}
                </>
              )}
            </Dropdown>
          </div>
        </div>
        <h2 className="text-[17px] font-semibold leading-snug text-foreground">{issue.title}</h2>
        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Avatar user={reporter} size={14} />
          <span>{reporter?.name ?? 'Unknown reporter'}</span>
          {reporter?.role && !(reporter.role === 'support' && issue.source === 'support') && <RoleBadge role={reporter.role} />}
          <span aria-hidden="true">·</span>
          <span title={fullTime(issue.created_at)}>{relTime(issue.created_at)}</span>
          {showProject && issue.project_name && (<><span aria-hidden="true">·</span><span>{issue.project_name}</span></>)}
          {issue.recurrence_count > 1 && (<><span aria-hidden="true">·</span><span>Reported {issue.recurrence_count} times</span></>)}
        </div>
      </header>

      {hints.eligible && (
        <div className="shrink-0 border-b border-border bg-card px-5">
          <Tabs value={tab} onValueChange={setTab} className="border-b-0"
            options={[
              { value: 'details', label: 'Details' },
              {
                value: 'duplicates',
                label: (
                  <span className={cn('inline-flex items-center gap-1', top && 'text-amber-700 dark:text-amber-300')}>
                    <Icon name={hints.computing && !top ? 'loader' : 'copy'} size={12} aria-hidden="true"
                      className={hints.computing && !top ? 'animate-spin' : undefined} />
                    {top ? `Duplicates · ${Math.round(top.confidence * 100)}%` : 'Duplicates'}
                  </span>
                ),
                badge: hints.hints.length || undefined,
              },
            ]} />
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto px-5 py-4">
        {tab === 'duplicates' ? (
          <section aria-label="Possible duplicates" data-testid="duplicate-hints">
            <h3 className="flex items-center gap-1.5 text-[10.5px] uppercase tracking-wide font-semibold text-amber-700 dark:text-amber-300">
              <Icon name="copy" size={12} aria-hidden="true" />
              Possible duplicates{hints.hints.length ? ` (${hints.hints.length})` : ''}
            </h3>
            {hints.isLoading || (hints.computing && hints.hints.length === 0) ? (
              <div className="mt-2 rounded-lg border border-dashed border-border px-3 py-3 text-[12px] text-muted-foreground" role="status">
                <div className="mb-2 h-16 rounded-lg bg-muted animate-pulse" aria-hidden="true" />
                Looking for similar bugs…
              </div>
            ) : hints.hints.length === 0 ? (
              <p className="mt-2 rounded-lg border border-dashed border-border px-3 py-3 text-[12px] text-muted-foreground">
                No close matches — nothing reached the similarity threshold.
              </p>
            ) : (
              <ul className="mt-2 grid grid-cols-1 gap-3">
                {hints.hints.map(hint => (
                  <DuplicateCandidateCard key={hint.candidate_id} hint={hint}
                    onMerge={merge} onCompare={setCompare} onDismiss={hints.dismiss} />
                ))}
              </ul>
            )}
          </section>
        ) : (
          <div>
            <div className="text-[13px] text-foreground/90 leading-relaxed max-w-none">
              {issue.description
                ? renderMarkdown(issue.description)
                : <span className="text-muted-foreground">No description provided.</span>}
            </div>
            {attachments.length > 0
              ? <MediaPreview key={issue.id} attachments={attachments} readonly />
              : (
                <div className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground/60">
                  <Icon name="paperclip" size={11} />
                  <span>No attachments</span>
                </div>
              )}
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-border bg-card px-5 pb-4 max-h-[62%] overflow-y-auto">
        <TriageOutcomePanel
          issue={issue}
          assignable={assignable}
          onDone={onDone}
          toast={toast}
          presetOriginal={preset?.issueId === issue.id ? preset.candidate : null}
        />
      </div>

      {compare && (
        <DuplicateCompareDialog issue={issue} attachments={attachments} hint={compare} onClose={() => setCompare(null)}
          onMerge={merge} onDismiss={hints.dismiss} />
      )}
    </div>
  )
}
