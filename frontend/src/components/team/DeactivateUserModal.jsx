import React, { useState, useEffect } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { teamApi } from '../../lib/api'
import { useToast } from '../ui/Toast'
import { Avatar } from '../ui/Avatar'
import { RoleBadge } from '../ui/Badge'

export function DeactivateUserModal({ open, onClose, user, onDeactivated, currentUser }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  // Projects this user is triage lead of — they lose their lead (AC-23).
  const [affectedProjects, setAffectedProjects] = useState([])
  const { toast } = useToast()

  const isDeactivatingSelf = currentUser?.id === user?.id

  useEffect(() => {
    if (!open) return
    setError(null)
    setAffectedProjects([])
    if (!user || isDeactivatingSelf) return
    let cancelled = false
    teamApi.deactivationImpact(user.id)
      .then((res) => { if (!cancelled) setAffectedProjects(res.data?.affected_projects || []) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [open, user, isDeactivatingSelf])

  async function handleDeactivate() {
    if (isDeactivatingSelf) {
      setError('You cannot deactivate your own account')
      return
    }

    setLoading(true)
    setError(null)

    try {
      await teamApi.deactivate(user.id)

      toast({
        title: 'User deactivated',
        body: `${user.name} has been deactivated`,
      })

      onDeactivated?.(user.id)
      onClose()
    } catch (err) {
      const message = err.response?.data?.detail || 'Failed to deactivate user'
      setError(message)
      toast({
        title: 'Deactivation failed',
        body: message,
      })
    } finally {
      setLoading(false)
    }
  }

  if (!user) return null

  return (
    <Dialog open={open} onClose={onClose} title="Deactivate team member" size="sm">
      <div className="p-5 space-y-4">
        {isDeactivatingSelf ? (
          <div className="rounded-lg bg-amber-100 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 px-3 py-2">
            <p className="text-sm text-amber-700 dark:text-amber-400">You cannot deactivate your own account. Ask another admin to do this for you.</p>
          </div>
        ) : (
          <>
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30 shrink-0">
                <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium mb-1">Deactivate {user.name}?</p>
                <p className="text-xs text-muted-foreground">
                  They will no longer be able to access the workspace and their login credentials will be disabled. Their past activity and contributions will be preserved.
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

            {affectedProjects.length > 0 && (
              <div role="status" className="rounded-lg bg-amber-100 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 px-3 py-2 space-y-1">
                <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
                  {user.name} is the triage lead of {affectedProjects.length === 1 ? 'this project' : `${affectedProjects.length} projects`}:
                </p>
                <ul className="text-sm text-amber-800 dark:text-amber-300 list-disc pl-5">
                  {affectedProjects.map((p) => <li key={p.id}>{p.name}</li>)}
                </ul>
                <p className="text-xs text-amber-700 dark:text-amber-400">
                  Until you choose a new lead, triage notifications for {affectedProjects.length === 1 ? 'it' : 'them'} go to every admin.
                </p>
              </div>
            )}

            {error && (
              <div className="rounded-lg bg-red-100 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-3 py-2">
                <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
              </div>
            )}
          </>
        )}

        {!isDeactivatingSelf && (
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={onClose} disabled={loading}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={handleDeactivate}
              loading={loading}
            >
              {loading ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Deactivating…
                </>
              ) : (
                'Deactivate'
              )}
            </Button>
          </div>
        )}
      </div>
    </Dialog>
  )
}
