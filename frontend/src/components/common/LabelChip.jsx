import React from 'react'
import { cn } from '../../lib/cn'

export function LabelChip({ label, className }) {
  if (!label) return null
  const color = label.color ?? '#6366f1'
  const name = label.name ?? label

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        'bg-card text-foreground',
        className
      )}
      style={{ borderColor: color + '60' }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full shrink-0"
        style={{ backgroundColor: color }}
      />
      {name}
    </span>
  )
}
