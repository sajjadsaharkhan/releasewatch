import React, { useState, useEffect, useRef } from 'react'
import { Plus, Trash2, Paperclip, X, ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { Select, SelectItem } from '../ui/Select'
import { DatePicker } from '../ui/DatePicker'
import { Switch } from '../ui/Switch'
import { CommentComposer } from './CommentComposer'
import { AttachmentsSection } from './AttachmentsSection'
import { SimilarityRing, similarityBand } from '../triage/SimilarityRing'
import { useSimilarItems } from '../../hooks/useSimilarItems'
import { issueSlug } from '../../lib/issueSlug'
import { BacklogCategoryPicker, ContainerPicker, ProjectSwitcher } from '../common'
import { PRIORITY, PRIORITIES, TASK_DEFAULT_PRIORITY, TECH_DEBT, TYPE, isOpenRelease } from '../../lib/constants'
import { ENVIRONMENT } from './DescriptionSection'
import { issuesApi, projectsApi, releasesApi, labelsApi, teamApi } from '../../lib/api'
import { useBacklogCategories } from '../../hooks/useBacklogCategories'
import { useApp } from '../../hooks/useApp'
import { StatusBadge, TypeIcon } from '../ui'

const INITIAL_FORM = {
  type: 'bug', title: '', projectId: '', releaseId: null, priority: null, environment: null,
  description: '', steps: [''], curlCommand: '', labels: [], assigneeId: '', dueDate: null,
  isReleaseBlocker: false, backlogCategoryId: null, isTechDebt: false,
}

// ───────────────────────── shared form state (mirrors NewIssueModal) ─────────────────────────
function useNewIssueForm({ open, onClose, onCreated }) {
  const { activeProjectId, activeReleaseId, newIssueDraft, setNewIssueDraft } = useApp()
  const [form, setForm] = useState(INITIAL_FORM)
  const [composerKey, setComposerKey] = useState(0)
  const [loading, setLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [errors, setErrors] = useState({})
  const [attachments, setAttachments] = useState([])
  const [pendingAttachments, setPendingAttachments] = useState([])
  const [projects, setProjects] = useState([])
  const [allReleases, setAllReleases] = useState([])
  const [labels, setLabels] = useState([])
  const [teamUsers, setTeamUsers] = useState([])
  const [assignableUsers, setAssignableUsers] = useState([])
  const [dataLoading, setDataLoading] = useState(false)

  const isTask = form.type === 'task'
  const priority = form.priority ?? (isTask ? TASK_DEFAULT_PRIORITY : null)
  const inRelease = form.releaseId != null && allReleases.some((r) => r.id === form.releaseId)
  const { categories } = useBacklogCategories(form.projectId || null)

  useEffect(() => {
    if (!open) return
    const seedProjectId = activeProjectId
    const seedReleaseId = activeReleaseId
    ;(async () => {
      setDataLoading(true)
      try {
        const [p, r, l, t, a] = await Promise.all([
          projectsApi.list(), releasesApi.list(), labelsApi.list(), teamApi.list(), teamApi.listAssignable(),
        ])
        setProjects(p.data || [])
        setAllReleases(r.data?.releases || [])
        setLabels(l.data || [])
        setTeamUsers(t.data || [])
        setAssignableUsers(a.data || [])
        const projectId = seedProjectId || p.data?.[0]?.id || ''
        const seed = (r.data?.releases || []).find(
          (x) => x.id === seedReleaseId && x.projectId === projectId && isOpenRelease(x),
        )
        setForm((f) => ({ ...f, projectId, releaseId: seed?.id ?? null }))
      } catch (err) {
        console.error('Failed to load data:', err)
      } finally {
        setDataLoading(false)
      }
    })()
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open || !newIssueDraft) return
    setForm((f) => ({ ...f, ...newIssueDraft }))
    setComposerKey((k) => k + 1)
    setNewIssueDraft(null)
  }, [open, newIssueDraft]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) {
      setAttachments([]); setPendingAttachments([]); setForm(INITIAL_FORM); setErrors({})
    }
  }, [open])

  const set = (key, val) => {
    setForm((f) => ({ ...f, [key]: val }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }
  const setType = (type) => {
    setForm((f) => ({
      ...f,
      type,
      isReleaseBlocker: type === 'task' ? false : f.isReleaseBlocker,
      releaseId: type === 'task'
        ? null
        : (f.releaseId ?? (activeReleaseId && allReleases.some((r) => r.id === activeReleaseId && r.projectId === f.projectId && isOpenRelease(r)) ? activeReleaseId : null)),
    }))
    setErrors({})
  }
  const setProject = (id) =>
    setForm((f) => ({ ...f, projectId: id, releaseId: null, isReleaseBlocker: false, backlogCategoryId: null }))
  const setContainer = (id) => {
    const still = id != null && allReleases.some((r) => r.id === id)
    setForm((f) => ({ ...f, releaseId: id, isReleaseBlocker: still ? f.isReleaseBlocker : false }))
  }
  const addStep = () => setForm((f) => ({ ...f, steps: [...f.steps, ''] }))
  const updateStep = (i, v) => setForm((f) => { const s = [...f.steps]; s[i] = v; return { ...f, steps: s } })
  const removeStep = (i) => setForm((f) => ({ ...f, steps: f.steps.filter((_, x) => x !== i) }))
  const toggleLabel = (name) =>
    setForm((f) => ({ ...f, labels: f.labels.includes(name) ? f.labels.filter((l) => l !== name) : [...f.labels, name] }))

  async function submit() {
    if (!form.title.trim()) { setErrors({ title: 'Give it a title first' }); return false }
    setLoading(true)
    try {
      const shared = {
        type: form.type, title: form.title, project_id: form.projectId,
        description: form.description || null, labels: form.labels,
        assignee_id: form.assigneeId || null,
        due_date: form.dueDate ? form.dueDate.toISOString().slice(0, 10) : null,
        priority, pending_attachments: pendingAttachments,
      }
      const payload = isTask
        ? { ...shared, release_id: form.releaseId, backlog_category_id: form.backlogCategoryId, is_tech_debt: form.isTechDebt }
        : {
          ...shared,
          release_id: form.releaseId,
          backlog_category_id: form.releaseId == null ? form.backlogCategoryId : null,
          environment_name: form.environment || null,
          curl_command: form.curlCommand || null,
          is_release_blocker: inRelease && form.isReleaseBlocker,
          reproduction_steps: form.steps
            .map((s, i) => (s.trim() ? { step_order: i + 1, description: s, expected_result: null, actual_result: null } : null))
            .filter(Boolean),
        }
      const res = await issuesApi.create(payload)
      onCreated?.(res.data)
      onClose?.()
      return true
    } catch (err) {
      const body = err.response?.data
      setErrors((e) => ({ ...e, submit: body?.detail || err.normalizedMessage || 'Failed to save issue' }))
      return false
    } finally {
      setLoading(false)
    }
  }

  return {
    form, set, setType, setProject, setContainer, addStep, updateStep, removeStep, toggleLabel,
    errors, loading, dataLoading, isUploading, setIsUploading, isTask, priority, inRelease, categories,
    projects, labels, teamUsers, assignableUsers, composerKey, submit,
    attachments, setAttachments,
    addPending: (p) => setPendingAttachments((prev) => [...prev, p]),
    pendingCount: pendingAttachments.length,
    stepsCount: form.steps.filter((s) => s.trim()).length,
  }
}

// "Possibly the same" as horizontal candidate cards — the triage DuplicateCandidateCard
// shape (similarity ring · type/key/status · band · title) in one row, with Open /
// Not the same instead of Merge (merging happens in triage). Renders nothing while
// Jev is off or nothing matched (BR-S02/S03).
function CandidateRow({ item, onDismiss }) {
  const { issue, confidence } = item
  const band = similarityBand(confidence)
  return (
    <li
      data-testid="similar-candidate"
      className={cn('flex items-center gap-3 rounded-lg border bg-card px-3 py-2', confidence >= 0.9 ? 'border-amber-300 dark:border-amber-800/70' : 'border-border')}
    >
      <SimilarityRing confidence={confidence} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <TypeIcon type={issue.type} aria-hidden />
          <span className="font-mono">{issue.key}</span>
          <StatusBadge status={issue.status} />
          <span className={cn('font-medium', band.high ? 'text-amber-700 dark:text-amber-300' : '')}>· {band.label}</span>
        </div>
        <a
          href={`/issue/${issueSlug(issue)}`} target="_blank" rel="noreferrer"
          className="mt-0.5 block truncate text-[13px] text-foreground underline-offset-2 hover:underline"
        >
          {issue.title}
        </a>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Button size="sm" variant="outline" onClick={() => window.open(`/issue/${issueSlug(issue)}`, '_blank', 'noopener')}>
          <Icon name="external-link" size={12} aria-hidden="true" /> Open
        </Button>
        <Button size="sm" variant="ghost" className="text-muted-foreground" onClick={() => onDismiss(issue.id)}>Not the same</Button>
      </div>
    </li>
  )
}

function Similar({ s }) {
  const { features } = useApp()
  const similar = useSimilarItems({
    enabled: Boolean(features?.jev_enabled), context: 'tech',
    projectId: s.form.projectId || null, title: s.form.title, description: s.form.description,
  })
  const [dismissed, setDismissed] = useState([])
  const [open, setOpen] = useState(false)
  const items = similar?.filter((x) => !dismissed.includes(x.issue.id))
  if (!items?.length) return null
  const top = items.reduce((m, x) => (x.confidence > m.confidence ? x : m), items[0])
  const topBand = similarityBand(top.confidence)
  return (
    <section aria-label="Possibly the same" className={cn('rounded-lg border bg-muted/20', topBand.high ? 'border-amber-300 dark:border-amber-800/70' : 'border-border')}>
      <button
        type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Icon name="copy" size={14} className="shrink-0 text-amber-600 dark:text-amber-400" aria-hidden />
        <span className="text-sm font-medium">Possibly the same</span>
        <span className="rounded-full bg-muted px-1.5 text-[11px] font-medium tabular-nums">{items.length}</span>
        <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
          · top match <span className={cn('font-semibold tabular-nums', topBand.high ? 'text-amber-700 dark:text-amber-300' : 'text-foreground')}>{Math.round(top.confidence * 100)}%</span>
          {' '}<span className="font-mono">{top.issue.key}</span>
        </span>
        {open ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
      </button>
      {open && (
        <div className="border-t border-border/60 p-2">
          <ul className="space-y-1.5">
            {items.map((it) => <CandidateRow key={it.issue.id} item={it} onDismiss={(id) => setDismissed((d) => [...d, id])} />)}
          </ul>
          <p className="mt-2 px-1 text-[11px] text-muted-foreground/70">Check before filing — merging happens in triage.</p>
        </div>
      )}
    </section>
  )
}

// ───────────────────────── shell (same look as Dialog, custom header) ─────────────────────────
function Shell({ open, onClose, size, ariaLabel, header, footer, children, onSubmitShortcut }) {
  useEffect(() => {
    if (!open) return
    const h = (e) => {
      if (e.key === 'Escape') onClose?.()
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); onSubmitShortcut?.() }
    }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [open, onClose, onSubmitShortcut])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 !m-0" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      <div className="absolute inset-0 flex items-center justify-center p-4" onClick={(e) => e.stopPropagation()}>
        <div role="dialog" aria-modal="true" aria-label={ariaLabel} className={cn('dialog-enter relative flex max-h-[90vh] w-full flex-col rounded-xl border border-border bg-card shadow-2xl', size)}>
          {header}
          <div className="flex-1 overflow-y-auto scrollbar-thin">{children}</div>
          {footer}
        </div>
      </div>
    </div>
  )
}

function CloseButton({ onClose }) {
  return (
    <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
      <X className="h-4 w-4" />
    </button>
  )
}

function Footer({ s, onClose, hint = true, extra }) {
  return (
    <div className="flex shrink-0 items-center justify-between gap-3 border-t border-border bg-card px-5 py-3">
      <div className="min-w-0 text-xs">
        {s.errors.submit
          ? <p className="text-destructive">{s.errors.submit}</p>
          : hint && <span className="text-muted-foreground"><kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-sans text-[11px]">⌘ Enter</kbd> to create</span>}
      </div>
      <div className="flex items-center gap-2">
        {extra}
        <Button variant="ghost" onClick={onClose} disabled={s.loading}>Cancel</Button>
        <Button onClick={s.submit} loading={s.loading} disabled={s.isUploading || s.dataLoading}>
          {s.loading ? 'Creating…' : s.isTask ? 'Create task' : 'Create bug'}
        </Button>
      </div>
    </div>
  )
}

function Skeleton() {
  return (
    <div className="space-y-3 p-5" aria-busy="true">
      <div className="h-8 w-2/3 animate-pulse rounded bg-muted" />
      <div className="h-24 animate-pulse rounded bg-muted" />
      <div className="h-8 animate-pulse rounded bg-muted" />
    </div>
  )
}

// ───────────────────────── shared field pieces ─────────────────────────
const Label = ({ children, hint, className }) => (
  <label className={cn('mb-1.5 block text-xs font-medium text-muted-foreground', className)}>
    {children} {hint && <span className="font-normal text-muted-foreground/70">{hint}</span>}
  </label>
)

function TypeTabs({ s, size = 'sm' }) {
  return (
    <div role="tablist" aria-label="Type" className="inline-flex items-center gap-0.5 rounded-lg bg-muted p-0.5">
      {['bug', 'task'].map((t) => (
        <button
          key={t} role="tab" aria-selected={s.form.type === t} onClick={() => s.setType(t)}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            s.form.type === t ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Icon name={TYPE[t].icon} size={14} /> {TYPE[t].label}
        </button>
      ))}
    </div>
  )
}

function Chip({ selected, onClick, children, ...p }) {
  return (
    <button
      type="button" onClick={onClick} aria-pressed={selected} {...p}
      className={cn(
        'flex h-8 items-center gap-1.5 whitespace-nowrap rounded-md border px-2.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        selected ? 'border-foreground bg-foreground text-background dark:border-background dark:bg-background dark:text-foreground' : 'border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}

function PriorityRow({ s }) {
  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label="Priority">
      {!s.isTask && <Chip selected={s.priority == null} onClick={() => s.set('priority', null)}>Unrated</Chip>}
      {PRIORITIES.map((p) => (
        <Chip key={p} selected={s.priority === p} onClick={() => s.set('priority', p)}>
          <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', PRIORITY[p].dot)} />{PRIORITY[p].label}
        </Chip>
      ))}
    </div>
  )
}

function EnvRow({ s }) {
  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label="Environment">
      {Object.values(ENVIRONMENT).map((env) => (
        <Chip key={env.value} selected={s.form.environment === env.value} onClick={() => s.set('environment', s.form.environment === env.value ? null : env.value)}>
          {env.label}
        </Chip>
      ))}
    </div>
  )
}

function LabelRow({ s }) {
  if (!s.labels.length) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {s.labels.map((l) => {
        const on = s.form.labels.includes(l.name)
        return (
          <button
            key={l.id} type="button" aria-pressed={on} onClick={() => s.toggleLabel(l.name)}
            className={cn('inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors', on ? 'border-transparent text-white' : 'border-border text-muted-foreground hover:text-foreground')}
            style={on ? { backgroundColor: l.color } : {}}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: on ? 'white' : l.color }} />{l.name}
          </button>
        )
      })}
    </div>
  )
}

function TitleInput({ s, big, autoFocus = true }) {
  const ref = useRef(null)
  useEffect(() => { if (autoFocus && !s.dataLoading) ref.current?.focus() }, [s.dataLoading]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div>
      <input
        ref={ref} value={s.form.title} onChange={(e) => s.set('title', e.target.value)}
        placeholder={s.isTask ? 'What needs doing?' : 'What went wrong?'}
        aria-label="Title" aria-invalid={!!s.errors.title}
        className={cn(
          'w-full bg-transparent placeholder:text-muted-foreground/60 focus:outline-none',
          big ? 'text-lg font-semibold' : 'h-9 rounded-md border border-input px-3 text-sm focus-visible:ring-1 focus-visible:ring-ring',
          s.errors.title && 'placeholder:text-destructive/70',
        )}
      />
      {s.errors.title && <p role="alert" className="mt-1 text-xs text-destructive">{s.errors.title}</p>}
    </div>
  )
}

function Description({ s, label = true }) {
  return (
    <div>
      {label && <Label>Description</Label>}
      <CommentComposer
        key={s.composerKey} initialValue={s.form.description} onChange={(v) => s.set('description', v)}
        placeholder={s.isTask ? 'Describe the task…' : 'What happened, and what did you expect instead?'}
        showInternal={false} hideFooter users={s.teamUsers}
      />
    </div>
  )
}

function Steps({ s }) {
  return (
    <div>
      <Label>Steps to reproduce</Label>
      <div className="space-y-2">
        {s.form.steps.map((step, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-5 shrink-0 text-right text-xs tabular-nums text-muted-foreground">{i + 1}.</span>
            <input
              value={step} onChange={(e) => s.updateStep(i, e.target.value)} placeholder={`Step ${i + 1}…`}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.metaKey && !e.ctrlKey && step.trim()) { e.preventDefault(); if (i === s.form.steps.length - 1) s.addStep() } }}
              className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            {s.form.steps.length > 1 && (
              <Button variant="ghost" size="icon-sm" onClick={() => s.removeStep(i)} aria-label={`Remove step ${i + 1}`}>
                <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
              </Button>
            )}
          </div>
        ))}
        <Button variant="ghost" size="sm" onClick={s.addStep}><Plus className="h-3.5 w-3.5" /> Add step</Button>
      </div>
    </div>
  )
}

function Curl({ s }) {
  return (
    <div>
      <Label hint="(optional)">cURL command</Label>
      <textarea
        value={s.form.curlCommand} onChange={(e) => s.set('curlCommand', e.target.value)} rows={3} placeholder="curl -X POST …"
        className="flex w-full resize-none rounded-[var(--radius)] border border-input bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      />
    </div>
  )
}

function Files({ s }) {
  return (
    <div>
      <Label className="flex items-center gap-1.5"><Paperclip className="h-3.5 w-3.5" /> Attachments</Label>
      <AttachmentsSection
        issue={{ attachments: s.attachments }} onAttachmentsChange={s.setAttachments}
        disabled={s.loading || s.dataLoading} onUploadingChange={s.setIsUploading} onPendingAttachment={s.addPending}
      />
    </div>
  )
}

function TaskDebt({ s }) {
  if (!s.isTask) return null
  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-3">
      <div className="flex items-start gap-3">
        <Switch checked={s.form.isTechDebt} onCheckedChange={(v) => s.set('isTechDebt', v)} aria-labelledby="np-debt" className="mt-0.5" />
        <div className="min-w-0">
          <span id="np-debt" className="flex items-center gap-1.5 text-sm font-medium">
            <Icon name={TECH_DEBT.icon} size={14} className={TECH_DEBT.iconClass} aria-hidden="true" /> Technical debt
          </span>
          <p className="mt-0.5 text-[11.5px] text-muted-foreground">Listed under Technical debt, not the backlog. Put components, risk and approach in the description.</p>
        </div>
      </div>
    </div>
  )
}

// Shown only while the item is going to the backlog (releaseId null) and the project
// has more than its Default category. Empty = the project's Default.
function BacklogCategory({ s }) {
  if (s.form.releaseId != null || s.categories.length === 0) return null
  return (
    <div>
      <Label>Backlog category</Label>
      <BacklogCategoryPicker categories={s.categories} value={s.form.backlogCategoryId} onChange={(v) => s.set('backlogCategoryId', v)} />
    </div>
  )
}

const Assignee = ({ s }) => (
  <Select value={s.form.assigneeId} onChange={(id) => s.set('assigneeId', id)} placeholder="Unassigned">
    {s.assignableUsers.map((u) => <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>)}
  </Select>
)
const Due = ({ s }) => <DatePicker value={s.form.dueDate} onChange={(d) => s.set('dueDate', d)} placeholder="No due date" />
const Blocker = ({ s }) => !s.isTask && s.inRelease && (
  <label className="flex cursor-pointer items-center gap-2">
    <Switch checked={s.form.isReleaseBlocker} onCheckedChange={(v) => s.set('isReleaseBlocker', v)} />
    <span className="text-sm font-medium">Release blocker</span>
  </label>
)

// Title and description first, then one property box; the rest sits in a drawer
// that starts open. Quick capture (chosen from a prototype, 2026-10-02).
export function NewIssueModal({ open, onClose, onCreated }) {
  const s = useNewIssueForm({ open, onClose, onCreated })
  const [more, setMore] = useState(true)
  const extras = s.stepsCount + s.pendingCount + (s.form.curlCommand ? 1 : 0)
  return (
    <Shell
      open={open} onClose={onClose} size="max-w-2xl" ariaLabel={s.isTask ? 'New task' : 'New bug'} onSubmitShortcut={s.submit}
      header={
        <div className="relative flex shrink-0 items-center justify-between border-b border-border px-5 py-3">
          <div className="flex items-center gap-3"><TypeTabs s={s} /><span className="text-xs text-muted-foreground">New {s.isTask ? 'task' : 'bug'}</span></div>
          <CloseButton onClose={onClose} />
        </div>
      }
      footer={<Footer s={s} onClose={onClose} />}
    >
      {s.dataLoading ? <Skeleton /> : (
        <div className="space-y-4 px-5 py-4">
          <TitleInput s={s} big />
          <Description s={s} label={false} />
          <Similar s={s} />

          <div className="relative space-y-3 rounded-lg border border-border bg-muted/20 p-3">
            <div className="grid gap-2 sm:grid-cols-2">
              <div><Label>Project</Label><ProjectSwitcher projects={s.projects} activeProjectId={s.form.projectId} onChange={s.setProject} /></div>
              <div><Label>Place in</Label><ContainerPicker colorize projectId={s.form.projectId} value={s.form.releaseId} onChange={s.setContainer} /></div>
            </div>
            <BacklogCategory s={s} />
            <div><Label hint={!s.isTask ? '(optional until triage)' : undefined}>Priority</Label><PriorityRow s={s} /></div>
            <div className="grid gap-2 sm:grid-cols-[1fr_180px]">
              <div><Label>Assignee</Label><Assignee s={s} /></div>
              <div><Label>Due date</Label><Due s={s} /></div>
            </div>
          </div>

          <TaskDebt s={s} />

          <div className="relative">
            <button
              type="button" onClick={() => setMore((m) => !m)} aria-expanded={more}
              className="flex w-full items-center gap-1.5 rounded-md py-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {more ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              {s.isTask ? 'Labels & files' : 'Environment, reproduction, labels & files'}
              {(extras + s.form.labels.length) > 0 && <span className="rounded-full bg-muted px-1.5 text-[11px] tabular-nums">{extras + s.form.labels.length}</span>}
            </button>
            {more && (
              <div className="mt-3 space-y-4">
                {!s.isTask && (<>
                  <div><Label>Environment</Label><EnvRow s={s} /></div>
                  <Blocker s={s} />
                  <Steps s={s} />
                  <Curl s={s} />
                </>)}
                {s.labels.length > 0 && <div><Label>Labels</Label><LabelRow s={s} /></div>}
                <Files s={s} />
              </div>
            )}
          </div>
        </div>
      )}
    </Shell>
  )
}

