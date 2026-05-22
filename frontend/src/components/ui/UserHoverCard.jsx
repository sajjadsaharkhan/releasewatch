import React, { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { MapPin, Calendar, AlertCircle, CheckCircle, Activity } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Avatar } from './Avatar'
import { RoleBadge } from './Badge'
import { relTime } from '../../lib/relTime'

export function UserHoverCard({ user, size = 20, children, className, align = 'left' }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const triggerRef = useRef(null)
  const cardRef = useRef(null)
  const timeoutRef = useRef(null)

  const close = useCallback(() => setOpen(false), [])

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return
    const triggerRect = triggerRef.current.getBoundingClientRect()
    const cardWidth = 280
    const cardHeight = 320 // Estimated max height of the card
    const gap = 8 // Gap between trigger and card
    const padding = 12 // Minimum padding from viewport edges

    // Calculate available space in each direction
    const spaceAbove = triggerRect.top - padding
    const spaceBelow = window.innerHeight - triggerRect.bottom - padding
    const spaceLeft = triggerRect.left - padding
    const spaceRight = window.innerWidth - triggerRect.right - padding

    // Determine vertical position (prefer downward if enough space)
    let top
    const shouldGoUp = spaceBelow < cardHeight && spaceAbove > spaceBelow
    if (shouldGoUp) {
      // Position above the trigger
      top = triggerRect.top - cardHeight - gap
    } else {
      // Position below the trigger
      top = triggerRect.bottom + gap
    }

    // Determine horizontal position based on available space
    // Try to align with trigger left, but shift if needed
    let left
    if (spaceLeft >= cardWidth) {
      // Enough space to the left - align left edge with trigger left edge
      left = Math.max(padding, triggerRect.left)
    } else if (spaceRight >= cardWidth) {
      // Enough space to the right
      if (spaceLeft < padding && triggerRect.left + cardWidth > window.innerWidth - padding) {
        // Trigger is near left edge but card would overflow right
        left = padding
      } else {
        left = triggerRect.left
      }
    } else {
      // Not enough space on either side - position with maximum available space
      if (spaceLeft > spaceRight) {
        // More space on left - align right edge
        left = Math.max(padding, triggerRect.right - cardWidth)
      } else {
        // More space on right - align left edge
        left = Math.min(triggerRect.left, window.innerWidth - cardWidth - padding)
      }
    }

    // Final boundary checks
    left = Math.max(padding, Math.min(left, window.innerWidth - cardWidth - padding))
    top = Math.max(padding, Math.min(top, window.innerHeight - cardHeight - padding))

    setPosition({ top, left })
  }, [align])

  const handleMouseEnter = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    timeoutRef.current = setTimeout(() => {
      updatePosition()
      setOpen(true)
    }, 200) // 200ms delay before showing
  }

  const handleMouseLeave = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    timeoutRef.current = setTimeout(() => {
      setOpen(false)
    }, 150) // Small delay before hiding to allow moving mouse to card
  }

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  // Handle escape key
  useEffect(() => {
    if (!open) return
    const handleKey = (e) => {
      if (e.key === 'Escape') close()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, close])

  const cardContent = open ? (
    <div
      ref={cardRef}
      className="fixed z-[9999] w-70 bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700 shadow-lg overflow-hidden"
      style={{
        top: `${position.top}px`,
        left: `${position.left}px`,
        width: '280px'
      }}
      onMouseEnter={() => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current)
        setOpen(true)
      }}
      onMouseLeave={handleMouseLeave}
    >
      {/* Header section */}
      <div className="p-4 border-b border-zinc-200 dark:border-zinc-700">
        <div className="flex items-start gap-3">
          <Avatar user={user} size={48} ring />
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 truncate">
              {user.name}
            </h3>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 truncate">@{user.username}</p>
            {user.title && (
              <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-0.5 truncate">
                {user.title}
              </p>
            )}
          </div>
        </div>
        {user.bio && (
          <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-2 line-clamp-2">
            {user.bio}
          </p>
        )}
      </div>

      {/* Info section */}
      <div className="p-4 space-y-2">
        {user.location && (
          <div className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-400">
            <MapPin className="h-3.5 w-3.5" />
            <span>{user.location}</span>
          </div>
        )}

        {user.joinedAt && (
          <div className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-400">
            <Calendar className="h-3.5 w-3.5" />
            <span>Joined {relTime(user.joinedAt)}</span>
          </div>
        )}

        {user.tgConnected && user.tgHandle && (
          <div className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-400">
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
            </svg>
            <span>{user.tgHandle}</span>
          </div>
        )}
      </div>

      {/* Stats section */}
      {(user.reported !== undefined || user.fixed !== undefined) && (
        <div className="px-4 pb-4">
          <div className="grid grid-cols-3 gap-2">
            {user.reported !== undefined && (
              <div className="text-center">
                <div className="flex items-center justify-center gap-1 text-xs font-medium text-zinc-900 dark:text-zinc-100">
                  <AlertCircle className="h-3 w-3 text-amber-500" />
                  {user.reported}
                </div>
                <div className="text-[10px] text-zinc-500 dark:text-zinc-400">Reported</div>
              </div>
            )}
            {user.fixed !== undefined && (
              <div className="text-center">
                <div className="flex items-center justify-center gap-1 text-xs font-medium text-zinc-900 dark:text-zinc-100">
                  <CheckCircle className="h-3 w-3 text-green-500" />
                  {user.fixed}
                </div>
                <div className="text-[10px] text-zinc-500 dark:text-zinc-400">Fixed</div>
              </div>
            )}
            {user.fixRate !== undefined && (
              <div className="text-center">
                <div className="flex items-center justify-center gap-1 text-xs font-medium text-zinc-900 dark:text-zinc-100">
                  <Activity className="h-3 w-3 text-blue-500" />
                  {user.fixRate}%
                </div>
                <div className="text-[10px] text-zinc-500 dark:text-zinc-400">Fix Rate</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Footer with role badge */}
      {user.role && (
        <div className="px-4 py-2 bg-zinc-50 dark:bg-zinc-800/50 border-t border-zinc-200 dark:border-zinc-700">
          <RoleBadge role={user.role} />
        </div>
      )}
    </div>
  ) : null

  return (
    <>
      <span
        ref={triggerRef}
        className={cn('inline-flex cursor-pointer', className)}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onClick={(e) => {
          e.stopPropagation()
          navigate(`/u/${user.username}`)
        }}
      >
        {children || <Avatar user={user} size={size} />}
      </span>
      {cardContent && createPortal(cardContent, document.body)}
    </>
  )
}
