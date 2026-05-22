import React from 'react'
import { cn } from '../../lib/cn'
import { AlertTriangle } from 'lucide-react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'

export function DeleteLabelModal({ open, onClose, onConfirm, labelName }) {
  return (
    <Dialog open={open} onClose={onClose} title="Delete label" size="sm">
      <div className="p-5 space-y-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full shrink-0 bg-red-100 dark:bg-red-900/30">
            <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium mb-1">
              Are you sure you want to delete {labelName ? `"${labelName}"` : 'this label'}?
            </p>
            <p className="text-xs text-muted-foreground">
              This will remove the label from all issues. This action cannot be undone.
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={onConfirm} variant="destructive">
            Delete
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
