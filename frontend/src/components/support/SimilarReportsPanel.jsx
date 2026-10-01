import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { StatusBadge, TypeIcon } from '../ui'
import { Icon } from '../ui/Icon'
import { issuesApi } from '../../lib/api'
import { useApp } from '../../hooks/useApp'
import { useToast } from '../../hooks/useToast'
import { useSimilarItems } from '../../hooks/useSimilarItems'
import { issueSlug } from '../../lib/issueSlug'
import { composeReport } from '../../lib/supportCompose'

// "Similar reports" — open support reports of the project that are the same
// problem, under the title while Support writes (slice 14, FR-S09/S10,
// BR-S07). Shown once the title and at least one template text field are
// filled; only `same` verdicts, never Done/Cancelled/non-support/other-project
// items (the API enforces all of that). **This is the same problem — record
// recurrence** adds this form's composed content and attachments to that item
// and counts it once more — no new report is created (BR-S50).
export function SimilarReportsPanel({
  projectId,
  template,
  title,
  values,
  description,
  complete,
  pendingAttachments = [],
  onRecorded,
}) {
  const { features } = useApp()
  const { toast } = useToast()
  const [recording, setRecording] = useState(null) // the suggestion being confirmed
  const [submitting, setSubmitting] = useState(false)

  // One filled template text field, beyond the title, before the panel appears.
  const textFilled = (template?.fields ?? []).some(
    (f) =>
      ['short_text', 'long_text'].includes(f.field_type) &&
      String(values?.[f.id] ?? '').trim(),
  )
  const items = useSimilarItems({
    enabled: Boolean(features?.jev_enabled) && textFilled,
    context: 'support',
    projectId,
    title,
    description,
  })
  if (!items?.length) return null

  const composed = template
    ? composeReport(template, values, description)
    : (description ?? '').trim()

  async function record(suggestion) {
    setSubmitting(true)
    try {
      const res = await issuesApi.reportRecurrence(suggestion.issue.id, {
        comment: composed,
        pending_attachments: pendingAttachments,
      })
      const report = res.data
      toast({
        title: `Recurrence recorded on ${report.key}`,
        body: (
          <span>
            Reported {report.recurrence_count} times now.{' '}
            <Link
              to={`/issue/${issueSlug({ type: 'bug', issue_number: report.issue_number })}`}
              className="underline underline-offset-2"
            >
              View report
            </Link>
          </span>
        ),
      })
      setRecording(null)
      onRecorded?.()
    } catch (err) {
      const data = err.response?.data
      toast({ title: 'Could not record the recurrence', body: data?.detail || 'Try again in a moment.' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section
      aria-label="Similar reports"
      className="rounded-[var(--radius)] border border-amber-200 bg-amber-50/60 p-3 dark:border-amber-900/60 dark:bg-amber-950/20"
      data-testid="similar-reports"
    >
      <h3 className="flex items-center gap-1.5 text-xs font-medium text-amber-800 dark:text-amber-300">
        <Icon name="copy" size={13} aria-hidden />
        Similar reports
      </h3>
      <ul className="mt-2 space-y-2">
        {items.map(({ issue }) => (
          <li
            key={issue.id}
            className="flex items-start gap-2 rounded-md border border-border/60 bg-background px-2.5 py-2"
          >
            <span className="mt-0.5 flex min-w-0 flex-1 items-start gap-2">
              <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <TypeIcon type={issue.type} aria-hidden />
                <span className="font-mono">{issue.key}</span>
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[13px] text-foreground">{issue.title}</span>
                <StatusBadge status={issue.status} className="mt-0.5" />
              </span>
            </span>
            <Button
              size="sm"
              variant="outline"
              className="mt-0.5 shrink-0"
              disabled={!complete}
              title={complete ? undefined : 'Fill the required fields first'}
              onClick={() => setRecording({ issue })}
            >
              This is the same problem
            </Button>
          </li>
        ))}
      </ul>
      {!complete && (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Fill the required fields first to record a recurrence.
        </p>
      )}

      <Dialog
        open={Boolean(recording)}
        onClose={() => setRecording(null)}
        title="Record a recurrence"
        size="md"
      >
        <div className="flex flex-col max-h-[calc(90vh-120px)]">
          <p className="px-5 pt-4 text-sm text-muted-foreground">
            Your answers will be added to{' '}
            <strong className="font-semibold text-foreground">
              {recording?.issue.key} · {recording?.issue.title}
            </strong>{' '}
            as one more occurrence — no new report is created, and you'll be subscribed to its
            updates.
          </p>
          <div
            className="mx-5 my-3 flex-1 overflow-y-auto rounded-[var(--radius)] border border-border bg-muted/30 p-3 text-[13px] leading-relaxed text-foreground scrollbar-thin"
            data-testid="recurrence-preview"
          >
            <pre className="whitespace-pre-wrap font-sans">{composed}</pre>
          </div>
          <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
            <Button variant="ghost" onClick={() => setRecording(null)} disabled={submitting}>
              Keep editing
            </Button>
            <Button onClick={() => record(recording)} disabled={submitting}>
              {submitting ? 'Recording…' : 'Record recurrence'}
            </Button>
          </div>
        </div>
      </Dialog>
    </section>
  )
}
