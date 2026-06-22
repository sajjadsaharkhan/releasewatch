import React, { useState } from 'react'
import { Trash2, AlertTriangle } from 'lucide-react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { releasesApi } from '../../lib/api'
import { useToast } from '../../hooks/useToast'

export function DeleteReleaseModal({ open, onClose, release, onDeleted }) {
  const { toast } = useToast()
  const [loading, setLoading] = useState(false)

  async function handleDelete() {
    setLoading(true)
    try {
      await releasesApi.delete(release.id)
      toast({ title: `Release ${release.version} deleted`, tone: 'default' })
      onDeleted?.()
      onClose()
    } catch (err) {
      console.error('Failed to delete release:', err)
      toast({ title: 'Failed to delete release', tone: 'red' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} size="sm" title="Delete Release">
      <div className="p-6 space-y-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
            <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
          </div>
          <div>
            <p className="text-sm font-medium">
              Delete release <span className="font-mono font-bold">{release?.version}</span>?
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              This release will be removed from all views. This action cannot be undone.
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            size="sm"
            className="bg-red-600 hover:bg-red-700 text-white border-red-600 hover:border-red-700"
            onClick={handleDelete}
            disabled={loading}
          >
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />
            {loading ? 'Deleting…' : 'Delete Release'}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
