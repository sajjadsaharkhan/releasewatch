import React, { useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { NavLink } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'

// The collapsed rail's label: portaled, because the nav scrolls and would clip it.
export function RailLabel({ anchor, children }) {
  const r = anchor.getBoundingClientRect()
  return createPortal(
    <span
      role="tooltip"
      className="pointer-events-none fixed z-[100] -translate-y-1/2 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-xs font-medium text-background shadow-md"
      style={{ top: r.top + r.height / 2, left: r.right + 8 }}
    >
      {children}
    </span>,
    document.body,
  )
}

export function NavItem({ to, icon, label, badge, indent = false, collapsed = false }) {
  const ref = useRef(null)
  const [hover, setHover] = useState(false)
  const count = badge !== undefined && badge !== null && badge > 0 ? (badge > 99 ? '99+' : badge) : null

  if (collapsed) {
    return (
      <>
        <NavLink
          ref={ref}
          to={to}
          aria-label={count ? `${label} (${count})` : label}
          onMouseEnter={() => setHover(true)}
          onMouseLeave={() => setHover(false)}
          onFocus={() => setHover(true)}
          onBlur={() => setHover(false)}
          className={({ isActive }) =>
            cn(
              'relative mx-auto flex h-9 w-9 items-center justify-center rounded-lg transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              isActive ? 'bg-accent text-foreground' : 'text-muted-foreground hover:bg-accent hover:text-foreground'
            )
          }
        >
          {icon && <Icon name={icon} size={16} className="shrink-0" />}
          {count && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold leading-none text-primary-foreground">
              {count}
            </span>
          )}
        </NavLink>
        {hover && ref.current && <RailLabel anchor={ref.current}>{label}</RailLabel>}
      </>
    )
  }

  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          indent && 'pl-8',
          isActive
            ? 'bg-accent text-foreground'
            : 'text-muted-foreground hover:bg-accent hover:text-foreground'
        )
      }
    >
      {icon && <Icon name={icon} size={16} className="shrink-0" />}
      <span className="flex-1 truncate">{label}</span>
      {count && (
        <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-xs font-semibold text-primary-foreground">
          {count}
        </span>
      )}
    </NavLink>
  )
}
