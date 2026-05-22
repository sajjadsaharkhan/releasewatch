import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'

const toneMap = {
  default: { icon: 'bg-muted text-muted-foreground', delta: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400' },
  blue: { icon: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400', delta: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  green: { icon: 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400', delta: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  amber: { icon: 'bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400', delta: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
  red: { icon: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400', delta: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  purple: { icon: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400', delta: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
}

export function MetricCard({ label, value, icon, delta, tone = 'default', description, className }) {
  const colors = toneMap[tone] ?? toneMap.default

  return (
    <div className={cn('rounded-xl border border-border bg-card p-5 flex flex-col gap-3 min-h-[160px]', className)}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
        {icon && (
          <div className={cn('flex h-8 w-8 items-center justify-center rounded-lg', colors.icon)}>
            <Icon name={icon} size={16} />
          </div>
        )}
      </div>
      <div className="flex items-end justify-between gap-2">
        <p className="text-3xl font-bold tracking-tight">{value ?? '—'}</p>
        {delta && (
          <span className={cn('mb-1 rounded-full px-2 py-0.5 text-xs font-medium', colors.delta)}>
            {delta}
          </span>
        )}
      </div>
      {description && (
        <p className="text-xs text-muted-foreground line-clamp-2">{description}</p>
      )}
    </div>
  )
}
