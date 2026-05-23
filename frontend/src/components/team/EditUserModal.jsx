import React, { useState, useEffect } from 'react'
import { User as UserIcon, AtSign, Briefcase, FileText, Shield, RefreshCw, Eye, EyeOff, Key } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Textarea } from '../ui/Textarea'
import { Dialog } from '../ui/Dialog'
import { ColorSelectDropdown } from '../ui/ColorSelectDropdown'
import { ROLE } from '../../data/mockData'
import { teamApi, userApi } from '../../lib/api'
import { useToast } from '../ui/Toast'
import { Avatar } from '../ui/Avatar'
import { RoleBadge } from '../ui/Badge'

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

export function EditUserModal({ open, onClose, user, onUpdated, currentUser, canEditRole }) {
  const [form, setForm] = useState({
    name: '',
    username: '',
    title: '',
    bio: '',
    role: 'qa',
    avatar_color: '#6366f1',
    password: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hasChanges, setHasChanges] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    if (user) {
      setForm({
        name: user.name || '',
        username: user.username || '',
        title: user.title || '',
        bio: user.bio || '',
        role: user.role || 'qa',
        avatar_color: user.avatar_color || '#6366f1',
        password: '',
      })
      setHasChanges(false)
    }
  }, [user])

  function handleChange(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
    setHasChanges(true)
  }

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
    setHasChanges(true)
  }

  async function handleSave() {
    if (!hasChanges) {
      onClose()
      return
    }

    setLoading(true)
    setError(null)

    try {
      const isEditingSelf = currentUser?.id === user?.id
      const updateData = {
        name: form.name !== user.name ? form.name : undefined,
        username: form.username !== user.username ? form.username : undefined,
        title: form.title !== user.title ? form.title : undefined,
        bio: form.bio !== user.bio ? form.bio : undefined,
        avatar_color: form.avatar_color !== user.avatar_color ? form.avatar_color : undefined,
      }

      // Only admins can change role via profile update
      if (form.role !== user.role && canEditRole) {
        updateData.role = form.role
      }

      // Handle password change
      if (form.password && isEditingSelf) {
        updateData.password = form.password
      }

      // Remove undefined values
      Object.keys(updateData).forEach(key => updateData[key] === undefined && delete updateData[key])

      if (Object.keys(updateData).length === 0) {
        setLoading(false)
        return
      }

      if (isEditingSelf) {
        // Use /me/profile endpoint for own profile
        await userApi.updateProfile(updateData)
      } else {
        // Use /team/{user_id} endpoint for other users
        if (!canEditRole && Object.keys(updateData).length === 0) {
          setError('You do not have permission to make these changes')
          setLoading(false)
          return
        }
        await teamApi.update(user.id, updateData)
      }

      toast({
        title: isEditingSelf ? 'Profile updated' : 'User updated',
        body: `${form.name}'s information has been updated`,
      })

      onUpdated?.({ ...user, ...form })
      onClose()
    } catch (err) {
      const message = err.response?.data?.detail || 'Failed to update profile'
      setError(message)
      toast({
        title: 'Update failed',
        body: message,
      })
    } finally {
      setLoading(false)
    }
  }

  const isEditingSelf = currentUser?.id === user?.id
  const previewUser = { ...user, avatar_color: form.avatar_color }

  return (
    <Dialog open={open} onClose={onClose} title={isEditingSelf ? 'Edit profile' : 'Edit team member'} size="md">
      <div className="p-5 space-y-4 max-h-[80vh] overflow-y-auto">
        {error && (
          <div className="rounded-lg bg-red-100 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-3 py-2">
            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
          </div>
        )}

        <div className="flex items-center gap-4 pb-4 border-b border-border">
          <Avatar user={previewUser} size={56} />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{form.name || 'Unnamed'}</p>
            <div className="flex items-center gap-2">
              <p className="text-xs text-muted-foreground truncate">@{form.username}</p>
              <RoleBadge role={form.role} size="sm" />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2 sm:col-span-1">
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Full name</label>
            <div className="relative">
              <UserIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                value={form.name}
                onChange={(e) => handleChange('name', e.target.value)}
                placeholder="Full name"
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
                onChange={(e) => handleChange('username', e.target.value.toLowerCase().replace(/[^a-z0-9_.-]/g, ''))}
                placeholder="Username"
                className="pl-9 font-mono"
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">Lowercase letters, numbers, dots, hyphens, underscores</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground mb-1.5">
              <Shield className="h-3.5 w-3.5" />
              Role
            </label>
            <ColorSelectDropdown
              items={Object.entries(ROLE).map(([value, { label }]) => ({ value, label }))}
              value={form.role}
              onChange={(role) => handleChange('role', role)}
              placeholder="Select role"
              disabled={!canEditRole}
            />
            {!canEditRole && (
              <p className="text-xs text-muted-foreground mt-1">Only admins can change roles</p>
            )}
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Avatar color</label>
            <ColorSelectDropdown
              items={AVATAR_COLORS}
              value={form.avatar_color}
              onChange={(avatar_color) => handleChange('avatar_color', avatar_color)}
              placeholder="Select color"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Title</label>
          <div className="relative">
            <Briefcase className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={form.title}
              onChange={(e) => handleChange('title', e.target.value)}
              placeholder="e.g. Senior QA Engineer"
              className="pl-9"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Bio</label>
          <div className="relative">
            <FileText className="absolute left-2.5 top-3 h-4 w-4 text-muted-foreground" />
            <Textarea
              value={form.bio}
              onChange={(e) => handleChange('bio', e.target.value)}
              placeholder="Brief biography..."
              rows={3}
              className="pl-9 resize-none"
            />
          </div>
        </div>

        {isEditingSelf && (
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              New password <span className="text-zinc-500">(leave blank to keep current)</span>
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Key className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  value={form.password}
                  onChange={(e) => handleChange('password', e.target.value)}
                  placeholder="Generate a new password"
                  type={showPassword ? 'text' : 'password'}
                  className="pl-9 pr-20 font-mono text-sm"
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
            {form.password && (
              <p className="text-xs text-muted-foreground mt-1">
                Make sure to save your new password securely
              </p>
            )}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button onClick={handleSave} loading={loading} disabled={!hasChanges}>
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              'Save changes'
            )}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
