import React, { useState } from 'react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Dialog } from '../ui/Dialog'

const PROJECT_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#10b981', '#3b82f6',
  '#6366f1', '#8b5cf6', '#ec4899', '#14b8a6', '#6b7280',
]

export function EditProjectModal({ open, onClose, project, onSave }) {
  const [form, setForm] = useState({ name: '', slug: '', color: '#6366f1', desc: '' })

  React.useEffect(() => {
    if (project) {
      setForm({ name: project.name, slug: project.slug, color: project.color, desc: project.desc ?? '' })
    }
  }, [project])

  function handleSave() {
    if (!form.name.trim() || !form.slug.trim()) return
    onSave?.(form)
  }

  function handleNameChange(value) {
    setForm((f) => ({ ...f, name: value, slug: value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '') }))
  }

  return (
    <Dialog open={open} onClose={onClose} title="Edit project" size="sm">
      <div className="p-5 space-y-4">
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Project name</label>
          <Input
            value={form.name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="e.g. Mobile App"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Slug</label>
          <Input
            value={form.slug}
            onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
            placeholder="e.g. mobile-app"
            className="font-mono text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Color</label>
          <div className="flex items-center gap-3 flex-wrap">
            {PROJECT_COLORS.map((color) => (
              <button
                key={color}
                onClick={() => setForm((f) => ({ ...f, color }))}
                className={cn(
                  'h-8 w-8 rounded-full transition-transform hover:scale-110',
                  form.color === color && 'ring-2 ring-offset-2 ring-offset-background ring-foreground'
                )}
                style={{ backgroundColor: color }}
                title={color}
              />
            ))}
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Description</label>
          <Input
            value={form.desc}
            onChange={(e) => setForm((f) => ({ ...f, desc: e.target.value }))}
            placeholder="e.g. iOS + Android consumer app"
          />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave}>Save changes</Button>
        </div>
      </div>
    </Dialog>
  )
}
