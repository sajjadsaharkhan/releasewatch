import React, { useState, useEffect } from 'react'
import { Plus, Trash2, Paperclip } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Icon } from '../ui/Icon'
import { Segmented } from '../ui/Segmented'
import { Select, SelectItem } from '../ui/Select'
import { DatePicker } from '../ui/DatePicker'
import { Switch } from '../ui/Switch'
import { CommentComposer } from './CommentComposer'
import { AttachmentsSection } from './AttachmentsSection'
import { ProjectSwitcher, ReleaseSwitcher } from '../common'
import { PRIORITY, PRIORITIES, TASK_DEFAULT_PRIORITY, TYPE } from '../../lib/constants'
import { ENVIRONMENT } from './DescriptionSection'
import { issuesApi, projectsApi, releasesApi, labelsApi, teamApi } from '../../lib/api'
import { useApp } from '../../hooks/useApp'

const INITIAL_FORM = {
  type: 'bug',
  title: '',
  projectId: '',
  releaseId: '',
  priority: null,
  environment: null,
  description: '',
  steps: [''],
  curlCommand: '',
  labels: [],
  assigneeId: '',
  dueDate: null,
  isReleaseBlocker: false,
}

export function NewIssueModal({ open, onClose, onCreated }) {
  const { activeProjectId, activeReleaseId } = useApp()
  const [form, setForm] = useState(INITIAL_FORM)
  // A bug may stay unrated until triage; a task starts at medium (BR-16).
  const priority = form.priority ?? (form.type === 'task' ? TASK_DEFAULT_PRIORITY : null)
  const [loading, setLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [errors, setErrors] = useState({})
  const [attachments, setAttachments] = useState([])
  const [pendingAttachments, setPendingAttachments] = useState([])
  const [projects, setProjects] = useState([])
  const [allReleases, setAllReleases] = useState([])
  const [labels, setLabels] = useState([])
  const [teamUsers, setTeamUsers] = useState([])
  const [dataLoading, setDataLoading] = useState(false)

  // Fetch projects, releases, and labels when modal opens.
  // Capture context values as closure vars so changes to the global switcher
  // while the modal is open don't overwrite the user's in-modal selection.
  useEffect(() => {
    if (!open) return
    const seedProjectId = activeProjectId
    const seedReleaseId = activeReleaseId

    async function fetchData() {
      setDataLoading(true)
      try {
        const [projectsRes, releasesRes, labelsRes, teamRes] = await Promise.all([
          projectsApi.list(),
          releasesApi.list(),
          labelsApi.list(),
          teamApi.list(),
        ])
        setProjects(projectsRes.data || [])
        setAllReleases(releasesRes.data?.releases || [])
        setLabels(labelsRes.data || [])
        setTeamUsers(teamRes.data || [])

        setForm((f) => ({
          ...f,
          projectId: seedProjectId || projectsRes.data?.[0]?.id || '',
          releaseId: seedReleaseId || '',
        }))
      } catch (err) {
        console.error('Failed to load data:', err)
      } finally {
        setDataLoading(false)
      }
    }
    fetchData()
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  // Reset form when modal closes
  useEffect(() => {
    if (!open) {
      setAttachments([])
      setPendingAttachments([])
      setForm(INITIAL_FORM)
      setErrors({})
    }
  }, [open])

  const selectedProject = projects.find((p) => p.id === form.projectId)
  const releasesAllowed = selectedProject?.kind === 'product'

  // Filter releases for selected project and only active/blocked status
  const availableReleases = allReleases.filter(
    (r) => r.projectId === form.projectId && (r.status === 'active' || r.status === 'blocked')
  )

  // Create a wrapper issue object for AttachmentsSection display
  const issueWrapper = { attachments }

  function handlePendingAttachment(pending) {
    setPendingAttachments(prev => [...prev, pending])
  }

  function set(key, val) {
    setForm((f) => ({ ...f, [key]: val }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  function setType(type) {
    setForm((f) => ({ ...f, type }))
    setErrors({})
  }

  function setProject(id) {
    const project = projects.find((p) => p.id === id)
    const firstRelease = project?.kind === 'product'
      ? allReleases.find((r) => r.projectId === id && (r.status === 'active' || r.status === 'blocked'))
      : null
    setForm((f) => ({ ...f, projectId: id, releaseId: firstRelease?.id || '' }))
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

  function toggleLabel(labelName) {
    setForm((f) => ({
      ...f,
      labels: f.labels.includes(labelName) ? f.labels.filter((l) => l !== labelName) : [...f.labels, labelName],
    }))
  }

  function validate() {
    const errs = {}
    if (!form.title.trim()) errs.title = 'Title is required'
    return errs
  }

  async function handleSubmit() {
    const errs = validate()
    if (Object.keys(errs).length > 0) {
      setErrors(errs)
      return
    }

    setLoading(true)
    try {
      const shared = {
        type: form.type,
        title: form.title,
        project_id: form.projectId,
        description: form.description || null,
        labels: form.labels,
        assignee_id: form.assigneeId || null,
        due_date: form.dueDate ? form.dueDate.toISOString().slice(0, 10) : null,
        priority,
        pending_attachments: pendingAttachments,
      }

      const payload = form.type === 'task'
        ? shared
        : {
          ...shared,
          release_id: releasesAllowed ? (form.releaseId || null) : null,
          environment_name: form.environment || null,
          curl_command: form.curlCommand || null,
          is_release_blocker: form.isReleaseBlocker,
          reproduction_steps: form.steps
            .map((step, idx) => {
              if (!step.trim()) return null
              return {
                step_order: idx + 1,
                description: step,
                expected_result: null,
                actual_result: null,
              }
            })
            .filter(Boolean),
        }

      const response = await issuesApi.create(payload)
      const issue = response.data

      onCreated?.(issue)
      onClose?.()

      setForm({ ...INITIAL_FORM, projectId: projects[0]?.id ?? '' })
      setAttachments([])
      setPendingAttachments([])
      setErrors({})
    } catch (err) {
      console.error('Failed to save issue:', err)
      setErrors((e) => ({ ...e, submit: err.response?.data?.detail || err.normalizedMessage || 'Failed to save issue' }))
    } finally {
      setLoading(false)
    }
  }

  const isSubmitting = loading || dataLoading || isUploading
  const attachmentsDisabled = loading || dataLoading
  const isTask = form.type === 'task'

  return (
    <Dialog open={open} onClose={onClose} title={isTask ? 'New Task' : 'New Bug'} size="xl">
      <div className="flex flex-col max-h-[calc(90vh-60px)]">
        {/* Scrollable content area */}
        <div className="flex-1 overflow-y-auto px-5 scrollbar-thin">
          <div className="py-5 space-y-5">
            {dataLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="text-muted-foreground text-sm">Loading…</div>
              </div>
            ) : (
              <>
                {/* Type */}
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">Type</label>
                  <Segmented
                    value={form.type}
                    onValueChange={setType}
                    options={[
                      { value: 'bug', label: TYPE.bug.label, icon: <Icon name={TYPE.bug.icon} size={14} /> },
                      { value: 'task', label: TYPE.task.label, icon: <Icon name={TYPE.task.icon} size={14} /> },
                    ]}
                  />
                </div>

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

                {/* Project + Release (bugs) + Priority in one row */}
                <div className={cn('grid gap-3', isTask ? 'grid-cols-[200px_1fr]' : 'grid-cols-[200px_180px_1fr]')}>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">Project</label>
                    <ProjectSwitcher
                      projects={projects}
                      activeProjectId={form.projectId}
                      onChange={setProject}
                    />
                  </div>
                  {!isTask && releasesAllowed && (
                    <div>
                      <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                        Release <span className="text-muted-foreground/70 font-normal">(optional)</span>
                      </label>
                      <ReleaseSwitcher
                        releases={availableReleases}
                        activeReleaseId={form.releaseId}
                        onChange={(id) => set('releaseId', id)}
                        allowNone
                      />
                    </div>
                  )}
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                      Priority{' '}
                      {!isTask && <span className="text-muted-foreground/70 font-normal">(optional until triage)</span>}
                    </label>
                    <div className="overflow-x-auto overflow-y-hidden -mx-1 px-1">
                      <div className="flex gap-1 min-w-max pb-1">
                        {!isTask && (
                          <PriorityOption selected={priority == null} onClick={() => set('priority', null)}>
                            Unrated
                          </PriorityOption>
                        )}
                        {PRIORITIES.map(p => (
                          <PriorityOption key={p} selected={priority === p} onClick={() => set('priority', p)}>
                            <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', PRIORITY[p].dot)} />
                            {PRIORITY[p].label}
                          </PriorityOption>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Assignee + Due date */}
                <div className="grid grid-cols-[1fr_180px] gap-3 items-end">
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">Assignee</label>
                    <Select
                      value={form.assigneeId}
                      onChange={(id) => set('assigneeId', id)}
                      placeholder="Unassigned"
                    >
                      {teamUsers.map((u) => (
                        <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">Due date</label>
                    <DatePicker
                      value={form.dueDate}
                      onChange={(date) => set('dueDate', date)}
                      placeholder="No due date"
                    />
                  </div>
                </div>

                {!isTask && (
                  <>
                    {/* Environment */}
                    <div>
                      <label className="block text-xs font-medium text-muted-foreground mb-1.5">Environment</label>
                      <div className="flex flex-wrap gap-1">
                        {Object.values(ENVIRONMENT).map(env => (
                          <button
                            key={env.value}
                            onClick={() => set('environment', form.environment === env.value ? null : env.value)}
                            className={cn(
                              'h-8 px-2 rounded-md text-[11px] font-medium border transition-colors',
                              'flex items-center gap-1 whitespace-nowrap',
                              form.environment === env.value
                                ? 'bg-foreground text-background border-foreground dark:bg-background dark:text-foreground dark:border-background'
                                : 'bg-background text-muted-foreground border-border hover:bg-muted dark:bg-background dark:text-muted-foreground dark:border-border dark:hover:bg-muted'
                            )}
                          >
                            {env.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Switch checked={form.isReleaseBlocker} onCheckedChange={(v) => set('isReleaseBlocker', v)} />
                      <span className="text-sm font-medium">Release blocker</span>
                    </div>
                  </>
                )}

            {/* Description */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Description</label>
              <CommentComposer
                initialValue={form.description}
                onChange={(val) => set('description', val)}
                placeholder={isTask ? 'Describe the task…' : 'Describe the issue, expected vs actual behavior…'}
                showInternal={false}
                hideFooter={true}
                users={teamUsers}
              />
            </div>

            {!isTask && (
              <>
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
              </>
            )}

            {/* Labels */}
            {labels.length > 0 && (
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-2">Labels</label>
                <div className="flex flex-wrap gap-2">
                  {labels.map((l) => {
                    const selected = form.labels.includes(l.name)
                    return (
                      <button
                        key={l.id}
                        onClick={() => toggleLabel(l.name)}
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
            )}

            {/* Attachments */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Paperclip className="h-4 w-4 text-muted-foreground" />
                <label className="text-xs font-medium text-muted-foreground">Attachments</label>
              </div>
              <AttachmentsSection
                issue={issueWrapper}
                onAttachmentsChange={setAttachments}
                disabled={attachmentsDisabled}
                onUploadingChange={setIsUploading}
                onPendingAttachment={handlePendingAttachment}
              />
            </div>
              </>
            )}
          </div>
        </div>

        {/* Fixed footer */}
        <div className="flex justify-between items-center border-t border-border px-5 py-4 shrink-0 bg-background">
          <div>
            {errors.submit && <p className="text-xs text-destructive">{errors.submit}</p>}
          </div>
          <div className="flex gap-3">
            <Button variant="ghost" onClick={onClose} disabled={loading}>Cancel</Button>
            <Button onClick={handleSubmit} loading={loading} disabled={isUploading}>
              {loading ? 'Creating...' : isTask ? 'Create Task' : 'Create Bug'}
            </Button>
          </div>
        </div>
      </div>
    </Dialog>
  )
}

function PriorityOption({ selected, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        'h-8 px-2 rounded-md text-[11px] font-medium border transition-colors',
        'flex items-center gap-1 whitespace-nowrap',
        selected
          ? 'bg-foreground text-background border-foreground dark:bg-background dark:text-foreground dark:border-background'
          : 'bg-background text-muted-foreground border-border hover:bg-muted dark:bg-background dark:text-muted-foreground dark:border-border dark:hover:bg-muted'
      )}
    >
      {children}
    </button>
  )
}
