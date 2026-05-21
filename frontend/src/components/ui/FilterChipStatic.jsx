import React from 'react'
import { ChevronDown } from 'lucide-react'
import { Icon } from './Icon'

export function FilterChipStatic({ icon, label, value }) {
  return (
    <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 hover:bg-zinc-50 dark:hover:bg-zinc-900 text-[12px]">
      <Icon name={icon} size={12} className="text-zinc-500" />
      <span className="text-zinc-500">{label}:</span>
      <span className="font-medium text-zinc-800 dark:text-zinc-100">{value}</span>
      <ChevronDown className="h-3 w-3 text-zinc-400" />
    </button>
  )
}