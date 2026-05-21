import React from 'react'
import * as LucideIcons from 'lucide-react'
import { cn } from '../../lib/cn'

function kebabToPascal(name) {
  return name
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('')
}

function TabIcon({ name, size = 14 }) {
  if (!name) return null
  if (React.isValidElement(name)) return name

  const pascal = kebabToPascal(name)
  const Component = LucideIcons[pascal]

  if (!Component) return null
  return <Component size={size} />
}

export function Tabs({ value, onValueChange, options = [], className }) {
  return (
    <div
      className={cn(
        'flex items-center gap-1 border-b border-zinc-200 dark:border-zinc-800',
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
                ? 'text-zinc-900 dark:text-zinc-100'
                : 'text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100'
            )}
          >
            {opt.icon && <TabIcon name={opt.icon} />}
            {opt.label}
            {opt.badge !== undefined && opt.badge !== null && (
              <span
                className={cn(
                  'ml-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-xs font-medium',
                  isActive
                    ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
                    : 'bg-zinc-200 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400'
                )}
              >
                {opt.badge}
              </span>
            )}
            {isActive && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-full bg-zinc-900 dark:bg-zinc-100" />
            )}
          </button>
        )
      })}
    </div>
  )
}
