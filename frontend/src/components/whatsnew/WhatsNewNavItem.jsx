import React, { useRef, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { cn } from '../../lib/cn'
import { useWhatsNew } from '../../hooks/useWhatsNew'
import { RailLabel } from '../layout/NavItem'
import { useOpenChangelog } from './store'

/**
 * The sidebar's way back to What's new (TASK-575): opens the changelog. A blue
 * dot marks a note not yet seen; in the collapsed rail it sits on the icon's
 * corner and the label shows on hover, like every rail item.
 */
export function WhatsNewNavItem({ collapsed = false }) {
  const { hasUnseen } = useWhatsNew()
  const openChangelog = useOpenChangelog()
  const ref = useRef(null)
  const [hover, setHover] = useState(false)
  const label = hasUnseen ? 'What’s new (new updates)' : 'What’s new'

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={openChangelog}
        aria-label={collapsed ? label : undefined}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onFocus={() => setHover(true)}
        onBlur={() => setHover(false)}
        className={cn(
          'relative flex items-center rounded-lg text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          collapsed ? 'mx-auto h-9 w-9 justify-center' : 'w-full gap-2.5 px-3 py-2',
        )}
      >
        <Sparkles aria-hidden="true" className="h-4 w-4 shrink-0" />
        {!collapsed && <span className="flex-1 truncate text-left">What’s new</span>}
        {hasUnseen && (
          <span aria-hidden="true" className={cn('absolute flex h-2 w-2', collapsed ? 'right-1.5 top-1.5' : 'right-3 top-1/2 -translate-y-1/2')}>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75 motion-reduce:hidden" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
          </span>
        )}
        {hasUnseen && !collapsed && <span className="sr-only">(new updates)</span>}
      </button>
      {collapsed && hover && ref.current && <RailLabel anchor={ref.current}>What’s new</RailLabel>}
    </>
  )
}
