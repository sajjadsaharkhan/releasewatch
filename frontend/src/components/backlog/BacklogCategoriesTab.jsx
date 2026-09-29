import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors,
} from '@dnd-kit/core'
import {
  SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { AlertTriangle, Check, GripVertical, Lock, Pencil, Plus, Trash2 } from 'lucide-react'
import { cn } from '../../lib/cn'
import { backlogCategoriesApi } from '../../lib/api'
import { getContrastColor } from '../../lib/colors'
import {
  CATEGORY_COLOR, CATEGORY_COLORS, CATEGORY_ICONS, CATEGORY_LIMIT, CATEGORY_NAME_MAX, categoryColor,
} from '../../lib/constants'
import { useApp } from '../../hooks/useApp'
import { useToast } from '../../hooks/useToast'
import { useInvalidateBacklogCategories } from '../../hooks/useBacklogCategories'
import { Button, Dialog, Icon, Input, Tooltip } from '../ui'
import { BacklogCategoryBadge } from '../common/BacklogCategoryBadge'

// Settings → Backlog categories (2026-09-28). CTO and Admin shape each project's
// backlog groups: a name, an icon and a colour from curated sets. Two levels,
// both in the URL (`?project=`): every project → one project's categories,
// edited in place. Default is fixed and always first; every other category can
// be renamed, restyled, dragged into order, or deleted — its items move to
// Default.

export function BacklogCategoriesTab() {
  const { projects, refetchProjects } = useApp()
  const [params, setParams] = useSearchParams()
  const projectId = Number(params.get('project')) || null
  const project = projects.find((p) => p.id === projectId)

  const go = useCallback((id) => {
    setParams((p) => {
      const q = new URLSearchParams(p)
      if (id == null) q.delete('project')
      else q.set('project', String(id))
      return q
    })
  }, [setParams])

  if (!project) {
    return <ProjectOverview projects={projects.filter((p) => !p.archived)} onOpen={go} />
  }
  return <ProjectCategories key={project.id} project={project} onBack={() => go(null)} onChanged={refetchProjects} />
}

function ProjectMark({ project, size = 'h-8 w-8' }) {
  return (
    <span
      className={cn(size, 'flex shrink-0 items-center justify-center rounded-lg text-[12px] font-bold')}
      style={{ backgroundColor: project.color, color: getContrastColor(project.color) }}
      aria-hidden
    >
      {project.name?.[0]}
    </span>
  )
}

/** The category's icon on its soft hue — the "chip" used in lists and previews. */
function CategoryChip({ category, size = 'h-8 w-8', iconSize = 15 }) {
  const hue = categoryColor(category.color)
  return (
    <span className={cn(size, 'flex shrink-0 items-center justify-center rounded-lg', hue.soft)} aria-hidden>
      <Icon name={category.icon} size={iconSize} className={hue.icon} />
    </span>
  )
}

// ── Level 1: every project ───────────────────────────────────────────────────

function ProjectOverview({ projects, onOpen }) {
  return (
    <div>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-foreground">Backlog categories</h2>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          How each project groups its backlog. Every project has a fixed <span className="text-foreground/80">Default</span>,
          where items land unless someone picks another category.
        </p>
      </div>
      <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
        {projects.map((p) => {
          const total = p.backlog_category_count ?? 1
          return (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => onOpen(p.id)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
              >
                <ProjectMark project={p} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-foreground">{p.name}</span>
                  <span className="text-[12px] text-muted-foreground">
                    {total <= 1 ? 'Only Default' : `Default + ${total - 1} more`}
                  </span>
                </span>
                <span className="whitespace-nowrap text-[13px] text-muted-foreground">
                  {total} {total === 1 ? 'category' : 'categories'}
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

// ── Level 2: one project's categories ────────────────────────────────────────

const NEW = 'new'

function ProjectCategories({ project, onBack, onChanged }) {
  const { toast } = useToast()
  const invalidate = useInvalidateBacklogCategories()
  const [categories, setCategories] = useState(null)
  const [editing, setEditing] = useState(null) // category id, NEW, or null
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(() => (
    backlogCategoriesApi.list(project.id)
      .then((res) => setCategories(res.data.categories))
      .catch((err) => {
        setCategories([])
        toast.error('Failed to load categories', err.response?.data?.detail)
      })
  ), [project.id, toast])

  useEffect(() => { load() }, [load])

  const changed = () => {
    invalidate(project.id)
    onChanged?.()
  }

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  if (categories === null) {
    return <div className="flex justify-center py-16"><div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-primary" /></div>
  }

  const defaultCategory = categories.find((c) => c.is_default)
  const others = categories.filter((c) => !c.is_default)
  const atLimit = categories.length >= CATEGORY_LIMIT
  const names = (exceptId) => categories.filter((c) => c.id !== exceptId).map((c) => c.name.toLowerCase())

  async function save(draft, id) {
    try {
      if (id === NEW) {
        const res = await backlogCategoriesApi.create(project.id, draft)
        setCategories((list) => [...list, { ...res.data, item_count: 0 }])
        toast({ title: `Added ${res.data.name}` })
      } else {
        const res = await backlogCategoriesApi.update(project.id, id, draft)
        setCategories((list) => list.map((c) => (c.id === id ? { ...c, ...res.data } : c)))
        toast({ title: `Saved ${res.data.name}` })
      }
      setEditing(null)
      changed()
      return null
    } catch (err) {
      const body = err.response?.data
      if (body?.code === 'category_name_taken') return { name: 'Already used in this project.' }
      toast.error("Couldn't save the category", body?.detail)
      return {}
    }
  }

  async function onDragEnd({ active, over }) {
    if (!over || active.id === over.id) return
    const ids = others.map((c) => c.id)
    const nextIds = arrayMove(ids, ids.indexOf(active.id), ids.indexOf(over.id))
    const snapshot = categories
    setCategories([defaultCategory, ...nextIds.map((id) => others.find((c) => c.id === id))])
    try {
      await backlogCategoriesApi.reorder(project.id, nextIds)
      changed()
    } catch (err) {
      setCategories(snapshot)
      toast.error("Couldn't save the new order", err.response?.data?.detail)
    }
  }

  async function doDelete() {
    const c = confirmDelete
    setDeleting(true)
    try {
      const res = await backlogCategoriesApi.remove(project.id, c.id)
      const moved = res.data.moved_count
      setCategories((list) => list
        .filter((x) => x.id !== c.id)
        .map((x) => (x.is_default ? { ...x, item_count: x.item_count + moved } : x)))
      toast({
        title: `Deleted ${c.name}`,
        body: moved ? `${moved} ${moved === 1 ? 'item' : 'items'} moved to Default.` : undefined,
      })
      setConfirmDelete(null)
      changed()
    } catch (err) {
      toast.error("Couldn't delete the category", err.response?.data?.detail)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="mb-3 inline-flex items-center gap-1 rounded text-[13px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Icon name="arrow-left" size={14} aria-hidden /> Backlog categories
      </button>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <ProjectMark project={project} size="h-10 w-10" />
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-base font-semibold text-foreground">{project.name}</h2>
          <p className="text-[12.5px] text-muted-foreground">
            <span className="tabular-nums">{categories.length}</span> of {CATEGORY_LIMIT} categories ·
            items land in Default unless another is picked
          </p>
        </div>
        <Tooltip content={atLimit ? `A project can have at most ${CATEGORY_LIMIT} categories.` : null}>
          <span>
            <Button onClick={() => setEditing(NEW)} disabled={atLimit || editing === NEW}>
              <Plus className="h-3.5 w-3.5" aria-hidden /> Add category
            </Button>
          </span>
        </Tooltip>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        {defaultCategory && <DefaultRow category={defaultCategory} />}
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={others.map((c) => c.id)} strategy={verticalListSortingStrategy}>
            <ul aria-label={`${project.name} categories`}>
              {others.map((c) => (
                <SortableCategoryRow
                  key={c.id}
                  category={c}
                  editing={editing === c.id}
                  dragDisabled={editing != null}
                  takenNames={names(c.id)}
                  onEdit={() => setEditing(c.id)}
                  onCancel={() => setEditing(null)}
                  onSave={(draft) => save(draft, c.id)}
                  onDelete={() => setConfirmDelete(c)}
                />
              ))}
            </ul>
          </SortableContext>
        </DndContext>
        {editing === NEW && (
          <div className="border-t border-border">
            <CategoryEditor
              initial={{ name: '', icon: 'sparkles', color: 'emerald' }}
              takenNames={names(null)}
              isNew
              onCancel={() => setEditing(null)}
              onSave={(draft) => save(draft, NEW)}
            />
          </div>
        )}
        {others.length === 0 && editing !== NEW && (
          <div className="border-t border-border px-6 py-8 text-center">
            <p className="text-sm font-medium text-foreground">Only Default so far</p>
            <p className="mx-auto mt-1 max-w-sm text-[12.5px] text-muted-foreground">
              Add categories like “Feature requests” or “Ideas” to group this project's backlog.
            </p>
            <Button className="mt-3" size="sm" variant="outline" onClick={() => setEditing(NEW)}>
              <Plus className="h-3.5 w-3.5" aria-hidden /> Add the first category
            </Button>
          </div>
        )}
      </div>
      {others.length > 1 && (
        <p className="mt-2 text-[11.5px] text-muted-foreground">
          Drag the handle to reorder — or focus it and press Space, then the arrow keys. The backlog's groups follow this order.
        </p>
      )}

      <DeleteDialog
        category={confirmDelete}
        deleting={deleting}
        onCancel={() => setConfirmDelete(null)}
        onConfirm={doDelete}
      />
    </div>
  )
}

// ── Rows ─────────────────────────────────────────────────────────────────────

function ItemCount({ n }) {
  return (
    <span className="text-[12px] tabular-nums text-muted-foreground">
      {n === 0 ? 'No items' : `${n} ${n === 1 ? 'item' : 'items'}`}
    </span>
  )
}

function DefaultRow({ category }) {
  return (
    <div className="flex items-center gap-3 border-b border-border bg-muted/30 px-3 py-2.5">
      <Tooltip content="Default is fixed — always first, never renamed, restyled or deleted.">
        <span className="flex h-7 w-5 items-center justify-center text-muted-foreground" tabIndex={0} aria-label="Default is fixed">
          <Lock className="h-3.5 w-3.5" aria-hidden />
        </span>
      </Tooltip>
      <CategoryChip category={category} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-foreground">{category.name}</span>
          <span className="rounded-full border border-border bg-background px-1.5 text-[10.5px] font-medium text-muted-foreground">
            Fixed
          </span>
        </div>
        <ItemCount n={category.item_count} />
      </div>
    </div>
  )
}

function SortableCategoryRow({
  category, editing, dragDisabled, takenNames, onEdit, onCancel, onSave, onDelete,
}) {
  const {
    attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging,
  } = useSortable({ id: category.id, disabled: dragDisabled })

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={cn(
        'border-b border-border bg-card last:border-b-0',
        isDragging && 'relative z-10 rounded-lg shadow-lg ring-1 ring-border',
      )}
    >
      {editing ? (
        <CategoryEditor initial={category} takenNames={takenNames} onCancel={onCancel} onSave={onSave} />
      ) : (
        <div className="group flex items-center gap-3 px-3 py-2.5">
          <button
            type="button"
            ref={setActivatorNodeRef}
            {...attributes}
            {...listeners}
            disabled={dragDisabled}
            aria-label={`Reorder ${category.name}`}
            className={cn(
              'flex h-7 w-5 items-center justify-center rounded-md text-muted-foreground',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              dragDisabled ? 'cursor-not-allowed opacity-40' : 'cursor-grab hover:text-foreground active:cursor-grabbing',
            )}
          >
            <GripVertical className="h-3.5 w-3.5" aria-hidden />
          </button>
          <CategoryChip category={category} />
          <div className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-foreground">{category.name}</span>
            <ItemCount n={category.item_count} />
          </div>
          <div className="flex items-center gap-1 opacity-70 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
            <Button size="icon-sm" variant="ghost" onClick={onEdit} aria-label={`Edit ${category.name}`}>
              <Pencil className="h-3.5 w-3.5" aria-hidden />
            </Button>
            <Button
              size="icon-sm"
              variant="ghost"
              onClick={onDelete}
              aria-label={`Delete ${category.name}`}
              className="hover:text-destructive"
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden />
            </Button>
          </div>
        </div>
      )}
    </li>
  )
}

// ── The in-place editor ──────────────────────────────────────────────────────

function CategoryEditor({ initial, takenNames, isNew = false, onCancel, onSave }) {
  const [name, setName] = useState(initial.name)
  const [icon, setIcon] = useState(initial.icon)
  const [color, setColor] = useState(initial.color)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const nameRef = useRef(null)

  useEffect(() => { nameRef.current?.focus() }, [])

  const trimmed = name.trim()
  const validate = useCallback(() => {
    if (!trimmed) return 'Give the category a name.'
    if (trimmed.length > CATEGORY_NAME_MAX) return `At most ${CATEGORY_NAME_MAX} characters.`
    if (takenNames.includes(trimmed.toLowerCase())) return 'Already used in this project.'
    return null
  }, [trimmed, takenNames])

  const preview = useMemo(() => ({ name: trimmed || 'Category name', icon, color }), [trimmed, icon, color])
  const unchanged = !isNew && trimmed === initial.name && icon === initial.icon && color === initial.color

  async function submit(e) {
    e?.preventDefault()
    const problem = validate()
    setError(problem)
    if (problem) {
      nameRef.current?.focus()
      return
    }
    setSaving(true)
    const errors = await onSave({ name: trimmed, icon, color })
    setSaving(false)
    if (errors?.name) {
      setError(errors.name)
      nameRef.current?.focus()
    }
  }

  return (
    <form
      onSubmit={submit}
      onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); onCancel() } }}
      className="space-y-4 bg-muted/20 px-4 py-4"
      aria-label={isNew ? 'New category' : `Edit ${initial.name}`}
    >
      <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-start">
        <div>
          <label htmlFor="category-name" className="mb-1.5 block text-xs font-medium text-muted-foreground">Name</label>
          <Input
            id="category-name"
            ref={nameRef}
            value={name}
            maxLength={CATEGORY_NAME_MAX}
            onChange={(e) => { setName(e.target.value); if (error) setError(null) }}
            onBlur={() => trimmed && setError(validate())}
            placeholder="e.g. Feature requests"
            error={!!error}
            aria-invalid={!!error}
            aria-describedby="category-name-hint"
          />
          <div id="category-name-hint" className="mt-1 flex justify-between text-[11px]">
            <span className={error ? 'text-destructive' : 'text-muted-foreground'}>{error ?? ' '}</span>
            <span className="tabular-nums text-muted-foreground">{trimmed.length}/{CATEGORY_NAME_MAX}</span>
          </div>
        </div>
        <div>
          <span className="mb-1.5 block text-xs font-medium text-muted-foreground">Preview</span>
          <div className="flex h-9 items-center gap-3 rounded-lg border border-border bg-card px-3">
            <span className="flex items-center gap-2 text-[12.5px] font-semibold text-foreground">
              <Icon name={icon} size={14} className={categoryColor(color).icon} aria-hidden />
              <span className="max-w-[140px] truncate">{preview.name}</span>
            </span>
            <span className="h-4 w-px bg-border" aria-hidden />
            <BacklogCategoryBadge category={preview} />
          </div>
        </div>
      </div>

      <fieldset>
        <legend className="mb-1.5 text-xs font-medium text-muted-foreground">Colour</legend>
        <div role="radiogroup" aria-label="Colour" className="flex flex-wrap gap-1.5">
          {CATEGORY_COLORS.map((hue) => {
            const selected = hue === color
            return (
              <button
                key={hue}
                type="button"
                role="radio"
                aria-checked={selected}
                aria-label={CATEGORY_COLOR[hue].label}
                title={CATEGORY_COLOR[hue].label}
                onClick={() => setColor(hue)}
                className={cn(
                  'flex h-7 w-7 items-center justify-center rounded-full transition-transform',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                  CATEGORY_COLOR[hue].swatch,
                  selected ? 'ring-2 ring-foreground ring-offset-2 ring-offset-background' : 'hover:scale-110 motion-reduce:hover:scale-100',
                )}
              >
                {selected && <Check className="h-3.5 w-3.5 text-white" strokeWidth={3} aria-hidden />}
              </button>
            )
          })}
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-1.5 text-xs font-medium text-muted-foreground">Icon</legend>
        <div role="radiogroup" aria-label="Icon" className="grid grid-cols-[repeat(auto-fill,minmax(2.25rem,1fr))] gap-1">
          {CATEGORY_ICONS.map((name) => {
            const selected = name === icon
            return (
              <button
                key={name}
                type="button"
                role="radio"
                aria-checked={selected}
                aria-label={name.replace(/-/g, ' ')}
                title={name.replace(/-/g, ' ')}
                onClick={() => setIcon(name)}
                className={cn(
                  'flex h-9 items-center justify-center rounded-md border transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  selected
                    ? 'border-foreground bg-foreground text-background dark:border-background dark:bg-background dark:text-foreground'
                    : 'border-transparent text-muted-foreground hover:border-border hover:bg-card hover:text-foreground',
                )}
              >
                <Icon name={name} size={16} aria-hidden className={selected ? undefined : categoryColor(color).icon} />
              </button>
            )
          })}
        </div>
      </fieldset>

      <div className="flex items-center justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button type="submit" size="sm" loading={saving} disabled={unchanged}>
          {isNew ? 'Add category' : 'Save'}
        </Button>
      </div>
    </form>
  )
}

// ── Delete confirmation ──────────────────────────────────────────────────────

function DeleteDialog({ category, deleting, onCancel, onConfirm }) {
  const n = category?.item_count ?? 0
  return (
    <Dialog open={!!category} onClose={onCancel} title="Delete category" size="sm">
      {category && (
        <div className="space-y-4 p-5">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
              <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" aria-hidden />
            </div>
            <div className="flex-1">
              <p className="mb-1 text-sm font-medium">Delete “{category.name}”?</p>
              <p className="text-xs text-muted-foreground">
                {n > 0
                  ? <>{n} {n === 1 ? 'item moves' : 'items move'} to <strong className="font-medium text-foreground">Default</strong>. Each item's timeline records the move; nobody is notified.</>
                  : 'No items use it.'}
              </p>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={onCancel} disabled={deleting}>Cancel</Button>
            <Button variant="destructive" onClick={onConfirm} loading={deleting}>
              {n > 0 ? `Delete and move ${n}` : 'Delete category'}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  )
}
