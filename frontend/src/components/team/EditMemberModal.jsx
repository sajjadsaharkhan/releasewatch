import React, { useState, useEffect, useRef } from 'react'
import { RefreshCw, Eye, EyeOff, Check, Circle, Camera } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Dialog } from '../ui/Dialog'
import { Dropdown, DropdownItem } from '../ui/Dropdown'
import { Avatar } from '../ui/Avatar'
import { ImageCropper } from '../ui/ImageCropper'
import { ROLE } from '../../lib/constants'

export function EditMemberModal({ open, onClose, member, onSave, onAvatarChange }) {
  const [form, setForm] = useState({ name: '', username: '', password: '', role: 'qa' })
  const [showPassword, setShowPassword] = useState(false)
  const [cropperImage, setCropperImage] = useState(null)
  const [avatarPreview, setAvatarPreview] = useState(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    if (member) {
      setForm({
        name: member.name,
        username: member.username,
        password: '',
        role: member.role
      })
      setAvatarPreview(member.avatar_url || null)
    }
  }, [member])

  function generatePassword() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'
    let password = ''
    for (let i = 0; i < 16; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    setForm((f) => ({ ...f, password }))
  }

  function handleAvatarClick() {
    fileInputRef.current?.click()
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (file && file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = (event) => {
        setCropperImage(event.target.result)
      }
      reader.readAsDataURL(file)
    }
    e.target.value = ''
  }

  function handleCropSave(blob) {
    const url = URL.createObjectURL(blob)
    setAvatarPreview(url)
    setCropperImage(null)
    onAvatarChange?.(url)
  }

  function handleCropCancel() {
    setCropperImage(null)
  }

  function handleSave() {
    if (!form.name || !form.username) return
    onSave?.(form)
  }

  // Create a user object for Avatar that uses the preview when available
  const avatarUser = avatarPreview ? { ...member, avatar_url: avatarPreview } : member

  return (
    <>
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        className="hidden"
      />
      {cropperImage && (
        <ImageCropper
          image={cropperImage}
          onSave={handleCropSave}
          onCancel={handleCropCancel}
        />
      )}
      <Dialog open={open} onClose={onClose} title="Edit member" size="sm">
        <div className="p-5 space-y-4">
          <div className="flex items-center gap-4 pb-4 border-b border-border">
            <div className="relative">
              <Avatar user={avatarUser} size={56} />
              <button
                type="button"
                onClick={handleAvatarClick}
                className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm hover:bg-primary/90"
                title="Change photo"
              >
                <Camera className="h-3 w-3" />
              </button>
            </div>
            <div>
              <p className="text-sm font-medium">{form.name}</p>
              <p className="text-xs text-muted-foreground">@{form.username}</p>
            </div>
          </div>
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
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">New password (leave blank to keep)</label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="New password"
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
          <Button onClick={handleSave}>Save changes</Button>
        </div>
      </div>
    </Dialog>
    </>
  )
}