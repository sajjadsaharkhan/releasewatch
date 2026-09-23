import React, { useState, useEffect } from 'react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Dialog } from '../ui/Dialog'
import { Select, SelectItem } from '../ui/Select'
import { teamApi } from '../../lib/api'
import { PROJECT_KIND } from '../../lib/constants'

const PROJECT_COLORS = [
  '#ef4444', '#dc2626', '#f97316', '#ea580c', '#f59e0b',
  '#10b981', '#059669', '#14b8a6', '#0891b2', '#3b82f6',
  '#2563eb', '#6366f1', '#4f46e5', '#8b5cf6', '#a855f7',
  '#ec4899', '#db2777', '#f43f5e', '#84cc16', '#6b7280',
]

export function EditProjectModal({ open, onClose, project, onSave }) {
  const [form, setForm] = useState({ name: '', slug: '', color: '#6366f1', kind: 'product', desc: '', triageLeadId: '' })
  const [teamMembers, setTeamMembers] = useState([])

  useEffect(() => {
    if (project) {
      setForm({
        name: project.name,
        slug: project.slug,
        color: project.color,
        kind: project.kind ?? 'product',
        desc: project.desc ?? '',
        triageLeadId: project.triage_lead_id ?? project.triageLeadId ?? '',
      })
    }
  }, [project])

  useEffect(() => {
    if (!open) return
    // Triage lead must be an active tech-role user (BR-15) — the assignable list.
    teamApi.listAssignable()
      .then((res) => setTeamMembers(res.data || []))
      .catch(() => setTeamMembers([]))
  }, [open])

  // A deactivated (or Support) lead isn't in the list — the admin must pick a new one (AC-23).
  const leadIsValid = teamMembers.some((m) => String(m.id) === String(form.triageLeadId))
  const canSave = form.name.trim() && form.slug.trim() && leadIsValid

  function handleSave() {
    if (!canSave) return
    onSave?.({
      name: form.name,
      slug: form.slug,
      color: form.color,
      kind: form.kind,
      desc: form.desc,
      triage_lead_id: form.triageLeadId,
    })
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
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Kind</label>
          <Select
            value={form.kind}
            onChange={(val) => setForm((f) => ({ ...f, kind: val }))}
          >
            {Object.entries(PROJECT_KIND).map(([value, token]) => (
              <SelectItem key={value} value={value}>{token.label}</SelectItem>
            ))}
          </Select>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Only Product projects accept releases.
          </p>
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
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Triage lead</label>
          {teamMembers.length > 0 && !leadIsValid && (
            <p className="mb-1.5 text-xs text-amber-700 dark:text-amber-400">
              This project needs a triage lead. Triage notifications go to admins until you choose one.
            </p>
          )}
          <Select
            value={leadIsValid ? form.triageLeadId : ''}
            onChange={(val) => setForm((f) => ({ ...f, triageLeadId: val }))}
            placeholder="Choose a triage lead"
          >
            {teamMembers.map((member) => (
              <SelectItem key={member.id} value={member.id}>
                <div className="flex items-center gap-2">
                  <span
                    className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium text-white shrink-0"
                    style={{ backgroundColor: member.avatar_color || '#6b7280' }}
                  >
                    {(member.name || member.username || '?')[0].toUpperCase()}
                  </span>
                  <span>{member.name || member.username}</span>
                  {member.title && (
                    <span className="text-muted-foreground text-xs">· {member.title}</span>
                  )}
                </div>
              </SelectItem>
            ))}
          </Select>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={!canSave}>Save changes</Button>
        </div>
      </div>
    </Dialog>
  )
}
