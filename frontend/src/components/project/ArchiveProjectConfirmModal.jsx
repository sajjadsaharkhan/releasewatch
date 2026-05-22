import React from 'react'
import { cn } from '../../lib/cn'
import { Archive, RotateCcw } from 'lucide-react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'

export function ArchiveProjectConfirmModal({ open, onClose, onConfirm, projectName, type = 'archive' }) {
  const isArchive = type === 'archive'

  return (
    <Dialog open={open} onClose={onClose} title={isArchive ? 'Archive project' : 'Restore project'} size="sm">
      <div className="p-5 space-y-4">
        <div className="flex items-start gap-3">
          <div className={cn(
            'flex h-10 w-10 items-center justify-center rounded-full shrink-0',
            isArchive ? 'bg-amber-100 dark:bg-amber-900/30' : 'bg-green-100 dark:bg-green-900/30'
          )}>
            {isArchive ? (
              <Archive className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            ) : (
              <RotateCcw className="h-5 w-5 text-green-600 dark:text-green-400" />
            )}
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium mb-1">
              {isArchive
                ? `Archive "${projectName}"?`
                : `Restore "${projectName}"?`}
            </p>
            <p className="text-xs text-muted-foreground">
              {isArchive
                ? 'This project will be hidden from the project switcher. You can restore it later from Settings.'
                : 'This project will become visible in the project switcher again.'}
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={onConfirm} variant={isArchive ? 'default' : 'default'}>
            {isArchive ? 'Archive' : 'Restore'}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
