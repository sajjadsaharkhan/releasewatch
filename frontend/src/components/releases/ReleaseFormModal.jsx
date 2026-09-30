import React, { useEffect, useState } from 'react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Textarea } from '../ui/Textarea'
import { DatePicker } from '../ui/DatePicker'
import { Select, SelectItem } from '../ui/Select'
import { useApp } from '../../hooks/useApp'
import { projectsApi, releasesApi } from '../../lib/api'

// Create or edit a release (FR-49): name (version), description, code freeze
// date, target ship date, staging URL. Status is never edited here — the
// lifecycle menu and Ship do that (FR-50).

const toDay = (d) => (d ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` : null)
const fromDay = (s) => (s ? new Date(`${String(s).slice(0, 10)}T00:00:00`) : null)

function emptyForm(release) {
  return {
    version: release?.version ?? '',
    description: release?.description ?? '',
    codeFreeze: fromDay(release?.code_freeze_date),
    target: release?.target_date ? new Date(release.target_date) : null,
    stagingUrl: release?.staging_url ?? '',
  }
}

export function ReleaseFormModal({ open, onClose, release = null, projectId = null, onSaved }) {
  const { projects = [], activeProjectId } = useApp()
  const editing = Boolean(release)
  const [form, setForm] = useState(emptyForm(release))
  const [project, setProject] = useState(projectId ?? activeProjectId ?? '')
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setForm(emptyForm(release))
    setErrors({})
    setProject(projectId ?? activeProjectId ?? projects[0]?.id ?? '')
  }, [open, release, projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k, v) => { setForm((f) => ({ ...f, [k]: v })); setErrors((e) => ({ ...e, [k]: undefined })) }

  function validate() {
    const e = {}
    if (!form.version.trim()) e.version = 'Give the release a name, e.g. 2.4.0.'
    if (!editing && !project) e.project = 'Choose a project.'
    if (form.stagingUrl && !/^https?:\/\//i.test(form.stagingUrl.trim())) e.stagingUrl = 'Start the URL with http:// or https://.'
    if (form.codeFreeze && form.target && toDay(form.codeFreeze) > toDay(form.target)) {
      e.codeFreeze = 'Code freeze comes before the target ship date.'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  async function submit(ev) {
    ev.preventDefault()
    if (!validate()) return
    const payload = {
      version: form.version.trim(),
      description: form.description.trim() || null,
      code_freeze_date: toDay(form.codeFreeze),
      target_date: form.target ? new Date(`${toDay(form.target)}T12:00:00`).toISOString() : null,
      staging_url: form.stagingUrl.trim() || null,
    }
    setSaving(true)
    try {
      const res = editing
        ? await releasesApi.update(release.id, payload)
        : await projectsApi.createRelease(project, payload)
      onSaved?.(res.data)
      onClose?.()
    } catch (err) {
      setErrors({ _form: err.response?.data?.detail || `Could not ${editing ? 'save' : 'create'} the release.` })
    } finally {
      setSaving(false)
    }
  }

  const field = (label, key, control, hint) => (
    <div>
      <label className="block text-xs font-medium text-muted-foreground mb-1.5" htmlFor={`release-${key}`}>{label}</label>
      {control}
      {errors[key]
        ? <p className="mt-1 text-xs text-red-600 dark:text-red-400" role="alert">{errors[key]}</p>
        : hint && <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  )

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} title={editing ? `Edit ${release.version}` : 'New release'} size="md">
      <form onSubmit={submit} className="p-5 space-y-4" noValidate>
        {errors._form && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400">
            {errors._form}
          </div>
        )}
        {!editing && !projectId && field('Project', 'project', (
          <Select value={project} onChange={setProject} placeholder="Choose a project">
            {projects.filter((p) => !p.archived_at).map((p) => (
              <SelectItem key={p.id} value={p.id}>
                <span className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
                  {p.name}
                </span>
              </SelectItem>
            ))}
          </Select>
        ))}
        {field('Name', 'version', (
          <Input id="release-version" autoFocus value={form.version} onChange={(e) => set('version', e.target.value)}
            placeholder="2.4.0" className="font-mono" aria-invalid={Boolean(errors.version)} />
        ), editing ? null : 'New releases start in Planning.')}
        {field('Description', 'description', (
          <Textarea id="release-description" rows={3} value={form.description}
            onChange={(e) => set('description', e.target.value)} placeholder="What this release is for" />
        ))}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {field('Code freeze', 'codeFreeze', (
            <DatePicker value={form.codeFreeze} onChange={(d) => set('codeFreeze', d)} placeholder="Optional" />
          ), 'When QA starts.')}
          {field('Target ship date', 'target', (
            <DatePicker value={form.target} onChange={(d) => set('target', d)} placeholder="Optional" />
          ), 'Past this date it shows as Overdue.')}
        </div>
        {field('Staging URL', 'stagingUrl', (
          <Input id="release-stagingUrl" type="url" value={form.stagingUrl} onChange={(e) => set('stagingUrl', e.target.value)}
            placeholder="https://staging.example.com" aria-invalid={Boolean(errors.stagingUrl)} />
        ))}
        <div className="flex justify-end gap-2 border-t border-border -mx-5 px-5 pt-4">
          <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button type="submit" loading={saving}>{editing ? 'Save changes' : 'Create release'}</Button>
        </div>
      </form>
    </Dialog>
  )
}
