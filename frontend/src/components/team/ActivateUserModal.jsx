import React, { useState, useEffect } from 'react'
import { CheckCircle, RefreshCw } from 'lucide-react'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { teamApi } from '../../lib/api'
import { useToast } from '../ui/Toast'
import { Avatar } from '../ui/Avatar'
import { RoleBadge } from '../ui/Badge'

export function ActivateUserModal({ open, onClose, user, onActivated, currentUser }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const { toast } = useToast()

  useEffect(() => {
    if (open) {
      setError(null)
    }
  }, [open])

  async function handleActivate() {
    setLoading(true)
    setError(null)

    try {
      await teamApi.activate(user.id)

      toast({
        title: 'User activated',
        body: `${user.name} has been reactivated`,
      })

      onActivated?.(user.id)
      onClose()
    } catch (err) {
      const message = err.response?.data?.detail || 'Failed to activate user'
      setError(message)
      toast({
        title: 'Activation failed',
        body: message,
      })
    } finally {
      setLoading(false)
    }
  }

  if (!user) return null

  return (
    <Dialog open={open} onClose={onClose} title="Reactivate team member" size="sm">
      <div className="p-5 space-y-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30 shrink-0">
            <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium mb-1">Reactivate {user.name}?</p>
            <p className="text-xs text-muted-foreground">
              They will regain access to the workspace and can log in with their existing credentials.
            </p>
          </div>
        </div>

        <div className="rounded-lg bg-zinc-100 dark:bg-zinc-800/50 border border-border p-3 flex items-center gap-3">
          <Avatar user={user} size={40} />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user.name}</p>
            <div className="flex items-center gap-2">
              <p className="text-xs text-muted-foreground truncate">@{user.username}</p>
              <RoleBadge role={user.role} size="sm" />
            </div>
          </div>
        </div>

        {error && (
          <div className="rounded-lg bg-red-100 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-3 py-2">
            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button
            onClick={handleActivate}
            loading={loading}
          >
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Activating...
              </>
            ) : (
              'Reactivate'
            )}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
