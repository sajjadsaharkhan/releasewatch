import React, { useState, useRef, useEffect, useCallback, createContext, useContext } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/cn'

const DropdownContext = createContext(null)

export function Dropdown({ trigger, children, align = 'left', className, width = null }) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const triggerRef = useRef(null)
  const dropdownRef = useRef(null)

  const close = useCallback(() => setOpen(false), [])

  useEffect(() => {
    if (!open || !triggerRef.current) return
    const triggerRect = triggerRef.current.getBoundingClientRect()
    const dropdownWidth = width || 140
    const viewportWidth = window.innerWidth
    const padding = 12

    let left = triggerRect.left
    if (align === 'right') {
      left = triggerRect.right - dropdownWidth
    }

    // Ensure dropdown doesn't go off the right edge
    if (left + dropdownWidth > viewportWidth - padding) {
      left = viewportWidth - dropdownWidth - padding
    }

    // Ensure dropdown doesn't go off the left edge
    if (left < padding) {
      left = padding
    }

    setPosition({
      top: triggerRect.bottom + 4,
      left: left,
    })
  }, [open, align, width])

  useEffect(() => {
    if (!open) return
    function handle(e) {
      if (triggerRef.current?.contains(e.target) || dropdownRef.current?.contains(e.target)) return
      close()
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

  const dropdownContent = open ? (
    <DropdownContext.Provider value={close}>
      <div
        ref={dropdownRef}
        className={cn('fixed z-[100] mt-1 rounded-lg border border-border bg-card shadow-lg', 'py-1 text-sm', className)}
        style={{ top: position.top, left: position.left, width: width || undefined }}
        onClick={(e) => e.stopPropagation()}
      >
        {typeof children === 'function' ? children({ close }) : children}
      </div>
    </DropdownContext.Provider>
  ) : null

  return (
    <>
      <div ref={triggerRef} onClick={() => setOpen((o) => !o)} className="cursor-pointer inline-flex">
        {trigger}
      </div>
      {dropdownContent && createPortal(dropdownContent, document.body)}
    </>
  )
}

export function DropdownItem({ children, onClick, icon: Icon, destructive = false, disabled = false }) {
  const closeDropdown = useContext(DropdownContext)

  const handleClick = (e) => {
    if (disabled) return
    onClick?.(e)
    closeDropdown?.()
  }

  return (
    <button
      onClick={handleClick}
      disabled={disabled}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm transition-colors',
        'focus-visible:outline-none',
        destructive ? 'text-destructive hover:bg-destructive/10' : 'text-foreground hover:bg-accent',
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
