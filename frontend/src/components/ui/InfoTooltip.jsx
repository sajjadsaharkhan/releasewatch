import React, { useState, useRef, useCallback } from 'react'
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
 */
export function InfoTooltip({ content, side = 'top', className }) {
  const [visible, setVisible] = useState(false)
  const timerRef = useRef(null)

  const show = useCallback(() => {
    timerRef.current = setTimeout(() => setVisible(true), 100)
  }, [])

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

  // Tooltip positioning - offset from trigger
  const tooltipPositions = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  }

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
    >
      <Icon name="info" size={14} className="text-muted-foreground cursor-help" />

      {visible && (
        <div
          className={cn(
            // Base styles
            'absolute z-[100] w-48 rounded-lg px-2.5 py-2 text-[11px] leading-snug',
            // Colors - dark background with white text
            'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-md',
            // Text wrapping
            'break-words whitespace-normal',
            // Animation
            'animate-in fade-in zoom-in-95 duration-200',
            // Position
            tooltipPositions[side] ?? tooltipPositions.top,
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
      )}
    </span>
  )
}
