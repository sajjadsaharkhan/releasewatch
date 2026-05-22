import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'

const TONE_STYLES = {
  blue: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
  green: 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400',
  amber: 'bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400',
  red: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
  purple: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
}

export function MetricSummaryCard({ label, value, icon, tone = 'blue', unit, description }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          {label}
        </span>
        <div className={cn('flex h-8 w-8 items-center justify-center rounded-lg', TONE_STYLES[tone])}>
          <Icon name={icon} size={16} />
        </div>
      </div>

      {/* Value */}
      <div className="flex items-baseline gap-2">
        {value != null ? (
          <>
            <span className="text-3xl font-bold tracking-tight">
              {typeof value === 'number' ? value.toFixed(1) : value}
            </span>
            {unit && (
              <span className="text-sm text-muted-foreground">{unit}</span>
            )}
          </>
        ) : (
          <span className="text-3xl font-bold tracking-tight text-zinc-300 dark:text-zinc-700">
            —
          </span>
        )}
      </div>

      {/* Description */}
      {description && (
        <p className="text-xs text-muted-foreground">
          {description}
        </p>
      )}
    </div>
  )
}
