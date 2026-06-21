import React, { useState } from 'react'
import { RefreshCw, Eye, EyeOff, Check, Circle } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Dialog } from '../ui/Dialog'
import { Dropdown, DropdownItem } from '../ui/Dropdown'
import { ROLE } from '../../lib/constants'

export function CreateMemberModal({ open, onClose, onCreate }) {
  const [form, setForm] = useState({ name: '', username: '', password: '', role: 'qa' })
  const [showPassword, setShowPassword] = useState(false)

  function generatePassword() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'
    let password = ''
    for (let i = 0; i < 16; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    setForm((f) => ({ ...f, password }))
  }

  function handleCreate() {
    if (!form.name || !form.username || !form.password) return
    onCreate?.(form)
    setForm({ name: '', username: '', password: '', role: 'qa' })
  }

  return (
    <Dialog open={open} onClose={onClose} title="Add team member" size="sm">
      <div className="p-5 space-y-4">
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Full name</label>
          <Input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Full name"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Username</label>
          <Input
            value={form.username}
            onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
            placeholder="Username"
            className="font-mono"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Password</label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="Password"
                type={showPassword ? 'text' : 'password'}
                className="pr-9"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <Button variant="outline" size="sm" onClick={generatePassword} title="Generate strong password">
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Role</label>
          <Dropdown
            trigger={
              <button
                className={cn(
                  'flex items-center justify-between gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-sm font-medium w-full',
                  'hover:bg-accent transition-colors'
                )}
              >
                <span>{ROLE[form.role]?.label ?? form.role}</span>
              </button>
            }
          >
            {Object.entries(ROLE).map(([k, v]) => (
              <DropdownItem key={k} onClick={() => setForm((f) => ({ ...f, role: k }))}>
                <span className="flex items-center gap-2">
                  {k === form.role ? (
                    <Check className="h-4 w-4 shrink-0" />
                  ) : (
                    <Circle className="h-4 w-4 shrink-0 opacity-70" />
                  )}
                  <span>{v.label}</span>
                </span>
              </DropdownItem>
            ))}
          </Dropdown>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleCreate}>Create</Button>
        </div>
      </div>
    </Dialog>
  )
}