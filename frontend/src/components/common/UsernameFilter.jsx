import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { AtSign, ChevronDown, Search, X } from 'lucide-react'
import { cn } from '../../lib/cn'

export function UsernameFilter({ users = [], selectedId, onChange }) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0 })

  const triggerRef = useRef(null)
  const dropdownRef = useRef(null)

  const selectedUser = users.find(u => u.id === selectedId)

  // Filter users by search query (username or name)
  const filteredUsers = useMemo(() => {
    if (!searchQuery.trim()) return users
    const q = searchQuery.toLowerCase()
    return users.filter(u =>
      u.username.toLowerCase().includes(q) ||
      u.name.toLowerCase().includes(q)
    )
  }, [searchQuery, users])

  // Calculate dropdown position with smart placement
  const updateDropdownPosition = useCallback(() => {
    if (!triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    const dropdownWidth = 288 // w-72 = 18rem = 288px
    const dropdownHeight = 320 // Approximate max height
    const gap = 4 // Gap between trigger and dropdown
    const viewportPadding = 12 // Minimum padding from viewport edges

    // Check if there's enough space above to open upward
    const spaceAbove = rect.top - viewportPadding
    const spaceBelow = window.innerHeight - rect.bottom - viewportPadding

    // Default to opening downward (safer), only open upward if there's significantly more space above
    // and not enough space below
    const openUpward = spaceAbove > dropdownHeight && spaceBelow < dropdownHeight

    let top
    if (openUpward) {
      // Open above the trigger
      top = Math.max(viewportPadding, rect.top - dropdownHeight - gap)
    } else {
      // Open below the trigger (default)
      top = rect.bottom + gap
    }

    // Calculate left position, ensuring we don't go off the right edge
    let left = rect.left
    // If dropdown would overflow right edge, align to right side of trigger instead
    if (left + dropdownWidth > window.innerWidth - viewportPadding) {
      left = window.innerWidth - dropdownWidth - viewportPadding
    }
    // Ensure we don't go off the left edge either
    left = Math.max(viewportPadding, left)

    // Ensure we don't go above viewport
    top = Math.max(viewportPadding, top)
    // Ensure we don't go below viewport (adjust if needed)
    top = Math.min(top, window.innerHeight - dropdownHeight - viewportPadding)

    setDropdownPosition({
      top,
      left
    })
  }, [])

  const toggleOpen = () => {
    if (!isOpen) {
      updateDropdownPosition()
    }
    setIsOpen(!isOpen)
    setSearchQuery('')
  }

  const close = () => {
    setIsOpen(false)
    setSearchQuery('')
  }

  const selectUser = (userId) => {
    onChange(userId)
    close()
  }

  const clearSelection = (e) => {
    e.stopPropagation()
    onChange(null)
  }

  // Handle clicks outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target) &&
        !triggerRef.current?.contains(e.target)
      ) {
        close()
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  // Handle scroll to reposition
  useEffect(() => {
    if (isOpen) {
      window.addEventListener('scroll', updateDropdownPosition, true)
      return () => window.removeEventListener('scroll', updateDropdownPosition, true)
    }
  }, [isOpen, updateDropdownPosition])

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') close()
    }
    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      return () => document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  return (
    <div className="inline-flex">
      {/* Trigger button */}
      <button
        ref={triggerRef}
        type="button"
        onClick={toggleOpen}
        className={cn(
          "inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border transition-colors text-[12px]",
          isOpen
            ? "border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20"
            : "border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 hover:bg-zinc-50 dark:hover:bg-zinc-900"
        )}
      >
        <AtSign className="h-3.5 w-3.5 text-zinc-500" />
        <span className="text-zinc-500">Member:</span>
        <span className="font-medium text-zinc-800 dark:text-zinc-100 max-w-[120px] truncate">
          {selectedUser ? selectedUser.name : 'All members'}
        </span>
        {selectedUser && (
          <button
            type="button"
            onClick={clearSelection}
            className="ml-0.5 hover:text-zinc-600 dark:hover:text-zinc-300"
          >
            <X className="h-3 w-3" />
          </button>
        )}
        <ChevronDown className={cn("h-3 w-3 transition-transform text-zinc-400", isOpen && "rotate-180")} />
      </button>

      {/* Floating Dropdown - rendered via Portal to escape stacking context */}
      {isOpen && createPortal(
        <div
          ref={dropdownRef}
          className="fixed z-[9999] w-72 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-lg shadow-lg overflow-hidden"
          style={{ top: `${dropdownPosition.top}px`, left: `${dropdownPosition.left}px` }}
        >
          {/* Search input */}
          <div className="border-b border-zinc-200 dark:border-zinc-700 px-3 py-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400" />
              <input
                type="text"
                placeholder="Search members..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-sm bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
              />
            </div>
          </div>

          {/* "All members" option */}
          <div className="py-1 max-h-64 overflow-y-auto">
            <button
              type="button"
              onClick={() => selectUser(null)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2 text-left transition-colors',
                !selectedId
                  ? 'bg-blue-100 dark:bg-blue-900/40'
                  : 'hover:bg-zinc-100 dark:hover:bg-zinc-800'
              )}
            >
              <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0 bg-zinc-400">
                All
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">All Team Members</div>
                <div className="text-xs text-zinc-500 dark:text-zinc-400">Show metrics for everyone</div>
              </div>
              {!selectedId && (
                <span className="h-4 w-4 rounded-full bg-blue-500 text-white flex items-center justify-center">
                  ✓
                </span>
              )}
            </button>

            {/* User list */}
            {filteredUsers.length === 0 && searchQuery ? (
              <div className="py-4 text-center text-sm text-zinc-500">
                No members found matching "{searchQuery}"
              </div>
            ) : (
              filteredUsers.map(user => {
                const isSelected = selectedId === user.id
                return (
                  <button
                    key={user.id}
                    type="button"
                    onClick={() => selectUser(user.id)}
                    className={cn(
                      'w-full flex items-center gap-3 px-3 py-2 text-left transition-colors',
                      isSelected
                        ? 'bg-blue-100 dark:bg-blue-900/40'
                        : 'hover:bg-zinc-100 dark:hover:bg-zinc-800'
                    )}
                  >
                    <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0" style={{ backgroundColor: user.avatar_color }}>
                      {user.name.charAt(0).toUpperCase()}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">{user.name}</div>
                      <div className="text-xs text-zinc-500 dark:text-zinc-400 truncate">@{user.username}</div>
                    </div>
                    {isSelected && (
                      <span className="h-4 w-4 rounded-full bg-blue-500 text-white flex items-center justify-center">
                        ✓
                      </span>
                    )}
                  </button>
                )
              })
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
