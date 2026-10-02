import React, { useEffect, useState } from 'react'
import { Avatar } from '../ui/Avatar'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { PriorityBadge, RoleBadge, StatusBadge, TypeIcon } from '../ui/Badge'
import { ContainerBadge } from '../common/ContainerBadge'
import { LabelChip } from '../common/LabelChip'
import { MediaPreview } from '../common/MediaPreview'
import { SourceBadge } from '../common/SourceBadge'
import { attachmentsApi, issuesApi } from '../../lib/api'
import { normalizeAttachment } from '../../lib/attachments'
import { cn } from '../../lib/cn'
import { issueKey } from '../../lib/issueSlug'
import { relTime, fullTime } from '../../lib/relTime'
import { renderMarkdown } from '../../lib/markdown'
import { SimilarityRing, similarityBand } from './SimilarityRing'
import { mergeEffectSentence } from './mergeEffect'

function Section({ title, count, children }) {
  return (
    <section className="mt-5">
      <h5 className="mb-1.5 flex items-center gap-1.5 text-[10.5px] uppercase tracking-wide font-semibold text-muted-foreground">
        {title}
        {count != null && <span className="rounded-full bg-muted px-1.5 text-[10px] tabular-nums normal-case tracking-normal">{count}</span>}
      </h5>
      {children}
    </section>
  )
}

function None({ children }) {
  return <p className="text-[12px] text-muted-foreground/70">{children}</p>
}

function Skeleton() {
  return (
    <div className="mt-4 space-y-3" aria-hidden="true">
      <div className="h-4 w-3/4 rounded bg-muted animate-pulse" />
      <div className="h-20 rounded bg-muted animate-pulse" />
      <div className="h-12 rounded bg-muted animate-pulse" />
    </div>
  )
}

/** Everything the triager weighs when deciding two bugs are the same problem. */
function ItemColumn({ label, tone, item, attachments, loading }) {
  const reporter = item?.reporter_user
  const steps = item?.reproduction_steps ?? []
  return (
    <div className={cn(
      'min-w-0 rounded-lg border bg-background p-4',
      tone === 'candidate' ? 'border-amber-200 dark:border-amber-900/60' : 'border-border',
    )}>
      <p className={cn(
        'text-[10.5px] uppercase tracking-wide font-semibold',
        tone === 'candidate' ? 'text-amber-700 dark:text-amber-300' : 'text-muted-foreground',
      )}>{label}</p>

      {!item ? <Skeleton /> : (
        <>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <TypeIcon type={item.type} aria-hidden />
            <span className="font-mono text-[11.5px] text-muted-foreground">{issueKey(item)}</span>
            <StatusBadge status={item.status} />
            <PriorityBadge priority={item.priority} />
            <SourceBadge source={item.source} />
          </div>
          <h4 className="mt-2 text-[15px] font-semibold leading-snug">{item.title}</h4>

          <dl className="mt-3 grid grid-cols-[88px_1fr] gap-x-3 gap-y-1.5 text-[12px]">
            <dt className="text-muted-foreground">Reporter</dt>
            <dd className="flex min-w-0 items-center gap-1.5">
              <Avatar user={reporter} size={16} />
              <span className="truncate">{reporter?.name ?? 'Unknown'}</span>
              {reporter?.role && !(reporter.role === 'support' && item.source === 'support') && <RoleBadge role={reporter.role} />}
            </dd>
            <dt className="text-muted-foreground">Filed</dt>
            <dd title={fullTime(item.created_at)}>{relTime(item.created_at)}</dd>
            {item.recurrence_count > 1 && (<><dt className="text-muted-foreground">Reported</dt><dd>{item.recurrence_count} times</dd></>)}
            <dt className="text-muted-foreground">Project</dt>
            <dd className="truncate">{item.project_name ?? '—'}</dd>
            <dt className="text-muted-foreground">Placement</dt>
            <dd><ContainerBadge item={item} /></dd>
            {item.assignee_user && (<><dt className="text-muted-foreground">Assignee</dt>
              <dd className="flex items-center gap-1.5"><Avatar user={item.assignee_user} size={16} />{item.assignee_user.name}</dd></>)}
            {item.environment_name && (<><dt className="text-muted-foreground">Environment</dt><dd>{item.environment_name}</dd></>)}
            {item.labels_detail?.length > 0 && (
              <><dt className="text-muted-foreground">Labels</dt>
                <dd className="flex flex-wrap gap-1">{item.labels_detail.map(l => <LabelChip key={l.id ?? l.name} label={l} />)}</dd></>
            )}
          </dl>

          <Section title="Description">
            <div className="text-[12.5px] leading-relaxed text-foreground/90">
              {item.description ? renderMarkdown(item.description) : <None>No description.</None>}
            </div>
          </Section>

          {steps.length > 0 && (
            <Section title="Reproduction steps" count={steps.length}>
              <ol className="space-y-2">
                {steps.map((st, i) => (
                  <li key={st.id ?? i} className="rounded-md bg-muted/50 px-3 py-2 text-[12px]">
                    <p><span className="mr-1.5 font-semibold tabular-nums">{i + 1}.</span>{st.description}</p>
                    {st.expected_result && <p className="mt-1 text-muted-foreground"><span className="font-medium text-green-700 dark:text-green-400">Expected</span> {st.expected_result}</p>}
                    {st.actual_result && <p className="mt-0.5 text-muted-foreground"><span className="font-medium text-red-700 dark:text-red-400">Actual</span> {st.actual_result}</p>}
                  </li>
                ))}
              </ol>
            </Section>
          )}

          <Section title="Attachments" count={loading ? null : attachments.length}>
            {loading ? <div className="h-12 rounded bg-muted animate-pulse" aria-hidden="true" />
              : attachments.length > 0 ? <MediaPreview attachments={attachments} readonly />
              : <None><Icon name="paperclip" size={11} className="mr-1 inline" />No attachments.</None>}
          </Section>
        </>
      )}
    </div>
  )
}

/**
 * This bug and a candidate side by side — metadata, description, reproduction
 * steps and attachments — with the same actions as the candidate card. The
 * candidate is fetched in full; this bug's attachments come from the pane.
 */
export function DuplicateCompareDialog({ issue, attachments, hint, onClose, onMerge, onDismiss }) {
  const c = hint.candidate
  const band = similarityBand(hint.confidence)
  const [full, setFull] = useState(null)
  const [candidateAttachments, setCandidateAttachments] = useState(null)

  useEffect(() => {
    let cancelled = false
    setFull(null)
    setCandidateAttachments(null)
    issuesApi.get(c.id)
      .then((res) => { if (!cancelled) setFull(res.data) })
      .catch(() => { if (!cancelled) setFull({ ...c, description: '' }) })
    attachmentsApi.list(c.id)
      .then((res) => { if (!cancelled) setCandidateAttachments(res.data.map(normalizeAttachment)) })
      .catch(() => { if (!cancelled) setCandidateAttachments([]) })
    return () => { cancelled = true }
  }, [c.id])

  return (
    <Dialog open onClose={onClose} size="xl" className="max-w-6xl"
      title={`Compare ${issueKey(issue)} with ${c.key}`}>
      <div className="flex items-center gap-3 border-b border-border bg-amber-50/60 px-5 py-3 dark:bg-amber-950/20">
        <SimilarityRing confidence={hint.confidence} />
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-amber-800 dark:text-amber-300">{band.label}</p>
          <p className="text-[12px] text-muted-foreground">If merged: {mergeEffectSentence(hint)}</p>
        </div>
      </div>
      <div className="grid grid-cols-1 items-start gap-4 p-5 md:grid-cols-2">
        <ItemColumn label="This bug" item={issue} attachments={attachments} />
        <ItemColumn label="Candidate" tone="candidate" item={full} attachments={candidateAttachments ?? []} loading={candidateAttachments == null} />
      </div>
      <div className="sticky bottom-0 flex items-center gap-2 border-t border-border bg-card px-5 py-3">
        <a href={`/issue/${c.key.toLowerCase()}`} target="_blank" rel="noreferrer"
          className="inline-flex items-center gap-1 text-[12px] text-muted-foreground underline-offset-2 hover:underline">
          Open {c.key} <Icon name="external-link" size={11} aria-hidden="true" />
        </a>
        <Button variant="ghost" className="ml-auto text-muted-foreground" onClick={() => { onDismiss(hint); onClose() }}>
          Not a duplicate
        </Button>
        <Button onClick={() => { onMerge(c); onClose() }}>Merge into {c.key}</Button>
      </div>
    </Dialog>
  )
}
