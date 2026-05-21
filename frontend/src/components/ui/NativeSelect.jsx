import React from 'react'
import { ArrowUpDown } from 'lucide-react'
import { cn } from '../../lib/cn'

export function NativeSelect({ value, onChange, className, children }) {
  return (
    <div className="flex items-center gap-2">
      <ArrowUpDown className="h-3 w-3 text-zinc-400" />
      <select
        value={value}
        onChange={onChange}
        className={cn('text-[12px] bg-transparent border-0 p-0 focus:ring-0 cursor-pointer', className)}
      >
        {children}
      </select>
    </div>
  )
}