import React, { useEffect, useRef } from 'react'
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

// Labels never wrap: a tab row that doesn't fit scrolls sideways instead, and
// the active tab keeps itself in view.
export function Tabs({ value, onValueChange, options = [], className }) {
  const activeRef = useRef(null)
  useEffect(() => {
    activeRef.current?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
  }, [value])

  return (
    <div
      role="tablist"
      className={cn(
        'flex items-center gap-1 border-b border-border overflow-x-auto overflow-y-hidden scrollbar-thin',
        className
      )}
    >
      {options.map((opt) => {
        const isActive = opt.value === value
        return (
          <button
            key={opt.value}
            ref={isActive ? activeRef : undefined}
            role="tab"
            aria-selected={isActive}
            onClick={() => onValueChange?.(opt.value)}
            className={cn(
              'relative flex shrink-0 items-center gap-1.5 whitespace-nowrap px-3 py-2 text-sm font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring rounded-t-md',
              isActive
                ? 'text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {opt.icon && <TabIcon name={opt.icon} />}
            {opt.label}
            {opt.badge !== undefined && opt.badge !== null && (
              <span
                className={cn(
                  'ml-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-xs font-medium',
                  isActive
                    ? 'bg-foreground text-background'
                    : 'bg-muted text-muted-foreground'
                )}
              >
                {opt.badge}
              </span>
            )}
            {isActive && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-full bg-foreground" />
            )}
          </button>
        )
      })}
    </div>
  )
}
