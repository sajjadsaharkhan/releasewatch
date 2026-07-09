import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'

export function EnvTile({ icon, label, value, mono = false }) {
  return (
    <div className="rounded-lg border border-border px-2.5 py-2 bg-card">
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        <Icon name={icon} size={10} /> {label}
      </div>
      <div className={cn('text-[12.5px] mt-0.5 text-zinc-800 dark:text-zinc-100 truncate', mono && 'font-mono')}>{value}</div>
    </div>
  )
}