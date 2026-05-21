import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'

export function LabelChip({ label, className, removable, onRemove }) {
  if (!label) return null
  const color = label.color ?? '#6366f1'
  const name = label.name ?? label

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
      {name}
      {removable && (
        <button onClick={onRemove} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-100">
          <Icon name="x" size={10} />
        </button>
      )}
    </span>
  )
}
