import React, { useState } from 'react'
import { Plus, Trash2, Paperclip } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { MarkdownComposer } from './MarkdownComposer'
import { AttachmentsSection } from './AttachmentsSection'
import { ProjectSwitcher, ReleaseSwitcher } from '../common'
import { MOCK_PROJECTS, MOCK_RELEASES, MOCK_LABELS, SEVERITY } from '../../data/mockData'
import { issuesApi } from '../../lib/api'

export function NewIssueModal({ open, onClose, onCreated }) {
  const [form, setForm] = useState({
    title: '',
    projectId: MOCK_PROJECTS[0]?.id ?? '',
    releaseId: '',
    severity: 'major',
    description: '',
    steps: [''],
    curlCommand: '',
    labels: [],
    assignee: '',
  })
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})
  const [attachments, setAttachments] = useState([])

  const availableReleases = MOCK_RELEASES.filter((r) => r.projectId === form.projectId)

  // Create a wrapper issue object for AttachmentsSection
  const issueWrapper = { attachments }

  function set(key, val) {
    setForm((f) => ({ ...f, [key]: val }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  function addStep() {
    setForm((f) => ({ ...f, steps: [...f.steps, ''] }))
  }

  function updateStep(idx, val) {
    setForm((f) => {
      const steps = [...f.steps]
      steps[idx] = val
      return { ...f, steps }
    })
  }

  function removeStep(idx) {
    setForm((f) => ({ ...f, steps: f.steps.filter((_, i) => i !== idx) }))
  }

  function toggleLabel(id) {
    setForm((f) => ({
      ...f,
      labels: f.labels.includes(id) ? f.labels.filter((l) => l !== id) : [...f.labels, id],
    }))
  }

  function validate() {
    const errs = {}
    if (!form.title.trim()) errs.title = 'Title is required'
    return errs
  }

  async function handleSubmit() {
    const errs = validate()
    if (Object.keys(errs).length > 0) { setErrors(errs); return }
    setLoading(true)
    try {
      // In prod: await issuesApi.create({ ...form, attachments })
      await new Promise((r) => setTimeout(r, 800))
      onCreated?.({ ...form, id: `BUG-${Math.floor(Math.random() * 900) + 100}`, createdAt: new Date().toISOString() })
      onClose?.()
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="New Issue" size="xl">
      <div className="flex flex-col max-h-[calc(90vh-60px)]">
        {/* Scrollable content area */}
        <div className="flex-1 overflow-y-auto px-5 scrollbar-thin">
          <div className="py-5 space-y-5">
            {/* Title */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                Title <span className="text-destructive">*</span>
              </label>
              <Input
                value={form.title}
                onChange={(e) => set('title', e.target.value)}
                placeholder="Short, descriptive title…"
                error={!!errors.title}
              />
              {errors.title && <p className="mt-1 text-xs text-destructive">{errors.title}</p>}
            </div>

            {/* Project + Release + Severity in one row */}
            <div className="grid grid-cols-[200px_180px_1fr] gap-3">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Project</label>
                <ProjectSwitcher
                  projects={MOCK_PROJECTS}
                  activeProjectId={form.projectId}
                  onChange={(id) => set('projectId', id)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Release</label>
                <ReleaseSwitcher
                  releases={availableReleases}
                  activeReleaseId={form.releaseId}
                  onChange={(id) => set('releaseId', id)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Severity</label>
                <div className="overflow-x-auto overflow-y-hidden -mx-1 px-1">
                  <div className="flex gap-1 min-w-max pb-1">
                    {Object.keys(SEVERITY).map(s => (
                      <button
                        key={s}
                        onClick={() => set('severity', s)}
                        className={cn(
                          'h-8 px-2 rounded-md text-[11px] font-medium border transition-colors',
                          'flex items-center gap-1 whitespace-nowrap',
                          form.severity === s
                            ? 'bg-foreground text-background border-foreground dark:bg-background dark:text-foreground dark:border-background'
                            : 'bg-background text-muted-foreground border-border hover:bg-muted dark:bg-background dark:text-muted-foreground dark:border-border dark:hover:bg-muted'
                        )}
                      >
                        <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', SEVERITY[s].dot)} />
                        {SEVERITY[s].label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Description</label>
              <MarkdownComposer
                onSubmit={(body) => set('description', body)}
                placeholder="Describe the issue, expected vs actual behavior…"
                showMentions={false}
                showInternal={false}
                mode="create"
              />
            </div>

            {/* Steps to reproduce */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-2">
                Steps to Reproduce
              </label>
              <div className="space-y-2">
                {form.steps.map((step, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <span className="w-5 text-xs text-muted-foreground text-right shrink-0">{idx + 1}.</span>
                    <Input
                      value={step}
                      onChange={(e) => updateStep(idx, e.target.value)}
                      placeholder={`Step ${idx + 1}…`}
                    />
                    {form.steps.length > 1 && (
                      <Button variant="ghost" size="icon-sm" onClick={() => removeStep(idx)}>
                        <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                      </Button>
                    )}
                  </div>
                ))}
                <Button variant="ghost" size="sm" onClick={addStep}>
                  <Plus className="h-3.5 w-3.5" /> Add step
                </Button>
              </div>
            </div>

            {/* cURL */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">cURL command (optional)</label>
              <textarea
                value={form.curlCommand}
                onChange={(e) => set('curlCommand', e.target.value)}
                rows={3}
                placeholder="curl -X POST …"
                className="flex w-full rounded-[var(--radius)] border border-input bg-zinc-950 text-zinc-100 px-3 py-2 font-mono text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
              />
            </div>

            {/* Labels */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-2">Labels</label>
              <div className="flex flex-wrap gap-2">
                {MOCK_LABELS.map((l) => {
                  const selected = form.labels.includes(l.id)
                  return (
                    <button
                      key={l.id}
                      onClick={() => toggleLabel(l.id)}
                      className={cn(
                        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
                        selected
                          ? 'border-transparent text-white'
                          : 'border-border text-muted-foreground hover:text-foreground'
                      )}
                      style={selected ? { backgroundColor: l.color } : {}}
                    >
                      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: selected ? 'white' : l.color }} />
                      {l.name}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Attachments */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Paperclip className="h-4 w-4 text-muted-foreground" />
                <label className="text-xs font-medium text-muted-foreground">Attachments</label>
              </div>
              <AttachmentsSection
                issue={issueWrapper}
                onAttachmentsChange={(atts) => setAttachments(atts)}
              />
            </div>
          </div>
        </div>

        {/* Fixed footer */}
        <div className="flex justify-end gap-3 border-t border-border px-5 py-4 shrink-0 bg-background">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} loading={loading}>Create Issue</Button>
        </div>
      </div>
    </Dialog>
  )
}
