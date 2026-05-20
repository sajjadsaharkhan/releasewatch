import React from 'react'
import { cn } from '../../lib/cn'

export function Segmented({ value, onValueChange, options = [], className }) {
  return (
    <div
      className={cn(
        'inline-flex items-center rounded-lg border border-border bg-muted p-0.5 gap-0.5',
        className
      )}
    >
      {options.map((opt) => {
        const isActive = opt.value === value
        return (
          <button
            key={opt.value}
            onClick={() => onValueChange?.(opt.value)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-sm font-medium transition-all',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              isActive
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {opt.icon && <span className="opacity-70 text-xs">{opt.icon}</span>}
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
