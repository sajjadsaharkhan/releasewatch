import React, { useState, useEffect } from 'react'
import { Plus, Trash2, Paperclip } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { CommentComposer } from './CommentComposer'
import { AttachmentsSection } from './AttachmentsSection'
import { ProjectSwitcher, ReleaseSwitcher } from '../common'
import { SEVERITY } from '../../lib/constants'
import { ENVIRONMENT } from './DescriptionSection'
import { issuesApi, projectsApi, releasesApi, labelsApi, teamApi } from '../../lib/api'
import { useApp } from '../../hooks/useApp'

export function NewIssueModal({ open, onClose, onCreated }) {
  const { activeProjectId, activeReleaseId } = useApp()
  const [form, setForm] = useState({
    title: '',
    projectId: activeProjectId || '',
    releaseId: activeReleaseId || '',
    severity: 'major',
    environment: null,
    description: '',
    steps: [''],
    curlCommand: '',
    labels: [],
  })
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

  // Fetch projects, releases, and labels on mount
  useEffect(() => {
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

        // Set initial values from AppContext or defaults
        setForm((f) => ({
          ...f,
          projectId: activeProjectId || projectsRes.data?.[0]?.id || '',
          releaseId: activeReleaseId || '',
        }))
      } catch (err) {
        console.error('Failed to load data:', err)
      } finally {
        setDataLoading(false)
      }
    }
    if (open) fetchData()
  }, [open, activeProjectId, activeReleaseId])

  // Reset form when modal closes
  useEffect(() => {
    if (!open) {
      setAttachments([])
      setPendingAttachments([])
      setForm({
        title: '',
        projectId: activeProjectId || projects[0]?.id || '',
        releaseId: activeReleaseId || '',
        severity: 'major',
        environment: null,
        description: '',
        steps: [''],
        curlCommand: '',
        labels: [],
      })
      setErrors({})
    }
  }, [open, activeProjectId, activeReleaseId])

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
    if (!form.releaseId) errs.releaseId = 'Please select a release'
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
      // Build reproduction steps from the form
      const reproductionSteps = form.steps
        .map((step, idx) => {
          if (!step.trim()) return null
          return {
            step_order: idx + 1,
            description: step,
            expected_result: null,
            actual_result: null,
          }
        })
        .filter(Boolean)

      const payload = {
        title: form.title,
        release_id: form.releaseId,
        description: form.description || null,
        severity: form.severity,
        environment_name: form.environment || null,
        labels: form.labels,
        curl_command: form.curlCommand || null,
        reproduction_steps: reproductionSteps,
        pending_attachments: pendingAttachments,
      }

      const response = await issuesApi.create(payload)
      const issue = response.data

      onCreated?.(issue)
      onClose?.()

      // Reset form
      setForm({
        title: '',
        projectId: projects[0]?.id ?? '',
        releaseId: '',
        severity: 'major',
        environment: null,
        description: '',
        steps: [''],
        curlCommand: '',
        labels: [],
      })
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

  return (
    <Dialog open={open} onClose={onClose} title="New Issue" size="xl">
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
                      projects={projects}
                      activeProjectId={form.projectId}
                      onChange={(id) => set('projectId', id)}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                      Release <span className="text-destructive">*</span>
                    </label>
                    <ReleaseSwitcher
                      releases={availableReleases}
                      activeReleaseId={form.releaseId}
                      onChange={(id) => set('releaseId', id)}
                    />
                    {errors.releaseId && <p className="mt-1 text-xs text-destructive">{errors.releaseId}</p>}
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

            {/* Description */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Description</label>
              <CommentComposer
                initialValue={form.description}
                onChange={(val) => set('description', val)}
                placeholder="Describe the issue, expected vs actual behavior…"
                showInternal={false}
                hideFooter={true}
                users={teamUsers}
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
              {loading ? 'Creating...' : 'Create Issue'}
            </Button>
          </div>
        </div>
      </div>
    </Dialog>
  )
}
