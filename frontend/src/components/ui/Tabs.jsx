import React from 'react'
import { cn } from '../../lib/cn'

export function Tabs({ value, onValueChange, options = [], className }) {
  return (
    <div
      className={cn(
        'flex items-center gap-1 border-b border-border',
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
              'relative flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-colors',
              'focus-visible:outline-none',
              isActive
                ? 'text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {opt.icon && <span className="opacity-70">{opt.icon}</span>}
            {opt.label}
            {opt.badge !== undefined && opt.badge !== null && (
              <span
                className={cn(
                  'ml-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-xs font-medium',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
                )}
              >
                {opt.badge}
              </span>
            )}
            {isActive && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-full bg-primary" />
            )}
          </button>
        )
      })}
    </div>
  )
}
