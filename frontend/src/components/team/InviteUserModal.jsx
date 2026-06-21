import React, { useState, useEffect } from 'react'
import { User as UserIcon, AtSign, RefreshCw, Eye, EyeOff } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Dialog } from '../ui/Dialog'
import { ColorSelectDropdown } from '../ui/ColorSelectDropdown'
import { ROLE } from '../../lib/constants'
import { teamApi } from '../../lib/api'
import { useToast } from '../ui/Toast'

const AVATAR_COLORS = [
  { value: '#6366f1', label: 'Indigo', color: '#6366f1' },
  { value: '#f59e0b', label: 'Amber', color: '#f59e0b' },
  { value: '#10b981', label: 'Emerald', color: '#10b981' },
  { value: '#ec4899', label: 'Pink', color: '#ec4899' },
  { value: '#3b82f6', label: 'Blue', color: '#3b82f6' },
  { value: '#8b5cf6', label: 'Violet', color: '#8b5cf6' },
  { value: '#ef4444', label: 'Red', color: '#ef4444' },
  { value: '#14b8a6', label: 'Teal', color: '#14b8a6' },
]

export function InviteUserModal({ open, onClose, onInvited }) {
  const [form, setForm] = useState({
    name: '',
    username: '',
    password: '',
    role: 'qa',
    avatar_color: '#6366f1',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const { toast } = useToast()

  // Generate password when modal opens
  useEffect(() => {
    if (open) {
      setForm((prev) => ({ ...prev, password: generateStrongPassword() }))
    }
  }, [open])

  function generateStrongPassword() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'
    let password = ''
    for (let i = 0; i < 16; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    return password
  }

  function handleRegeneratePassword() {
    setForm((f) => ({ ...f, password: generateStrongPassword() }))
  }

  async function handleInvite() {
    const { name, username, password, role, avatar_color } = form

    if (!name || !username || !password) {
      setError('Please fill in all required fields')
      return
    }

    const usernameRegex = /^[a-z0-9_.-]+$/
    if (!usernameRegex.test(username)) {
      setError('Username can only contain lowercase letters, numbers, dots, hyphens, and underscores')
      return
    }

    if (password.length < 12) {
      setError('Password must be at least 12 characters long')
      return
    }

    setLoading(true)
    setError(null)

    try {
      await teamApi.invite({
        name,
        username,
        role,
        avatar_color,
        temporary_password: password,
      })

      toast({
        title: 'User created',
        body: `${name} has been added to the team`,
      })

      setForm({ name: '', username: '', password: '', role: 'qa', avatar_color: '#6366f1' })
      onInvited?.()
      onClose()
    } catch (err) {
      const message = err.response?.data?.detail || 'Failed to create user'
      setError(message)
      toast({
        title: 'Failed',
        body: message,
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Invite team member" size="sm">
      <div className="p-5 space-y-4">
        {error && (
          <div className="rounded-lg bg-red-100 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-3 py-2">
            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Full name</label>
          <div className="relative">
            <UserIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Jane Doe"
              className="pl-9"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Username</label>
          <div className="relative">
            <AtSign className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={form.username}
              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value.toLowerCase().replace(/[^a-z0-9_.-]/g, '') }))}
              placeholder="janedoe"
              className="pl-9 font-mono"
            />
          </div>
          <p className="text-xs text-muted-foreground mt-1">Only lowercase letters, numbers, dots, hyphens, and underscores</p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Role</label>
            <ColorSelectDropdown
              items={Object.entries(ROLE).map(([value, { label }]) => ({ value, label }))}
              value={form.role}
              onChange={(role) => setForm((f) => ({ ...f, role }))}
              placeholder="Select role"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Avatar color</label>
            <ColorSelectDropdown
              items={AVATAR_COLORS}
              value={form.avatar_color}
              onChange={(avatar_color) => setForm((f) => ({ ...f, avatar_color }))}
              placeholder="Select color"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Temporary password</label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="Generate a password"
                type={showPassword ? 'text' : 'password'}
                className="pr-20 font-mono text-sm"
              />
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-muted-foreground hover:text-foreground p-1"
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
                <button
                  type="button"
                  onClick={handleRegeneratePassword}
                  className="text-muted-foreground hover:text-foreground p-1"
                  title="Generate new password"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Share this password securely with the user. They can change it after logging in.
          </p>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button onClick={handleInvite} loading={loading}>
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Sending...
              </>
            ) : (
              'Send Invitation'
            )}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
