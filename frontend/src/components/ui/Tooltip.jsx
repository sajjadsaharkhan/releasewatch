import React, { useState, useRef, useCallback } from 'react'
import { cn } from '../../lib/cn'

export function Tooltip({ content, children, side = 'top', className }) {
  const [visible, setVisible] = useState(false)
  const timerRef = useRef(null)

  const show = useCallback(() => {
    timerRef.current = setTimeout(() => setVisible(true), 300)
  }, [])

  const hide = useCallback(() => {
    clearTimeout(timerRef.current)
    setVisible(false)
  }, [])

  if (!content) return children

  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-1.5',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-1.5',
    left: 'right-full top-1/2 -translate-y-1/2 mr-1.5',
    right: 'left-full top-1/2 -translate-y-1/2 ml-1.5',
  }

  return (
    <span className="relative inline-flex" onMouseEnter={show} onMouseLeave={hide}>
      {children}
      {visible && (
        <span
          className={cn(
            'pointer-events-none absolute z-50 whitespace-nowrap rounded-md',
            'bg-foreground text-background px-2 py-1 text-xs font-medium shadow-md',
            positionClasses[side] ?? positionClasses.top,
            className
          )}
        >
          {content}
        </span>
      )}
    </span>
  )
}
