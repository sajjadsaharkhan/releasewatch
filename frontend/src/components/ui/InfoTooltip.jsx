import React, { useState, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/cn'
import { Icon } from './Icon'

/**
 * InfoTooltip - An improved tooltip component with arrow pointer and smooth animation.
 *
 * Features:
 * - Arrow/pointer for visual connection to trigger element
 * - Smooth fade-in and scale animation
 * - Proper text wrapping with word-break
 * - Compact sizing to fit within card layouts
 * - 100ms delay for faster appearance
 * - Dark mode support via CSS variables
 * - Portal rendering to avoid z-index clipping issues
 */
export function InfoTooltip({ content, side = 'top', className }) {
  const [visible, setVisible] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const timerRef = useRef(null)
  const triggerRef = useRef(null)

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    const tooltipWidth = 192 // w-48 = 12rem = 192px

    // Calculate position based on side
    let top, left
    const gap = 8

    switch (side) {
      case 'top':
        top = rect.top + window.scrollY - gap
        left = rect.left + window.scrollX + rect.width / 2 - tooltipWidth / 2
        break
      case 'bottom':
        top = rect.bottom + window.scrollY + gap
        left = rect.left + window.scrollX + rect.width / 2 - tooltipWidth / 2
        break
      case 'left':
        top = rect.top + window.scrollY + rect.height / 2
        left = rect.left + window.scrollX - tooltipWidth - gap
        break
      case 'right':
        top = rect.top + window.scrollY + rect.height / 2
        left = rect.right + window.scrollX + gap
        break
    }

    setPosition({ top, left })
  }, [side])

  const show = useCallback(() => {
    timerRef.current = setTimeout(() => {
      updatePosition()
      setVisible(true)
    }, 100)
  }, [updatePosition])

  const hide = useCallback(() => {
    clearTimeout(timerRef.current)
    setVisible(false)
  }, [])

  if (!content) return null

  // Arrow positioning - positioned at the edge of the tooltip
  const arrowPositions = {
    top: '-bottom-1.5 left-1/2 -translate-x-1/2 border-t-zinc-900 dark:border-t-zinc-100',
    bottom: '-top-1.5 left-1/2 -translate-x-1/2 border-b-zinc-900 dark:border-b-zinc-100',
    left: '-right-1.5 top-1/2 -translate-y-1/2 border-l-zinc-900 dark:border-l-zinc-100',
    right: '-left-1.5 top-1/2 -translate-y-1/2 border-r-zinc-900 dark:border-r-zinc-100',
  }

  return (
    <span
      ref={triggerRef}
      className="relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
    >
      <Icon name="info" size={14} className="text-muted-foreground cursor-help" />

      {visible && createPortal(
        <div
          className="fixed z-[9999]"
          style={{ top: `${position.top}px`, left: `${position.left}px` }}
        >
          <div
            className={cn(
              // Base styles
              'w-48 rounded-lg px-2.5 py-2 text-[11px] leading-snug',
              // Colors - dark background with white text
              'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-md',
              // Text wrapping
              'break-words whitespace-normal',
              // Animation
              'animate-in fade-in zoom-in-95 duration-200',
              className
            )}
          >
            {/* Arrow */}
            <span
              className={cn(
                'absolute border-[5px] border-transparent',
                arrowPositions[side] ?? arrowPositions.top
              )}
            />

            {content}
          </div>
        </div>,
        document.body
      )}
    </span>
  )
}
