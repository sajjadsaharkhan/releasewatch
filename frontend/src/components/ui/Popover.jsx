import React, { useState, useRef, useEffect, createContext, useContext } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/cn'

const PopoverContext = createContext(null)

export function Popover({ open, onOpenChange, children, align = 'start' }) {
  const [internalOpen, setInternalOpen] = useState(false)
  const triggerRef = useRef(null)

  const isControlled = open !== undefined
  const isOpen = isControlled ? open : internalOpen

  const handleOpenChange = (newOpen) => {
    if (!isControlled) {
      setInternalOpen(newOpen)
    }
    onOpenChange?.(newOpen)
  }

  return (
    <PopoverContext.Provider value={{ isOpen, handleOpenChange, triggerRef, align }}>
      {children}
    </PopoverContext.Provider>
  )
}

export function PopoverTrigger({ asChild = false, children, onClick }) {
  const context = useContext(PopoverContext)
  if (!context) throw new Error('PopoverTrigger must be used within Popover')

  const { isOpen, handleOpenChange, triggerRef } = context

  const handleClick = (e) => {
    if (onClick) onClick(e)
    handleOpenChange(!isOpen)
  }

  if (asChild && React.isValidElement(children)) {
    // Get the existing ref from the child if any
    const childRef = children.ref

    return React.cloneElement(children, {
      ref: (node) => {
        // Set our trigger ref
        triggerRef.current = node

        // Forward to child's ref if it exists
        if (!childRef) return

        if (typeof childRef === 'function') {
          childRef(node)
        } else if (childRef !== null && typeof childRef === 'object') {
          childRef.current = node
        }
      },
      onClick: (e) => {
        handleClick(e)
        // Call original onClick if it exists
        if (typeof children.props.onClick === 'function') {
          children.props.onClick(e)
        }
      },
    })
  }

  return (
    <div ref={triggerRef} onClick={handleClick} className="inline-block cursor-pointer">
      {children}
    </div>
  )
}

export function PopoverContent({ children, className, width }) {
  const context = useContext(PopoverContext)
  if (!context) throw new Error('PopoverContent must be used within Popover')

  const { isOpen, handleOpenChange, triggerRef, align } = context
  const contentRef = useRef(null)
  const [position, setPosition] = useState({ top: 0, left: 0 })

  useEffect(() => {
    if (!isOpen || !triggerRef.current) return

    const updatePosition = () => {
      const trigger = triggerRef.current
      if (!trigger) return

      const triggerRect = trigger.getBoundingClientRect()
      const scrollX = window.scrollX || window.pageXOffset
      const scrollY = window.scrollY || window.pageYOffset

      // Use trigger width as default, or content width if specified
      const contentWidth = width || triggerRect.width
      const viewportWidth = window.innerWidth
      const padding = 12

      let left = triggerRect.left + scrollX
      if (align === 'center') {
        left = triggerRect.left + scrollX + triggerRect.width / 2 - contentWidth / 2
      } else if (align === 'end') {
        left = triggerRect.right + scrollX - contentWidth
      }

      // Ensure dropdown doesn't go off the right edge
      if (left + contentWidth > viewportWidth - padding) {
        left = viewportWidth - contentWidth - padding + scrollX
      }

      // Ensure dropdown doesn't go off the left edge
      if (left < padding + scrollX) {
        left = padding + scrollX
      }

      setPosition({
        top: triggerRect.bottom + scrollY + 4,
        left: left,
      })
    }

    // Update position immediately and after content renders
    updatePosition()
    const rafId = requestAnimationFrame(updatePosition)

    // Recalculate on resize
    window.addEventListener('resize', updatePosition)
    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('resize', updatePosition)
    }
  }, [isOpen, align, width, triggerRef])

  useEffect(() => {
    if (!isOpen) return
    function handle(e) {
      const content = contentRef.current
      const trigger = triggerRef.current
      if (content?.contains(e.target) || trigger?.contains(e.target)) return
      handleOpenChange(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [isOpen, handleOpenChange, triggerRef])

  useEffect(() => {
    if (!isOpen) return
    function handleKey(e) {
      if (e.key === 'Escape') handleOpenChange(false)
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [isOpen, handleOpenChange])

  if (!isOpen) return null

  return createPortal(
    <div
      ref={contentRef}
      className={cn(
        'fixed z-[100] rounded-lg border border-border bg-card shadow-lg p-4',
        'animate-in fade-in-0 zoom-in-95',
        className
      )}
      style={{ top: position.top, left: position.left, width: width || 'auto' }}
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </div>,
    document.body
  )
}
