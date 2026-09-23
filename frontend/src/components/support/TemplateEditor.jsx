import React, { useEffect, useMemo, useState } from 'react'
import { DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors } from '@dnd-kit/core'
import {
  SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Switch } from '../ui/Switch'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { Select, SelectItem } from '../ui/Select'
import { FieldShell, FIELD_TYPES, TemplateFields } from './TemplateFields'
import { templatesApi } from '../../lib/api'
import { useToast } from '../../hooks/useToast'

// The template builder (Settings → Support intake → project → template).
// Left: the fields as compact rows, one expanded at a time. Right: a live
// preview rendered by the same component Support's New report uses. One save
// model — the Live switch is part of the draft like everything else.

let seq = 0
const newKey = () => `k${++seq}`

// An option's stored value comes from its label; existing values are kept so
// renaming a label never orphans a value already sent in a report.
const slug = (s) => s.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'option'

function toDraft(f) {
  return {
    key: f.id ? `f${f.id}` : newKey(),
    id: f.id ?? null,
    label: f.label ?? '',
    field_type: f.field_type ?? 'short_text',
    is_required: f.is_required ?? false,
    help_text: f.help_text ?? '',
    options: (f.options ?? []).map((o) => ({ ...o, key: newKey() })),
  }
}

export function fieldsPayload(drafts) {
  return drafts.map((d) => {
    const used = new Set()
    const options = d.field_type === 'single_select'
      ? d.options.filter((o) => o.label.trim()).map((o) => {
        let value = o.value || slug(o.label)
        while (used.has(value)) value = `${value}_2`
        used.add(value)
        return { value, label: o.label.trim() }
      })
      : null
    return {
      id: d.id ?? undefined,
      label: d.label.trim(),
      field_type: d.field_type,
      is_required: d.is_required,
      help_text: d.help_text.trim() || null,
      options,
    }
  })
}

function problemsOf(name, drafts) {
  const out = {}
  if (!name.trim()) out.name = 'Give the template a name.'
  const seen = new Map()
  for (const d of drafts) {
    const label = d.label.trim().toLowerCase()
    if (!label) out[d.key] = 'Give this question a label.'
    else if (seen.has(label)) out[d.key] = 'Another question already uses this label.'
    else if (d.field_type === 'single_select' && !d.options.some((o) => o.label.trim())) {
      out[d.key] = 'Add at least one option.'
    }
    seen.set(label, d.key)
  }
  return out
}

export function TemplateEditor({ project, template, isLastLive, onBack, onSaved }) {
  const { toast } = useToast()
  const [name, setName] = useState(template.name)
  const [live, setLive] = useState(template.is_active)
  const [drafts, setDrafts] = useState(() => template.fields.map(toDraft))
  const [expanded, setExpanded] = useState(null)
  const [saving, setSaving] = useState(false)
  const [showProblems, setShowProblems] = useState(false)
  const [confirm, setConfirm] = useState(null) // 'turn-off' | 'leave'

  const baseline = useMemo(
    () => JSON.stringify([template.name, template.is_active, fieldsPayload(template.fields.map(toDraft))]),
    [template]
  )
  const dirty = JSON.stringify([name.trim(), live, fieldsPayload(drafts)]) !== baseline
  const problems = problemsOf(name, drafts)
  const hasProblems = Object.keys(problems).length > 0

  // Closing the browser tab with unsaved edits asks first.
  useEffect(() => {
    if (!dirty) return
    const handler = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  function update(key, patch) {
    setDrafts((list) => list.map((d) => (d.key === key ? { ...d, ...patch } : d)))
  }

  function addField(type) {
    const d = toDraft({ field_type: type })
    if (type === 'single_select') d.options = []
    setDrafts((list) => [...list, d])
    setExpanded(d.key)
    requestAnimationFrame(() => document.getElementById(`${d.key}-label`)?.focus())
  }

  function removeField(key) {
    setDrafts((list) => list.filter((d) => d.key !== key))
    if (expanded === key) setExpanded(null)
  }

  function handleDragEnd({ active, over }) {
    if (!over || active.id === over.id) return
    setDrafts((list) => arrayMove(
      list, list.findIndex((d) => d.key === active.id), list.findIndex((d) => d.key === over.id),
    ))
  }

  function toggleLive(next) {
    if (!next && template.is_active && isLastLive) setConfirm('turn-off')
    else setLive(next)
  }

  function back() {
    if (dirty) setConfirm('leave')
    else onBack()
  }

  function discard() {
    setName(template.name)
    setLive(template.is_active)
    setDrafts(template.fields.map(toDraft))
    setShowProblems(false)
  }

  async function save() {
    if (hasProblems) {
      setShowProblems(true)
      const firstField = drafts.find((d) => problems[d.key])
      if (firstField) setExpanded(firstField.key)
      return
    }
    setSaving(true)
    try {
      let latest = template
      if (name.trim() !== template.name) {
        latest = (await templatesApi.rename(project.id, template.id, name.trim())).data
      }
      const payload = fieldsPayload(drafts)
      if (JSON.stringify(payload) !== JSON.stringify(fieldsPayload(template.fields.map(toDraft)))) {
        latest = (await templatesApi.replaceFields(project.id, template.id, payload)).data
      }
      if (live !== template.is_active) {
        latest = (live
          ? await templatesApi.activate(project.id, template.id)
          : await templatesApi.deactivate(project.id, template.id)).data
      }
      setShowProblems(false)
      // Re-seed from what the server stored (new questions now have ids).
      setName(latest.name)
      setLive(latest.is_active)
      setDrafts(latest.fields.map(toDraft))
      setExpanded(null)
      onSaved(latest)
      toast({ title: 'Template saved', body: 'New reports use it right away. Reports already filed are unchanged.' })
    } catch (err) {
      toast({ title: 'Failed to save template', body: err.response?.data?.detail || 'Try again in a moment.' })
    } finally {
      setSaving(false)
    }
  }

  const previewFields = drafts.map((d) => ({
    id: d.key,
    label: d.label,
    field_type: d.field_type,
    is_required: d.is_required,
    help_text: d.help_text,
    options: d.options.filter((o) => o.label.trim()).map((o) => ({ value: o.value || o.key, label: o.label })),
  }))

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={back}
          className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Icon name="arrow-left" size={14} aria-hidden />
          {project.name}
        </button>
        <div className="ml-auto flex items-center gap-2">
          {dirty && <span className="text-[12px] text-muted-foreground mr-1">Unsaved changes</span>}
          <Button variant="ghost" size="sm" disabled={!dirty || saving} onClick={discard}>Discard</Button>
          <Button size="sm" disabled={!dirty || saving} onClick={save}>{saving ? 'Saving…' : 'Save template'}</Button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-4 rounded-xl border border-border bg-card p-4">
        <FieldShell id="template-name" label="Template name" error={showProblems ? problems.name : null} className="flex-1 min-w-[16rem]">
          <Input
            id="template-name"
            value={name}
            maxLength={120}
            error={showProblems && !!problems.name}
            placeholder="e.g. Online class problem"
            onChange={(e) => setName(e.target.value)}
          />
        </FieldShell>
        <div className="flex items-center gap-3 pb-1.5">
          <Switch checked={live} onCheckedChange={toggleLive} aria-label="Live" />
          <div className="leading-tight">
            <p className="text-sm font-medium text-foreground">{live ? 'Live' : 'Off'}</p>
            <p className="text-[12px] text-muted-foreground">{live ? 'Support can use it' : 'Hidden from Support'}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-start">
        {/* Builder */}
        <section aria-labelledby="fields-heading" className="min-w-0">
          <div className="flex items-baseline justify-between mb-2">
            <h3 id="fields-heading" className="text-sm font-semibold text-foreground">Questions</h3>
            <span className="text-[12px] text-muted-foreground">Drag to reorder</span>
          </div>

          {drafts.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center">
              <Icon name="list-plus" size={22} className="mx-auto mb-2 text-muted-foreground" aria-hidden />
              <p className="text-sm font-medium text-foreground">No questions yet</p>
              <p className="mt-0.5 text-[13px] text-muted-foreground">
                Support always gives a title and description. Add what else the team needs to know.
              </p>
            </div>
          ) : (
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={drafts.map((d) => d.key)} strategy={verticalListSortingStrategy}>
                <ul className="space-y-2">
                  {drafts.map((d) => (
                    <FieldRow
                      key={d.key}
                      draft={d}
                      open={expanded === d.key}
                      problem={showProblems ? problems[d.key] : null}
                      onToggle={() => setExpanded((k) => (k === d.key ? null : d.key))}
                      onChange={(patch) => update(d.key, patch)}
                      onRemove={() => removeField(d.key)}
                    />
                  ))}
                </ul>
              </SortableContext>
            </DndContext>
          )}

          <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => addField('short_text')}>
            <Icon name="plus" size={14} aria-hidden /> Add question
          </Button>
        </section>

        {/* Preview */}
        <section aria-labelledby="preview-heading" className="min-w-0 lg:sticky lg:top-4">
          <div className="flex items-baseline justify-between mb-2">
            <h3 id="preview-heading" className="text-sm font-semibold text-foreground">Preview</h3>
            <span className="text-[12px] text-muted-foreground">What Support sees</span>
          </div>
          <FormPreview name={name} fields={previewFields} />
        </section>
      </div>

      <Dialog open={confirm === 'turn-off'} onClose={() => setConfirm(null)} title="Turn off this template?" size="sm">
        <p className="px-5 py-4 text-sm text-muted-foreground">
          It's <strong className="text-foreground">{project.name}</strong>'s only live template. Support won't be able to
          report on this project until a template is live again. Reports already filed stay as they are.
        </p>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <Button variant="ghost" onClick={() => setConfirm(null)}>Keep it live</Button>
          <Button variant="destructive" onClick={() => { setLive(false); setConfirm(null) }}>Turn off</Button>
        </div>
      </Dialog>

      <Dialog open={confirm === 'leave'} onClose={() => setConfirm(null)} title="Leave without saving?" size="sm">
        <p className="px-5 py-4 text-sm text-muted-foreground">Your changes to this template will be lost.</p>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <Button variant="ghost" onClick={() => setConfirm(null)}>Keep editing</Button>
          <Button variant="destructive" onClick={() => { setConfirm(null); onBack() }}>Leave</Button>
        </div>
      </Dialog>
    </div>
  )
}

function FieldRow({ draft, open, problem, onToggle, onChange, onRemove }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: draft.key })
  const meta = FIELD_TYPES[draft.field_type] ?? FIELD_TYPES.short_text
  const style = { transform: CSS.Transform.toString(transform), transition }
  const k = draft.key

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={cn(
        'rounded-xl border bg-card transition-shadow',
        problem ? 'border-destructive/60' : open ? 'border-ring/60 shadow-sm' : 'border-border',
        isDragging && 'shadow-lg relative z-10'
      )}
    >
      <div className="flex items-center gap-1 pl-1.5 pr-2">
        <button
          type="button"
          className="h-8 w-7 shrink-0 flex items-center justify-center rounded text-muted-foreground/70 hover:text-foreground cursor-grab active:cursor-grabbing focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={`Reorder ${draft.label || 'question'}`}
          {...attributes}
          {...listeners}
        >
          <Icon name="grip-vertical" size={14} aria-hidden />
        </button>
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          className="flex flex-1 min-w-0 items-center gap-2.5 py-2.5 text-left rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="h-7 w-7 shrink-0 rounded-md bg-muted flex items-center justify-center text-muted-foreground" title={meta.label}>
            <Icon name={meta.icon} size={14} aria-hidden />
          </span>
          <span className="min-w-0 flex-1">
            <span className={cn('block truncate text-sm', draft.label ? 'text-foreground font-medium' : 'text-muted-foreground italic')}>
              {draft.label || 'Untitled question'}
            </span>
            <span className="block text-[11.5px] text-muted-foreground">
              {meta.label}
              {draft.field_type === 'single_select' && ` · ${draft.options.filter((o) => o.label.trim()).length} options`}
            </span>
          </span>
          {draft.is_required && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-foreground/80">Required</span>
          )}
          <Icon name={open ? 'chevron-up' : 'chevron-down'} size={15} className="text-muted-foreground shrink-0" aria-hidden />
        </button>
      </div>

      {problem && !open && (
        <p className="px-4 pb-2 -mt-1 text-[12px] text-destructive flex items-center gap-1">
          <Icon name="circle-alert" size={12} aria-hidden />{problem}
        </p>
      )}

      {open && (
        <div className="border-t border-border px-4 py-4 space-y-4">
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_11rem]">
            <FieldShell id={`${k}-label`} label="Question" error={problem && !draft.label.trim() ? problem : null}>
              <Input
                id={`${k}-label`}
                value={draft.label}
                maxLength={120}
                placeholder="e.g. Class time"
                error={!!problem && !draft.label.trim()}
                onChange={(e) => onChange({ label: e.target.value })}
              />
            </FieldShell>
            <FieldShell label="Answer type">
              <Select value={draft.field_type} onChange={(v) => onChange({ field_type: v })}>
                {Object.entries(FIELD_TYPES).map(([v, m]) => (
                  <SelectItem key={v} value={v}>
                    <span className="flex items-center gap-2">
                      <Icon name={m.icon} size={14} className="text-muted-foreground shrink-0" aria-hidden />
                      {m.label}
                    </span>
                  </SelectItem>
                ))}
              </Select>
            </FieldShell>
          </div>

          {draft.field_type === 'single_select' && (
            <OptionsInput
              id={`${k}-options`}
              options={draft.options}
              error={problem && draft.label.trim() ? problem : null}
              onChange={(options) => onChange({ options })}
            />
          )}

          <FieldShell id={`${k}-help`} label="Help text" optional>
            <Input
              id={`${k}-help`}
              value={draft.help_text}
              maxLength={500}
              placeholder="Shown under the question, e.g. “In the customer's local time”"
              onChange={(e) => onChange({ help_text: e.target.value })}
            />
          </FieldShell>

          <div className="flex items-center justify-between pt-1">
            <label className="flex items-center gap-2.5 text-sm text-foreground cursor-pointer">
              <Switch checked={draft.is_required} onCheckedChange={(v) => onChange({ is_required: v })} />
              Required
            </label>
            <Button type="button" variant="ghost" size="sm" className="text-destructive hover:bg-destructive/10" onClick={onRemove}>
              <Icon name="trash-2" size={14} aria-hidden /> Remove question
            </Button>
          </div>
        </div>
      )}
    </li>
  )
}

/** Options as chips — type and press Enter (or comma) to add. */
function OptionsInput({ id, options, error, onChange }) {
  const [text, setText] = useState('')
  const visible = options.filter((o) => o.label.trim())

  function add() {
    const label = text.trim()
    if (!label) return
    if (!visible.some((o) => o.label.toLowerCase() === label.toLowerCase())) {
      onChange([...visible, { key: newKey(), label }])
    }
    setText('')
  }

  return (
    <FieldShell id={id} label="Options" error={error}>
      <div className={cn(
        'flex flex-wrap items-center gap-1.5 rounded-[var(--radius)] border bg-transparent px-2 py-1.5 shadow-sm focus-within:ring-1 focus-within:ring-ring',
        error ? 'border-destructive' : 'border-input'
      )}>
        {visible.map((o) => (
          <span key={o.key} className="inline-flex items-center gap-1 rounded-md bg-muted pl-2 pr-1 py-0.5 text-[13px] text-foreground">
            {o.label}
            <button
              type="button"
              aria-label={`Remove ${o.label}`}
              onClick={() => onChange(visible.filter((x) => x.key !== o.key))}
              className="rounded p-0.5 text-muted-foreground hover:text-foreground hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Icon name="x" size={12} aria-hidden />
            </button>
          </span>
        ))}
        <input
          id={id}
          value={text}
          onChange={(e) => setText(e.target.value.replace(',', ''))}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add() }
            if (e.key === 'Backspace' && !text && visible.length) onChange(visible.slice(0, -1))
          }}
          onBlur={add}
          placeholder={visible.length ? 'Add another…' : 'Type an option and press Enter'}
          className="flex-1 min-w-[10rem] bg-transparent py-0.5 text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
    </FieldShell>
  )
}

/** A faithful, non-interactive mock of the New report modal's body for this template. */
function FormPreview({ name, fields }) {
  return (
    <div className="rounded-xl border border-border bg-background shadow-sm overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <span className="text-sm font-semibold text-foreground">New report</span>
        <Icon name="x" size={14} className="text-muted-foreground" aria-hidden />
      </div>
      <div className="p-4 space-y-4" inert="">
        <div>
          <span className="block text-xs font-medium text-muted-foreground mb-1.5">What's wrong?</span>
          <div className="flex h-9 items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 text-sm">
            <Icon name="clipboard-list" size={14} className="text-muted-foreground" aria-hidden />
            <span className={cn('font-medium truncate', name.trim() ? 'text-foreground' : 'text-muted-foreground italic')}>
              {name.trim() || 'Untitled template'}
            </span>
          </div>
        </div>
        <FieldShell id="preview-title" label="Title" required>
          <Input id="preview-title" placeholder="Summarize the problem in a few words…" readOnly />
        </FieldShell>
        <TemplateFields fields={fields} idPrefix="preview-field" />
        <div>
          <span className="flex items-baseline gap-1 text-xs font-medium text-muted-foreground mb-1.5">
            Anything else? <span className="font-normal text-muted-foreground/70">(optional)</span>
          </span>
          <div className="h-16 rounded-[var(--radius)] border border-input" />
        </div>
      </div>
    </div>
  )
}
