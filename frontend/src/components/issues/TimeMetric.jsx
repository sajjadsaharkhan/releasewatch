import React from 'react'
import { cn } from '../../lib/cn'

export function TimeMetric({ label, value, tone = 'default' }) {
  const tones = {
    default: 'text-zinc-800 dark:text-zinc-100',
    green: 'text-emerald-600 dark:text-emerald-400',
    amber: 'text-amber-600 dark:text-amber-400',
    red: 'text-red-600 dark:text-red-400',
  }
  return (
    <div className="flex items-center justify-between text-[12px]">
      <span className="text-zinc-500 dark:text-zinc-400">{label}</span>
      <span className={cn('font-medium tabular-nums', tones[tone])}>{value}</span>
    </div>
  )
}