import React from 'react'
import { cn } from '../../lib/cn'
import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'

export function ConfirmModal({ open, onClose, onConfirm, type = 'deactivate' }) {
  const isDeactivate = type === 'deactivate'

  return (
    <Dialog open={open} onClose={onClose} title={isDeactivate ? 'Deactivate member' : 'Activate member'} size="sm">
      <div className="p-5 space-y-4">
        <div className="flex items-start gap-3">
          <div className={cn(
            'flex h-10 w-10 items-center justify-center rounded-full shrink-0',
            isDeactivate ? 'bg-red-100 dark:bg-red-900/30' : 'bg-green-100 dark:bg-green-900/30'
          )}>
            {isDeactivate ? (
              <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
            ) : (
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
            )}
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium mb-1">
              {isDeactivate
                ? 'Are you sure you want to deactivate this member?'
                : 'Are you sure you want to activate this member?'}
            </p>
            <p className="text-xs text-muted-foreground">
              {isDeactivate
                ? 'They will no longer be able to access the workspace and their login credentials will be disabled.'
                : 'They will regain access to the workspace with their existing credentials.'}
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={onConfirm} variant={isDeactivate ? 'destructive' : 'default'}>
            {isDeactivate ? 'Deactivate' : 'Activate'}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}