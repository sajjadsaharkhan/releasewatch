import React, { useState } from 'react'
import { Calendar, Tag, FileText, AlertCircle } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { MOCK_PROJECTS } from '../../data/mockData'

export function CreateReleaseModal({ open, onClose, onCreated }) {
  const [form, setForm] = useState({
    version: '',
    projectId: MOCK_PROJECTS[0]?.id ?? '',
    targetDate: '',
    description: '',
  })
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})

  const selectedProject = MOCK_PROJECTS.find((p) => p.id === form.projectId)

  function set(key, val) {
    setForm((f) => ({ ...f, [key]: val }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  function validate() {
    const newErrors = {}
    if (!form.version.trim()) {
      newErrors.version = 'Version is required'
    } else if (!/^[v]?\d+\.\d+\.\d+$/.test(form.version.trim())) {
      newErrors.version = 'Version must be in format v1.2.3 or 1.2.3'
    }
    if (!form.targetDate) {
      newErrors.targetDate = 'Target date is required'
    }
    if (!form.description.trim()) {
      newErrors.description = 'Description is required'
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!validate()) return

    setLoading(true)
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 800))

      const newRelease = {
        id: `rel-${Date.now()}`,
        projectId: form.projectId,
        version: form.version,
        status: 'active',
        createdAt: new Date().toISOString(),
        targetDate: new Date(form.targetDate).toISOString(),
        openIssues: 0,
        blockers: 0,
        totalIssues: 0,
        fixedIssues: 0,
        goNoGo: null,
        goNoGoBy: null,
        description: form.description,
      }

      onCreated?.(newRelease)
      onClose()

      // Reset form
      setForm({
        version: '',
        projectId: MOCK_PROJECTS[0]?.id ?? '',
        targetDate: '',
        description: '',
      })
    } catch (err) {
      console.error('Failed to create release:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Release" size="md">
      <form onSubmit={handleSubmit} className="p-5 space-y-5">
        {/* Version */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Version <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <Tag className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="v1.0.0"
              value={form.version}
              onChange={(e) => set('version', e.target.value)}
              className={cn('pl-9', errors.version && 'border-red-500')}
              disabled={loading}
            />
          </div>
          {errors.version && (
            <p className="text-xs text-red-500 mt-1">{errors.version}</p>
          )}
        </div>

        {/* Project */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Project <span className="text-red-500">*</span>
          </label>
          <select
            value={form.projectId}
            onChange={(e) => set('projectId', e.target.value)}
            className="flex h-9 w-full rounded-[var(--radius)] border border-input bg-transparent px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            disabled={loading}
          >
            {MOCK_PROJECTS.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        {/* Target Date */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Target Date <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="date"
              value={form.targetDate}
              onChange={(e) => set('targetDate', e.target.value)}
              className={cn('pl-9', errors.targetDate && 'border-red-500')}
              disabled={loading}
              min={new Date().toISOString().split('T')[0]}
            />
          </div>
          {errors.targetDate && (
            <p className="text-xs text-red-500 mt-1">{errors.targetDate}</p>
          )}
        </div>

        {/* Description */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Description <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <FileText className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <textarea
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              placeholder="Describe the goals and scope of this release..."
              className={cn(
                'flex min-h-[100px] w-full rounded-[var(--radius)] border border-input bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none pl-9',
                errors.description && 'border-red-500'
              )}
              disabled={loading}
            />
          </div>
          {errors.description && (
            <p className="text-xs text-red-500 mt-1">{errors.description}</p>
          )}
        </div>

        {/* Info box */}
        <div className="rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/30 p-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <div className="text-xs text-blue-800 dark:text-blue-300">
              <p className="font-medium mb-1">Release Information</p>
              <p className="text-muted-foreground">
                This will create a new release for <strong>{selectedProject?.name}</strong>.
                You can add issues and set milestones once the release is created.
              </p>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button type="submit" loading={loading}>
            Create Release
          </Button>
        </div>
      </form>
    </Dialog>
  )
}