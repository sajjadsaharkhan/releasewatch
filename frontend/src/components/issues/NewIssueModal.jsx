import React, { useState, useRef } from 'react'
import { Plus, Trash2, Upload } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Segmented } from '../ui/Segmented'
import { Dropdown, DropdownItem } from '../ui/Dropdown'
import { MarkdownComposer } from './MarkdownComposer'
import { MOCK_PROJECTS, MOCK_RELEASES, MOCK_LABELS, MOCK_TEAM } from '../../data/mockData'
import { issuesApi } from '../../lib/api'

const SEVERITY_OPTIONS = [
  { value: 'blocker', label: 'Blocker' },
  { value: 'critical', label: 'Critical' },
  { value: 'major', label: 'Major' },
  { value: 'minor', label: 'Minor' },
  { value: 'enhancement', label: 'Enhancement' },
]

export function NewIssueModal({ open, onClose, onCreated }) {
  const [form, setForm] = useState({
    title: '',
    projectId: MOCK_PROJECTS[0]?.id ?? '',
    releaseId: '',
    severity: 'major',
    description: '',
    steps: [''],
    environment: { browser: '', os: '', build: '', staging: '' },
    curlCommand: '',
    labels: [],
    assignee: '',
  })
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})
  const [dragOver, setDragOver] = useState(false)
  const [attachments, setAttachments] = useState([])
  const fileRef = useRef(null)

  const selectedProject = MOCK_PROJECTS.find((p) => p.id === form.projectId)
  const availableReleases = MOCK_RELEASES.filter((r) => r.projectId === form.projectId)

  function set(key, val) {
    setForm((f) => ({ ...f, [key]: val }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  function setEnv(key, val) {
    setForm((f) => ({ ...f, environment: { ...f.environment, [key]: val } }))
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

  function handleFiles(files) {
    const newAtts = Array.from(files).map((file) => ({
      id: `att-${Date.now()}-${Math.random()}`,
      name: file.name,
      type: file.type.startsWith('image') ? 'image' : file.type.startsWith('video') ? 'video' : 'log',
      url: URL.createObjectURL(file),
      size: file.size,
    }))
    setAttachments((a) => [...a, ...newAtts])
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
      <div className="p-5 space-y-5">
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

        {/* Project + Release */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Project</label>
            <Dropdown
              trigger={
                <Button variant="outline" size="sm" className="w-full justify-between">
                  {selectedProject?.name ?? 'Select project'}
                </Button>
              }
            >
              {MOCK_PROJECTS.map((p) => (
                <DropdownItem key={p.id} onClick={() => set('projectId', p.id)}>{p.name}</DropdownItem>
              ))}
            </Dropdown>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Release</label>
            <Dropdown
              trigger={
                <Button variant="outline" size="sm" className="w-full justify-between">
                  {MOCK_RELEASES.find((r) => r.id === form.releaseId)?.version ?? 'Select release'}
                </Button>
              }
            >
              <DropdownItem onClick={() => set('releaseId', '')}>None</DropdownItem>
              {availableReleases.map((r) => (
                <DropdownItem key={r.id} onClick={() => set('releaseId', r.id)}>{r.version}</DropdownItem>
              ))}
            </Dropdown>
          </div>
        </div>

        {/* Severity */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Severity</label>
          <Segmented
            value={form.severity}
            onValueChange={(v) => set('severity', v)}
            options={SEVERITY_OPTIONS}
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Description</label>
          <MarkdownComposer
            onSubmit={(body) => set('description', body)}
            placeholder="Describe the issue, expected vs actual behavior…"
            showMentions={false}
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

        {/* Environment */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-2">Environment</label>
          <div className="grid grid-cols-2 gap-3">
            {[
              ['browser', 'Browser & version'],
              ['os', 'OS'],
              ['build', 'Build hash'],
              ['staging', 'Staging URL'],
            ].map(([key, label]) => (
              <div key={key}>
                <p className="text-xs text-muted-foreground mb-1">{label}</p>
                <Input
                  value={form.environment[key]}
                  onChange={(e) => setEnv(key, e.target.value)}
                  placeholder={label}
                />
              </div>
            ))}
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
          <label className="block text-xs font-medium text-muted-foreground mb-2">Attachments</label>
          <div
            className={cn(
              'rounded-lg border-2 border-dashed p-6 text-center cursor-pointer transition-colors',
              dragOver ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
            )}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
            onClick={() => fileRef.current?.click()}
          >
            <Upload className="mx-auto h-6 w-6 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">Drag files here or click to browse</p>
            <p className="text-xs text-muted-foreground/60 mt-1">Images, videos, logs accepted</p>
            <input ref={fileRef} type="file" multiple className="hidden" onChange={(e) => handleFiles(e.target.files)} />
          </div>
          {attachments.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {attachments.map((a) => (
                <div key={a.id} className="flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs">
                  {a.name}
                  <button onClick={() => setAttachments((prev) => prev.filter((x) => x.id !== a.id))} className="text-muted-foreground hover:text-destructive">
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 border-t border-border pt-4">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} loading={loading}>Create Issue</Button>
        </div>
      </div>
    </Dialog>
  )
}
