import React, { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { Dropdown, DropdownItem, DropdownSep } from '../ui/Dropdown'
import { Tooltip } from '../ui/Tooltip'
import { FieldShell } from './TemplateFields'
import { TemplateEditor, fieldsPayload } from './TemplateEditor'
import { templatesApi } from '../../lib/api'
import { relTime, fullTime } from '../../lib/relTime'
import { getContrastColor } from '../../lib/colors'
import { useApp } from '../../hooks/useApp'
import { useToast } from '../../hooks/useToast'

// Settings → Support intake (slice 05, FR-44). CTO and Admin decide which
// projects Support can report on and what Support is asked. Three levels, all
// in the URL so every view can be linked: projects → a project's templates →
// one template's editor.

export function SupportIntakeTab() {
  const { projects, refetchProjects } = useApp()
  const [params, setParams] = useSearchParams()
  const projectId = Number(params.get('project')) || null
  const templateId = Number(params.get('template')) || null

  const go = useCallback((next) => {
    setParams((p) => {
      const q = new URLSearchParams(p)
      for (const [k, v] of Object.entries(next)) {
        if (v == null) q.delete(k)
        else q.set(k, String(v))
      }
      return q
    })
  }, [setParams])

  const project = projects.find((p) => p.id === projectId)

  if (!project) {
    return <ProjectOverview projects={projects.filter((p) => !p.archived)} onOpen={(id) => go({ project: id, template: null })} />
  }
  return (
    <ProjectTemplates
      key={project.id}
      project={project}
      templateId={templateId}
      onOpenTemplate={(id) => go({ template: id })}
      onBack={() => go({ project: null, template: null })}
      onChanged={refetchProjects}
    />
  )
}

function ProjectMark({ project, size = 'h-8 w-8' }) {
  return (
    <span
      className={cn(size, 'rounded-lg shrink-0 flex items-center justify-center text-[12px] font-bold')}
      style={{ backgroundColor: project.color, color: getContrastColor(project.color) }}
      aria-hidden
    >
      {project.name?.[0]}
    </span>
  )
}

function IntakeStatus({ active }) {
  return active ? (
    <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-green-700 dark:text-green-400">
      <span className="h-1.5 w-1.5 rounded-full bg-green-500" aria-hidden />
      Accepting reports
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-[12px] text-muted-foreground">
      <span className="h-1.5 w-1.5 rounded-full bg-zinc-400" aria-hidden />
      Not accepting reports
    </span>
  )
}

// ── Level 1: every project ───────────────────────────────────────────────────

function ProjectOverview({ projects, onOpen }) {
  const accepting = projects.filter((p) => p.active_support_template_count > 0).length
  return (
    <div>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-foreground">Support intake</h2>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          Which projects Support can report on, and what they're asked. A project accepts reports while at least one
          of its templates is live.{' '}
          <span className="text-foreground/80">{accepting} of {projects.length} accepting.</span>
        </p>
      </div>
      <ul className="divide-y divide-border rounded-xl border border-border bg-card overflow-hidden">
        {projects.map((p) => {
          const total = p.support_template_count ?? 0
          const live = p.active_support_template_count ?? 0
          return (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => onOpen(p.id)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
              >
                <ProjectMark project={p} />
                <span className="flex-1 min-w-0">
                  <span className="block text-sm font-semibold text-foreground truncate">{p.name}</span>
                  <IntakeStatus active={live > 0} />
                </span>
                <span className="text-[13px] text-muted-foreground whitespace-nowrap">
                  {total === 0 ? 'No templates' : `${total} template${total === 1 ? '' : 's'}`}
                  {total > 0 && live < total && <span className="text-muted-foreground/70"> · {live} live</span>}
                </span>
                <Icon name="chevron-right" size={16} className="text-muted-foreground" aria-hidden />
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

// ── Level 2: one project's templates ─────────────────────────────────────────

function ProjectTemplates({ project, templateId, onOpenTemplate, onBack, onChanged }) {
  const { toast } = useToast()
  const [templates, setTemplates] = useState(null)
  const [creating, setCreating] = useState(false)
  const [confirmOff, setConfirmOff] = useState(null)

  const load = useCallback(() => {
    return templatesApi.list(project.id).then((res) => setTemplates(res.data)).catch(() => setTemplates([]))
  }, [project.id])

  useEffect(() => { load() }, [load])

  const liveCount = templates?.filter((t) => t.is_active).length ?? 0

  function replace(t) {
    setTemplates((list) => list.map((x) => (x.id === t.id ? t : x)))
    onChanged()
  }

  async function setLive(t, live) {
    try {
      const res = live ? await templatesApi.activate(project.id, t.id) : await templatesApi.deactivate(project.id, t.id)
      replace(res.data)
      toast({ title: live ? `${t.name} is live` : `${t.name} turned off` })
    } catch (err) {
      toast({ title: 'Failed to update template', body: err.response?.data?.detail || 'Try again in a moment.' })
    }
  }

  function requestOff(t) {
    if (t.is_active && liveCount === 1) setConfirmOff(t)
    else setLive(t, false)
  }

  async function duplicate(t) {
    try {
      const base = `${t.name} (copy)`
      let name = base
      for (let n = 2; templates.some((x) => x.name.toLowerCase() === name.toLowerCase()); n++) name = `${base} ${n}`
      const res = await templatesApi.create(project.id, {
        name,
        is_active: false,
        fields: fieldsPayload(t.fields.map((f) => ({ ...f, id: null, key: `d${f.id}`, help_text: f.help_text ?? '', options: f.options ?? [] }))),
      })
      setTemplates((list) => [...list, res.data])
      onChanged()
      onOpenTemplate(res.data.id)
    } catch (err) {
      toast({ title: 'Failed to duplicate template', body: err.response?.data?.detail || 'Try again in a moment.' })
    }
  }

  if (templates === null) {
    return <div className="flex justify-center py-16"><div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-primary" /></div>
  }

  const editing = templates.find((t) => t.id === templateId)
  if (editing) {
    return (
      <TemplateEditor
        key={editing.id}
        project={project}
        template={editing}
        isLastLive={editing.is_active && liveCount === 1}
        onBack={() => onOpenTemplate(null)}
        onSaved={replace}
      />
    )
  }

  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="mb-3 inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Icon name="arrow-left" size={14} aria-hidden /> Support intake
      </button>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <ProjectMark project={project} size="h-10 w-10" />
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-semibold text-foreground truncate">{project.name}</h2>
          <IntakeStatus active={liveCount > 0} />
        </div>
        {templates.length > 0 && (
          <Button onClick={() => setCreating(true)}>
            <Icon name="plus" size={14} aria-hidden /> New template
          </Button>
        )}
      </div>

      {templates.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border px-6 py-12 text-center">
          <span className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-muted">
            <Icon name="clipboard-list" size={20} className="text-muted-foreground" aria-hidden />
          </span>
          <p className="text-sm font-semibold text-foreground">Support can't report on {project.name} yet</p>
          <p className="mx-auto mt-1 max-w-sm text-[13px] text-muted-foreground">
            A template is a kind of problem — like “Online class problem” — with the questions Support must answer
            when reporting it.
          </p>
          <Button className="mt-4" onClick={() => setCreating(true)}>
            <Icon name="plus" size={14} aria-hidden /> Create the first template
          </Button>
        </div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {templates.map((t) => (
            <TemplateCard
              key={t.id}
              template={t}
              onEdit={() => onOpenTemplate(t.id)}
              onDuplicate={() => duplicate(t)}
              onToggle={() => (t.is_active ? requestOff(t) : setLive(t, true))}
            />
          ))}
        </ul>
      )}

      <NewTemplateDialog
        open={creating}
        project={project}
        templates={templates}
        onClose={() => setCreating(false)}
        onCreated={(t) => {
          setCreating(false)
          setTemplates((list) => [...list, t])
          onChanged()
          onOpenTemplate(t.id)
        }}
      />

      <Dialog open={!!confirmOff} onClose={() => setConfirmOff(null)} title="Turn off this template?" size="sm">
        <p className="px-5 py-4 text-sm text-muted-foreground">
          <strong className="text-foreground">{confirmOff?.name}</strong> is {project.name}'s only live template.
          Support won't be able to report on this project until a template is live again. Reports already filed stay as they are.
        </p>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <Button variant="ghost" onClick={() => setConfirmOff(null)}>Keep it live</Button>
          <Button variant="destructive" onClick={() => { setLive(confirmOff, false); setConfirmOff(null) }}>Turn off</Button>
        </div>
      </Dialog>
    </div>
  )
}

function TemplateCard({ template: t, onEdit, onDuplicate, onToggle }) {
  const required = t.fields.filter((f) => f.is_required).length
  return (
    <li className={cn(
      'group relative flex flex-col rounded-xl border bg-card p-4 transition-colors hover:border-ring/50',
      t.is_active ? 'border-border' : 'border-dashed border-border'
    )}>
      <div className="flex items-start gap-2">
        <button
          type="button"
          onClick={onEdit}
          className="flex-1 min-w-0 text-left rounded after:absolute after:inset-0 after:rounded-xl focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
        >
          <span className={cn('block text-sm font-semibold truncate', t.is_active ? 'text-foreground' : 'text-muted-foreground')}>
            {t.name}
          </span>
        </button>
        <span className={cn(
          'relative shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium',
          t.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' : 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400'
        )}>
          {t.is_active ? 'Live' : 'Off'}
        </span>
        <div className="relative -mr-1.5 -mt-1">
          <Dropdown
            align="right"
            width={180}
            trigger={
              <button
                type="button"
                aria-label={`More actions for ${t.name}`}
                className="h-7 w-7 flex items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Icon name="ellipsis" size={16} aria-hidden />
              </button>
            }
          >
            <DropdownItem onClick={onEdit}><Icon name="pencil" size={14} className="opacity-70" aria-hidden />Edit</DropdownItem>
            <DropdownItem onClick={onDuplicate}><Icon name="copy" size={14} className="opacity-70" aria-hidden />Duplicate</DropdownItem>
            <DropdownSep />
            <DropdownItem onClick={onToggle}>
              <Icon name="power" size={14} className="opacity-70" aria-hidden />{t.is_active ? 'Turn off' : 'Make live'}
            </DropdownItem>
          </Dropdown>
        </div>
      </div>

      <p className="mt-1 text-[12.5px] text-muted-foreground">
        {t.fields.length === 0
          ? 'No questions yet'
          : `${t.fields.length} question${t.fields.length === 1 ? '' : 's'}${required ? ` · ${required} required` : ''}`}
      </p>

      {t.fields.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-1" aria-label="Questions">
          {t.fields.slice(0, 4).map((f) => (
            <li key={f.id} className="rounded-md bg-muted px-1.5 py-0.5 text-[11.5px] text-foreground/80 truncate max-w-[10rem]">{f.label}</li>
          ))}
          {t.fields.length > 4 && <li className="px-1 py-0.5 text-[11.5px] text-muted-foreground">+{t.fields.length - 4}</li>}
        </ul>
      )}

      <p className="mt-auto pt-3 text-[11.5px] text-muted-foreground">
        <Tooltip content={fullTime(t.updated_at)}><span>Edited {relTime(t.updated_at)}</span></Tooltip>
      </p>
    </li>
  )
}

function NewTemplateDialog({ open, project, templates, onClose, onCreated }) {
  const { toast } = useToast()
  const [name, setName] = useState('')
  const [from, setFrom] = useState('blank')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) { setName(''); setFrom('blank'); setError(null) }
  }, [open])

  async function create(e) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) { setError('Give the template a name.'); return }
    if (templates.some((t) => t.name.toLowerCase() === trimmed.toLowerCase())) {
      setError('This project already has a template with that name.')
      return
    }
    const source = templates.find((t) => String(t.id) === from)
    setSaving(true)
    try {
      const res = await templatesApi.create(project.id, {
        name: trimmed,
        is_active: false,
        fields: source
          ? fieldsPayload(source.fields.map((f) => ({ ...f, id: null, key: `n${f.id}`, help_text: f.help_text ?? '', options: f.options ?? [] })))
          : [],
      })
      onCreated(res.data)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (err.response?.data?.code === 'template_name_taken') setError(detail)
      else toast({ title: 'Failed to create template', body: detail || 'Try again in a moment.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="New template" size="md">
      <form onSubmit={create} noValidate>
        <div className="px-5 py-4 space-y-4">
          <FieldShell
            id="new-template-name"
            label="Name"
            help="Name the kind of problem, so Support can pick it — e.g. “Payment problem”. It starts switched off; make it live once its questions are ready."
            error={error}
          >
            <Input
              id="new-template-name"
              autoFocus
              value={name}
              maxLength={120}
              error={!!error}
              placeholder="e.g. Online class problem"
              onChange={(e) => { setName(e.target.value); setError(null) }}
            />
          </FieldShell>
          {templates.length > 0 && (
            <fieldset>
              <legend className="text-xs font-medium text-muted-foreground mb-1.5">Start from</legend>
              <div className="space-y-1.5">
                {[{ id: 'blank', name: 'Blank template', hint: 'Add your own questions' },
                  ...templates.map((t) => ({ id: String(t.id), name: `Copy of ${t.name}`, hint: `${t.fields.length} questions` }))]
                  .map((o) => (
                    <label
                      key={o.id}
                      className={cn(
                        'flex items-center gap-3 rounded-lg border px-3 py-2 cursor-pointer transition-colors',
                        from === o.id ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/50'
                      )}
                    >
                      <input
                        type="radio"
                        name="template-source"
                        value={o.id}
                        checked={from === o.id}
                        onChange={() => setFrom(o.id)}
                        className="accent-primary"
                      />
                      <span className="min-w-0">
                        <span className="block text-sm text-foreground truncate">{o.name}</span>
                        <span className="block text-[12px] text-muted-foreground">{o.hint}</span>
                      </span>
                    </label>
                  ))}
              </div>
            </fieldset>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create and edit'}</Button>
        </div>
      </form>
    </Dialog>
  )
}
