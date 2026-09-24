import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Icon } from '../ui/Icon'
import { ProjectSwitcher } from '../common/ProjectSwitcher'
import { CommentComposer } from '../issues/CommentComposer'
import { AttachmentsSection } from '../issues/AttachmentsSection'
import { FieldShell, TemplateFields, checkFieldValue, isBlank } from './TemplateFields'
import { supportApi } from '../../lib/api'
import { issueSlug } from '../../lib/issueSlug'
import { useToast } from '../../hooks/useToast'

// Support's New report (slice 05, FR-07–10) — the same modal shell and project
// picker tech users get in New issue. Pick a project, pick what's wrong (a
// template), fill its fields, give it a title. The server composes the fields
// into the bug's description.

export function SupportReportModal({ open, onClose, onSubmitted, initialDescription = '' }) {
  const { toast } = useToast()

  const [projects, setProjects] = useState(null)
  const [projectId, setProjectId] = useState(null)
  const [templates, setTemplates] = useState(null)
  const [templateId, setTemplateId] = useState(null)
  const [values, setValues] = useState({})
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [attachments, setAttachments] = useState([])
  const [pendingAttachments, setPendingAttachments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  // The template a 409 retired mid-fill — its fields stay on screen (AC-05).
  const [retired, setRetired] = useState(null)
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const [composerKey, setComposerKey] = useState(0)

  function reset() {
    setTemplateId(null)
    setValues({})
    setTitle('')
    setDescription('')
    setAttachments([])
    setPendingAttachments([])
    setErrors({})
    setRetired(null)
    setComposerKey((k) => k + 1)
  }

  // "New report referencing this" (slice 07) opens with the old key already
  // written into the description, so triage sees the link.
  useEffect(() => {
    if (!open || !initialDescription) return
    setDescription(initialDescription)
    setComposerKey((k) => k + 1)
  }, [open, initialDescription])

  useEffect(() => {
    if (!open) return
    supportApi.projects()
      .then((res) => {
        setProjects(res.data)
        setProjectId((cur) => (res.data.some((p) => p.id === cur) ? cur : res.data[0]?.id ?? null))
      })
      .catch(() => setProjects([]))
  }, [open])

  useEffect(() => {
    if (!open || !projectId) return
    setTemplates(null)
    supportApi.templates(projectId)
      .then((res) => {
        setTemplates(res.data)
        setTemplateId((cur) => {
          if (res.data.some((t) => t.id === cur)) return cur
          return res.data.length === 1 ? res.data[0].id : null
        })
      })
      .catch(() => setTemplates([]))
  }, [open, projectId])

  const template = useMemo(
    () => templates?.find((t) => t.id === templateId) ?? retired,
    [templates, templateId, retired]
  )
  const dirty = Boolean(
    title.trim() || description.trim() || pendingAttachments.length ||
    Object.values(values).some((v) => !isBlank(v))
  )

  function requestClose() {
    if (confirmDiscard) return
    if (dirty && !submitting) setConfirmDiscard(true)
    else { reset(); onClose() }
  }

  function discard() {
    setConfirmDiscard(false)
    reset()
    onClose()
  }

  function chooseProject(id) {
    if (id === projectId) return
    setProjectId(id)
    setTemplateId(null)
    setRetired(null)
    setErrors({})
  }

  function chooseTemplate(id) {
    setTemplateId(id)
    setRetired(null)
    setErrors((e) => ({ title: e.title }))
  }

  function setValue(fieldId, v) {
    setValues((prev) => ({ ...prev, [fieldId]: v }))
    if (errors[fieldId]) {
      const field = template?.fields.find((f) => f.id === fieldId)
      setErrors((prev) => ({ ...prev, [fieldId]: field ? checkFieldValue(field, v) ?? undefined : undefined }))
    }
  }

  // Validate a field once the user leaves it (not on every keystroke).
  function blurField(fieldId) {
    const field = template?.fields.find((f) => f.id === fieldId)
    if (field) setErrors((prev) => ({ ...prev, [fieldId]: checkFieldValue(field, values[fieldId]) ?? undefined }))
  }

  function validate() {
    const next = {}
    if (!template) next.template = 'Choose what went wrong.'
    if (isBlank(title)) next.title = 'Give the report a title.'
    for (const f of template?.fields ?? []) {
      const msg = checkFieldValue(f, values[f.id])
      if (msg) next[f.id] = msg
    }
    setErrors(next)
    return next
  }

  function focusFirstError(errs) {
    const first = template?.fields.find((f) => errs[f.id])
    const id = errs.title ? 'report-title' : first ? `report-field-${first.id}` : null
    if (id) requestAnimationFrame(() => document.getElementById(id)?.focus())
  }

  async function handleSubmit() {
    const errs = validate()
    if (Object.keys(errs).length) {
      focusFirstError(errs)
      return
    }
    setSubmitting(true)
    try {
      const fieldValues = {}
      for (const f of template.fields) {
        if (!isBlank(values[f.id])) fieldValues[f.id] = values[f.id]
      }
      const res = await supportApi.submit({
        template_id: template.id,
        title: title.trim(),
        values: fieldValues,
        description: description.trim() || null,
        pending_attachments: pendingAttachments,
      })
      const report = res.data
      toast({
        title: `${report.key} submitted`,
        body: (
          <span>
            It's in {report.project_name}'s triage queue.{' '}
            <Link to={`/issue/${issueSlug({ type: 'bug', issue_number: report.issue_number })}`} className="underline underline-offset-2">
              View report
            </Link>
          </span>
        ),
      })
      reset()
      onSubmitted?.(report)
      onClose()
    } catch (err) {
      const data = err.response?.data
      if (err.response?.status === 409 && data?.code === 'template_inactive') {
        setRetired({ ...template, retired: true })
        supportApi.templates(projectId).then((r) => setTemplates(r.data)).catch(() => {})
      } else if (data?.code === 'invalid_fields' && data.errors) {
        const errs = Object.fromEntries(Object.entries(data.errors).map(([k, v]) => [Number(k), v]))
        setErrors(errs)
        focusFirstError(errs)
      } else {
        toast({ title: 'Failed to submit report', body: data?.detail || 'Try again in a moment.' })
      }
    } finally {
      setSubmitting(false)
    }
  }

  const loading = projects === null || (projectId && templates === null && !retired)
  const noProjects = projects !== null && projects.length === 0

  return (
    <>
      <Dialog open={open} onClose={requestClose} title="New report" size="lg">
        <div className="flex flex-col max-h-[calc(90vh-60px)]">
          <div className="flex-1 overflow-y-auto px-5 scrollbar-thin">
            {noProjects ? (
              <div className="py-12 text-center">
                <Icon name="clipboard-x" size={28} className="mx-auto mb-3 text-muted-foreground" aria-hidden />
                <p className="text-sm font-medium text-foreground">No projects are taking reports yet</p>
                <p className="mt-1 text-[13px] text-muted-foreground">An admin needs to add a support template to a project first.</p>
              </div>
            ) : loading ? (
              <div className="py-16 flex justify-center">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-primary" />
              </div>
            ) : (
              <div className="py-5 space-y-5">
                {retired && (
                  <div role="alert" className="flex items-start gap-2 rounded-[var(--radius)] border border-amber-300 bg-amber-50 px-3 py-2.5 text-[13px] text-amber-800 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                    <Icon name="triangle-alert" size={15} className="mt-0.5 shrink-0" aria-hidden />
                    <span>
                      <strong className="font-semibold">{retired.name}</strong> was just turned off by an admin. Your answers are still here —
                      {templates?.length ? ' choose another option below to send them.' : ' copy them before closing.'}
                    </span>
                  </div>
                )}

                <div className="grid gap-4 sm:grid-cols-[minmax(0,15rem)_minmax(0,1fr)]">
                  <div>
                    <span className="block text-xs font-medium text-muted-foreground mb-1.5">Project</span>
                    <ProjectSwitcher projects={projects} activeProjectId={projectId} onChange={chooseProject} />
                  </div>
                  <TemplateChooser
                    templates={templates ?? []}
                    value={retired ? null : templateId}
                    onChange={chooseTemplate}
                    error={errors.template}
                  />
                </div>

                {template && (
                  <>
                    <div className="border-t border-border" />
                    <FieldShell id="report-title" label="Title" required error={errors.title}>
                      <Input
                        id="report-title"
                        aria-required="true"
                        aria-invalid={errors.title ? true : undefined}
                        value={title}
                        error={!!errors.title}
                        maxLength={512}
                        placeholder="Summarize the problem in a few words…"
                        onChange={(e) => {
                          setTitle(e.target.value)
                          if (errors.title) setErrors((p) => ({ ...p, title: undefined }))
                        }}
                      />
                    </FieldShell>
                    {/* Similar reports (slice 14) appear here, right under the title. */}
                    <div data-slot="similar-reports" />

                    <TemplateFields
                      fields={template.fields}
                      values={values}
                      errors={errors}
                      onChange={setValue}
                      onBlur={blurField}
                      idPrefix="report-field"
                    />

                    <div>
                      <span className="flex items-baseline gap-1 text-xs font-medium text-muted-foreground mb-1.5">
                        Anything else? <span className="font-normal text-muted-foreground/70">(optional)</span>
                      </span>
                      <CommentComposer
                        key={composerKey}
                        initialValue={description}
                        onChange={setDescription}
                        placeholder="What the customer said, what they already tried…"
                        showInternal={false}
                        hideFooter
                      />
                    </div>

                    <AttachmentsSection
                      compact
                      issue={{ attachments }}
                      onAttachmentsChange={setAttachments}
                      onUploadingChange={setUploading}
                      onPendingAttachment={(p) => setPendingAttachments((prev) => [...prev, p])}
                    />
                  </>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-3.5 shrink-0 bg-background rounded-b-xl">
            <p className="text-[12px] text-muted-foreground hidden sm:block">
              {template ? 'Fields marked * are required.' : ' '}
            </p>
            <div className="flex gap-2 ml-auto">
              <Button variant="ghost" onClick={requestClose} disabled={submitting}>Cancel</Button>
              <Button onClick={handleSubmit} disabled={submitting || uploading || noProjects || !template}>
                {submitting ? 'Submitting…' : 'Submit report'}
              </Button>
            </div>
          </div>
        </div>
      </Dialog>

      <Dialog open={confirmDiscard} onClose={() => setConfirmDiscard(false)} title="Discard this report?" size="sm">
        <div className="px-5 py-4 text-sm text-muted-foreground">
          What you've typed will be lost.
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <Button variant="ghost" onClick={() => setConfirmDiscard(false)}>Keep editing</Button>
          <Button variant="destructive" onClick={discard}>Discard</Button>
        </div>
      </Dialog>
    </>
  )
}

/**
 * "What's wrong?" — a template is a kind of problem, so it's chosen as a card,
 * not buried in a dropdown. A single template is shown as a fixed chip.
 */
function TemplateChooser({ templates, value, onChange, error }) {
  if (templates.length === 0) {
    return (
      <div>
        <span className="block text-xs font-medium text-muted-foreground mb-1.5">What's wrong?</span>
        <p className="h-9 flex items-center text-[13px] text-muted-foreground">This project isn't taking reports right now.</p>
      </div>
    )
  }
  if (templates.length === 1) {
    const t = templates[0]
    return (
      <div>
        <span className="block text-xs font-medium text-muted-foreground mb-1.5">What's wrong?</span>
        <div className="flex h-9 items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 text-sm">
          <Icon name="clipboard-list" size={14} className="text-muted-foreground" aria-hidden />
          <span className="font-medium text-foreground truncate">{t.name}</span>
        </div>
      </div>
    )
  }
  return (
    <div className="sm:col-span-2 sm:row-start-2 min-w-0">
      <span id="template-chooser-label" className="flex items-baseline gap-1 text-xs font-medium text-muted-foreground mb-1.5">
        What's wrong? <span className="text-destructive" aria-hidden>*</span>
      </span>
      <div role="radiogroup" aria-labelledby="template-chooser-label" className="grid gap-2 sm:grid-cols-2">
        {templates.map((t) => {
          const selected = t.id === value
          return (
            <button
              key={t.id}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(t.id)}
              className={cn(
                'flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-left transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                selected
                  ? 'border-primary bg-primary/5 ring-1 ring-primary'
                  : error ? 'border-destructive/60 hover:bg-muted/50' : 'border-border hover:bg-muted/50'
              )}
            >
              <span className={cn(
                'mt-0.5 h-4 w-4 shrink-0 rounded-full border flex items-center justify-center',
                selected ? 'border-primary' : 'border-muted-foreground/40'
              )} aria-hidden>
                {selected && <span className="h-2 w-2 rounded-full bg-primary" />}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-medium text-foreground truncate">{t.name}</span>
                <span className="block text-[12px] text-muted-foreground">
                  {t.fields.length} question{t.fields.length === 1 ? '' : 's'}
                </span>
              </span>
            </button>
          )
        })}
      </div>
      {error && (
        <p className="mt-1 flex items-center gap-1 text-[12px] text-destructive" role="alert">
          <Icon name="circle-alert" size={12} aria-hidden />{error}
        </p>
      )}
    </div>
  )
}
