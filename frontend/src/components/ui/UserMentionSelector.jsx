import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { AtSign, ChevronDown, X, Search, Check } from 'lucide-react'
import { cn } from '../../lib/cn'

export function UserMentionSelector({ users = [], selectedIds = [], onChange }) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0 })

  const triggerRef = useRef(null)
  const dropdownRef = useRef(null)

  const selectedUsers = users.filter(u => selectedIds.includes(u.id))

  // Filter users by search query (username or name)
  const filteredUsers = useMemo(() => {
    if (!searchQuery.trim()) return users
    const q = searchQuery.toLowerCase()
    return users.filter(u =>
      u.username.toLowerCase().includes(q) ||
      u.name.toLowerCase().includes(q)
    )
  }, [searchQuery, users])

  // Calculate dropdown position (open ABOVE the button)
  const updateDropdownPosition = useCallback(() => {
    if (!triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    const dropdownHeight = 320 // Approximate max height

    setDropdownPosition({
      top: rect.top + window.scrollY - dropdownHeight - 4, // Open above with 4px gap
      left: rect.left + window.scrollX
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

  const toggleUser = (userId) => {
    if (selectedIds.includes(userId)) {
      onChange(selectedIds.filter(id => id !== userId))
    } else {
      onChange([...selectedIds, userId])
    }
  }

  const removeUser = (userId, e) => {
    e.stopPropagation()
    onChange(selectedIds.filter(id => id !== userId))
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
    <div className="border-t border-zinc-200 dark:border-zinc-700 pt-3 px-3">
      {/* Header: trigger on the left, selected user chips on the right */}
      <div className="flex items-center gap-2 mb-2">
        {/* Trigger button */}
        <button
          ref={triggerRef}
          type="button"
          onClick={toggleOpen}
          className={cn(
            "inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-sm font-medium transition-colors flex-shrink-0",
            isOpen
              ? "bg-blue-200 dark:bg-blue-900/60 text-blue-800 dark:text-blue-200"
              : "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/60"
          )}
        >
          <AtSign className="h-3.5 w-3.5" />
          Mention
          <ChevronDown className={cn("h-3 w-3 transition-transform", isOpen && "rotate-180")} />
        </button>

        {/* Selected users chips — immediately after the trigger */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {selectedUsers.map(user => (
            <span
              key={user.id}
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 text-xs font-medium"
            >
              <span className="w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold text-white" style={{ backgroundColor: user.avatar_color }}>
                {user.name.charAt(0).toUpperCase()}
              </span>
              <span>{user.name}</span>
              <button
                type="button"
                onClick={(e) => removeUser(user.id, e)}
                className="ml-0.5 hover:opacity-70"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      </div>

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
                placeholder="Search users..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-sm bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
              />
            </div>
          </div>

          {/* User list - single column */}
          <div className="py-1 max-h-64 overflow-y-auto">
            {filteredUsers.length === 0 ? (
              <div className="py-4 text-center text-sm text-zinc-500">
                No users found matching "{searchQuery}"
              </div>
            ) : (
              filteredUsers.map(user => {
                const isSelected = selectedIds.includes(user.id)
                return (
                  <button
                    key={user.id}
                    type="button"
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      toggleUser(user.id)
                    }}
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
                      <Check className="h-4 w-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
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
