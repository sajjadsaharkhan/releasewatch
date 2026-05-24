import React, { useState, useRef, useEffect, createContext, useContext } from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from '../../lib/cn'

const SelectContext = createContext(null)

export function Select({ value, onChange, children, placeholder = "Select...", className, disabled = false }) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0, width: 0 })
  const triggerRef = useRef(null)
  const dropdownRef = useRef(null)

  const close = () => setOpen(false)

  const selectedLabel = React.useMemo(() => {
    let label = placeholder
    React.Children.forEach(children, (child) => {
      if (React.isValidElement(child) && child.props.value === value) {
        label = child.props.children
      }
    })
    return label
  }, [children, value, placeholder])

  useEffect(() => {
    if (!open || !triggerRef.current) return
    const triggerRect = triggerRef.current.getBoundingClientRect()
    const viewportWidth = window.innerWidth
    const padding = 12

    let left = triggerRect.left
    const width = triggerRect.width

    // Ensure dropdown doesn't go off the right edge
    if (left + width > viewportWidth - padding) {
      left = viewportWidth - width - padding
    }

    // Ensure dropdown doesn't go off the left edge
    if (left < padding) {
      left = padding
    }

    setPosition({
      top: triggerRect.bottom + 4,
      left: left,
      width: width,
    })
  }, [open])

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

  const handleSelect = (val) => {
    onChange?.(val)
    close()
  }

  const dropdownContent = open ? (
    <SelectContext.Provider value={{ value, handleSelect, close }}>
      <div
        ref={dropdownRef}
        className="fixed z-[100] mt-1 rounded-lg border border-border bg-card shadow-lg py-1 text-sm max-h-60 overflow-auto"
        style={{ top: position.top, left: position.left, width: position.width }}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </SelectContext.Provider>
  ) : null

  return (
    <>
      <div
        ref={triggerRef}
        onClick={() => !disabled && setOpen((o) => !o)}
        className={cn(
          'flex items-center justify-between gap-2 h-9 px-3 py-1',
          'rounded-[var(--radius)] border border-input',
          'bg-transparent text-sm',
          'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
          'cursor-pointer transition-colors',
          disabled && 'cursor-not-allowed opacity-50',
          !disabled && 'hover:bg-accent/50',
          className
        )}
      >
        <span className={cn('flex-1', !value && 'text-muted-foreground')}>{selectedLabel}</span>
        <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
      </div>
      {dropdownContent && createPortal(dropdownContent, document.body)}
    </>
  )
}

export function SelectItem({ children, value, disabled = false }) {
  const context = useContext(SelectContext)
  if (!context) throw new Error('SelectItem must be used within Select')

  const { value: selectedValue, handleSelect } = context
  const isSelected = value === selectedValue

  return (
    <button
      type="button"
      onClick={() => !disabled && handleSelect(value)}
      disabled={disabled}
      className={cn(
        'flex items-center justify-between gap-2 w-full px-3 py-2 text-left text-sm transition-colors',
        'focus-visible:outline-none focus:bg-accent',
        'hover:bg-accent/50',
        isSelected ? 'bg-accent' : 'text-foreground',
        disabled && 'pointer-events-none opacity-50'
      )}
    >
      <span>{children}</span>
      {isSelected && <Check className="h-4 w-4 text-primary" />}
    </button>
  )
}
