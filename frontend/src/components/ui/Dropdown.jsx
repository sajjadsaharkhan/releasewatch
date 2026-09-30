import React, { useState, useRef, useEffect, useLayoutEffect, useCallback, createContext, useContext } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/cn'

const DropdownContext = createContext(null)

export function Dropdown({ trigger, children, align = 'left', className, width = null }) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const triggerRef = useRef(null)
  const dropdownRef = useRef(null)

  const close = useCallback(() => setOpen(false), [])

  // Place the fixed menu under the trigger — or above it when it wouldn't fit
  // below (like Select), e.g. from a bar pinned to the bottom of the screen.
  // Clamped to the viewport's sides.
  const place = useCallback(() => {
    if (!triggerRef.current) return false
    const rect = triggerRef.current.getBoundingClientRect()
    if (rect.bottom < 0 || rect.top > window.innerHeight) return false
    // Without a fixed width the menu shrink-wraps its items, so measure it —
    // assuming a width misaligns right-aligned menus from their trigger.
    const dropdownWidth = width || dropdownRef.current?.offsetWidth || 140
    const padding = 12
    let left = align === 'right' ? rect.right - dropdownWidth : rect.left
    left = Math.max(padding, Math.min(left, window.innerWidth - dropdownWidth - padding))
    const menuHeight = dropdownRef.current?.offsetHeight ?? 240
    const spaceBelow = window.innerHeight - rect.bottom
    const flip = spaceBelow < menuHeight + 8 && rect.top > spaceBelow
    setPosition(flip ? { bottom: window.innerHeight - rect.top + 4, left } : { top: rect.bottom + 4, left })
    return true
  }, [align, width])

  useLayoutEffect(() => {
    if (open) place()
  }, [open, place])

  // Follow the trigger when the page scrolls or resizes; close once it's off screen.
  useEffect(() => {
    if (!open) return
    function follow(e) {
      // A resize's target is window, which isn't a Node — contains() would throw.
      if (e?.target instanceof Node && dropdownRef.current?.contains(e.target)) return
      if (!place()) close()
    }
    window.addEventListener('scroll', follow, true)
    window.addEventListener('resize', follow)
    return () => {
      window.removeEventListener('scroll', follow, true)
      window.removeEventListener('resize', follow)
    }
  }, [open, place, close])

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
        className={cn(
          'fixed z-[100] rounded-lg border border-border bg-card shadow-lg py-1 text-sm',
          position.bottom == null && 'mt-1',
          // Intrinsic width, so place() measures the same size wherever the menu sits.
          !width && 'w-max',
          className,
        )}
        style={{ top: position.top, bottom: position.bottom, left: position.left, width: width || undefined }}
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
