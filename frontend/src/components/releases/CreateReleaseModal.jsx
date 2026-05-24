import React, { useState, useEffect } from 'react'
import { Tag, FileText, AlertCircle, FolderOpen } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Select, SelectItem } from '../ui/Select'
import { DatePicker } from '../ui/DatePicker'
import { releasesApi, projectsApi } from '../../lib/api'

export function CreateReleaseModal({ open, onClose, onCreated }) {
  const [projects, setProjects] = useState([])
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [form, setForm] = useState({
    version: '',
    projectId: '',
    targetDate: null,
    description: '',
  })
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})

  // Fetch projects on mount
  useEffect(() => {
    async function fetchProjects() {
      setLoadingProjects(true)
      try {
        const response = await projectsApi.list()
        const projectList = response.data || []
        setProjects(projectList)
        if (projectList.length > 0 && !form.projectId) {
          setForm((f) => ({ ...f, projectId: projectList[0].id }))
        }
      } catch (err) {
        console.error('Failed to fetch projects:', err)
        setProjects([])
      } finally {
        setLoadingProjects(false)
      }
    }
    if (open) {
      fetchProjects()
    }
  }, [open])

  const selectedProject = projects.find((p) => p.id === form.projectId)

  function set(key, val) {
    setForm((f) => ({ ...f, [key]: val }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  function validate() {
    const newErrors = {}
    if (!form.version.trim()) {
      newErrors.version = 'Version is required'
    }
    if (!form.projectId) {
      newErrors.projectId = 'Project is required'
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
      const response = await releasesApi.create({
        project_id: form.projectId,
        version: form.version,
        target_date: form.targetDate ? form.targetDate.toISOString() : null,
        description: form.description,
      })

      const newRelease = response.data
      onCreated?.(newRelease)
      onClose()

      // Reset form
      setForm({
        version: '',
        projectId: projects[0]?.id ?? '',
        targetDate: null,
        description: '',
      })
      setErrors({})
    } catch (err) {
      console.error('Failed to create release:', err)
      if (err.response?.data?.detail) {
        setErrors({ _form: err.response.data.detail })
      } else {
        setErrors({ _form: 'Failed to create release. Please try again.' })
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Release" size="md">
      <form onSubmit={handleSubmit} className="p-5 space-y-5">
        {errors._form && (
          <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/30 p-3 text-sm text-red-600 dark:text-red-400">
            {errors._form}
          </div>
        )}

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
          {loadingProjects ? (
            <div className="flex h-9 w-full items-center justify-center text-sm text-muted-foreground border border-input rounded-[var(--radius)]">
              Loading projects...
            </div>
          ) : projects.length === 0 ? (
            <div className="flex h-9 w-full items-center justify-center text-sm text-muted-foreground border border-input rounded-[var(--radius)]">
              No projects available
            </div>
          ) : (
            <Select
              value={form.projectId}
              onChange={(val) => set('projectId', val)}
              placeholder="Select a project"
              disabled={loading}
              className={errors.projectId && 'border-red-500'}
            >
              {projects.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: p.color }}
                    />
                    <span>{p.name}</span>
                  </div>
                </SelectItem>
              ))}
            </Select>
          )}
          {errors.projectId && (
            <p className="text-xs text-red-500 mt-1">{errors.projectId}</p>
          )}
        </div>

        {/* Target Date */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Target Date <span className="text-red-500">*</span>
          </label>
          <DatePicker
            value={form.targetDate}
            onChange={(date) => set('targetDate', date)}
            placeholder="Pick a target date"
            disabled={loading}
            minDate={new Date()}
            className={errors.targetDate && 'border-red-500'}
          />
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
        {selectedProject && (
          <div className="rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/30 p-3">
            <div className="flex items-start gap-2">
              <FolderOpen className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
              <div className="text-xs text-blue-800 dark:text-blue-300">
                <p className="font-medium mb-1">Selected Project</p>
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: selectedProject.color }}
                  />
                  <span className="font-medium">{selectedProject.name}</span>
                  {selectedProject.desc && (
                    <span className="text-muted-foreground">· {selectedProject.desc}</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

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
