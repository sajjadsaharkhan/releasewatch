import React, { useState, useRef, useEffect, useCallback } from 'react'
import { cn } from '../../lib/cn'

export function Dropdown({ trigger, children, align = 'left', className }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  const close = useCallback(() => setOpen(false), [])

  useEffect(() => {
    if (!open) return
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) close()
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open, close])

  useEffect(() => {
    if (!open) return
    function handleKey(e) {
      if (e.key === 'Escape') close()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, close])

  return (
    <div ref={ref} className="relative inline-flex">
      <div onClick={() => setOpen((o) => !o)} className="cursor-pointer">
        {trigger}
      </div>
      {open && (
        <div
          className={cn(
            'absolute top-full z-50 mt-1 min-w-[160px] rounded-lg border border-border bg-card shadow-lg',
            'py-1 text-sm',
            align === 'right' ? 'right-0' : 'left-0',
            className
          )}
          onClick={close}
        >
          {children}
        </div>
      )}
    </div>
  )
}

export function DropdownItem({ children, onClick, icon: Icon, destructive = false, disabled = false }) {
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm transition-colors',
        'focus-visible:outline-none',
        destructive
          ? 'text-destructive hover:bg-destructive/10'
          : 'text-foreground hover:bg-accent',
        disabled && 'pointer-events-none opacity-50'
      )}
    >
      {Icon && <Icon className="h-4 w-4 shrink-0 opacity-70" />}
      {children}
    </button>
  )
}

export function DropdownSep() {
  return <div className="my-1 h-px bg-border" />
}

export function DropdownLabel({ children }) {
  return (
    <div className="px-3 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
      {children}
    </div>
  )
}
