import React, { useState, useEffect } from 'react'
import { Palette } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Dialog } from '../ui/Dialog'
import { Select, SelectItem } from '../ui/Select'
import { teamApi } from '../../lib/api'

const PROJECT_COLORS = [
  '#ef4444', '#dc2626', '#f97316', '#ea580c', '#f59e0b',
  '#10b981', '#059669', '#14b8a6', '#0891b2', '#3b82f6',
  '#2563eb', '#6366f1', '#4f46e5', '#8b5cf6', '#a855f7',
  '#ec4899', '#db2777', '#f43f5e', '#84cc16', '#6b7280',
]

export function CreateProjectModal({ open, onClose, onCreate }) {
  const [form, setForm] = useState({ name: '', slug: '', color: '#6366f1', desc: '', triageLeadId: '' })
  const [teamMembers, setTeamMembers] = useState([])

  useEffect(() => {
    if (!open) return
    teamApi.list()
      .then((res) => setTeamMembers(res.data || []))
      .catch(() => setTeamMembers([]))
  }, [open])

  function handleCreate() {
    if (!form.name.trim() || !form.slug.trim()) return
    onCreate?.({
      name: form.name,
      slug: form.slug,
      color: form.color,
      desc: form.desc,
      triage_lead_id: form.triageLeadId || null,
    })
    setForm({ name: '', slug: '', color: '#6366f1', desc: '', triageLeadId: '' })
  }

  function handleNameChange(value) {
    setForm((f) => ({ ...f, name: value, slug: value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '') }))
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create new project" size="sm">
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
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Triage Lead</label>
          <Select
            value={form.triageLeadId}
            onChange={(val) => setForm((f) => ({ ...f, triageLeadId: val }))}
            placeholder="Assign a triage lead (optional)"
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
          <Button onClick={handleCreate}>Create project</Button>
        </div>
      </div>
    </Dialog>
  )
}
