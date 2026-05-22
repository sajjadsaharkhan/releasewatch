import React, { useState, useEffect } from 'react'
import { Calendar, Tag, FileText, AlertCircle } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { StatusBadge } from '../ui/Badge'
import { MOCK_PROJECTS } from '../../data/mockData'

export function EditReleaseModal({ open, onClose, release, onSave }) {
  const [form, setForm] = useState({
    version: '',
    targetDate: '',
    description: '',
    status: 'active',
    goNoGo: null,
  })
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})

  // Initialize form when release changes
  useEffect(() => {
    if (release) {
      setForm({
        version: release.version || '',
        targetDate: release.targetDate ? new Date(release.targetDate).toISOString().split('T')[0] : '',
        description: release.description || '',
        status: release.status || 'active',
        goNoGo: release.goNoGo || null,
      })
    }
  }, [release])

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
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!validate()) return

    setLoading(true)
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 600))

      const updatedRelease = {
        ...release,
        version: form.version,
        targetDate: new Date(form.targetDate).toISOString(),
        description: form.description,
        status: form.status,
        goNoGo: form.goNoGo,
      }

      onSave?.(updatedRelease)
      onClose()
    } catch (err) {
      console.error('Failed to update release:', err)
    } finally {
      setLoading(false)
    }
  }

  const statusOptions = [
    { value: 'active', label: 'Active', description: 'Currently in development' },
    { value: 'released', label: 'Released', description: 'Has been shipped' },
  ]

  return (
    <Dialog open={open} onClose={onClose} title="Edit Release" size="md">
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

        {/* Status */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Status
          </label>
          <div className="flex gap-2">
            {statusOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => set('status', option.value)}
                className={cn(
                  'flex-1 rounded-lg border p-3 text-left transition-colors',
                  form.status === option.value
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-border hover:bg-accent'
                )}
                disabled={loading}
              >
                <div className="flex items-center gap-2 mb-1">
                  <div className={cn(
                    'h-2 w-2 rounded-full',
                    form.status === option.value ? 'bg-blue-500' : 'bg-muted-foreground'
                  )} />
                  <span className="text-sm font-medium">{option.label}</span>
                </div>
                <p className="text-xs text-muted-foreground">{option.description}</p>
              </button>
            ))}
          </div>
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
            />
          </div>
          {errors.targetDate && (
            <p className="text-xs text-red-500 mt-1">{errors.targetDate}</p>
          )}
        </div>

        {/* Description */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Description
          </label>
          <div className="relative">
            <FileText className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <textarea
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              placeholder="Describe the goals and scope of this release..."
              className={cn(
                'flex min-h-[80px] w-full rounded-[var(--radius)] border border-input bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none pl-9',
                errors.description && 'border-red-500'
              )}
              disabled={loading}
            />
          </div>
        </div>

        {/* Info box */}
        <div className="rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700/50 p-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
            <div className="text-xs text-muted-foreground">
              <p className="font-medium mb-1 text-foreground">Release Details</p>
              <p>
                Project: <span className="font-medium text-foreground">{MOCK_PROJECTS.find(p => p.id === release?.projectId)?.name || 'Unknown'}</span>
              </p>
              <p>
                Created: <span className="font-medium text-foreground">{release?.createdAt ? new Date(release.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Unknown'}</span>
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
            Save Changes
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
