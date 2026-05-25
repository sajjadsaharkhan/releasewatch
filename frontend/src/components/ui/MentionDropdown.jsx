import React, { useState, useRef, useEffect, useCallback } from 'react'
import { cn } from '../../lib/cn'

export function MentionDropdown({
  open,
  top,
  left,
  query,
  users,
  onSelect,
  onClose
}) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const listRef = useRef(null)

  const filteredUsers = React.useMemo(() => {
    if (!query) return users.slice(0, 8)
    const q = query.toLowerCase()
    return users
      .filter(u => u.name.toLowerCase().includes(q) || u.username.toLowerCase().includes(q))
      .slice(0, 8)
  }, [query, users])

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  useEffect(() => {
    if (open && selectedIndex > 0 && listRef.current) {
      const selectedEl = listRef.current.children[selectedIndex]
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: 'nearest' })
      }
    }
  }, [selectedIndex, open])

  const handleKeyDown = useCallback((e) => {
    if (!open) return

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(prev => (prev + 1) % filteredUsers.length)
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(prev => (prev - 1 + filteredUsers.length) % filteredUsers.length)
        break
      case 'Enter':
        e.preventDefault()
        if (filteredUsers[selectedIndex]) {
          onSelect(filteredUsers[selectedIndex])
        }
        break
      case 'Escape':
        e.preventDefault()
        onClose()
        break
      case 'Tab':
        e.preventDefault()
        if (filteredUsers[selectedIndex]) {
          onSelect(filteredUsers[selectedIndex])
        }
        break
    }
  }, [open, selectedIndex, filteredUsers, onSelect, onClose])

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleKeyDown)
      return () => document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, handleKeyDown])

  if (!open || filteredUsers.length === 0) return null

  return (
    <div
      className="fixed z-50 w-56 bg-popover border border-border rounded-lg shadow-lg overflow-hidden"
      style={{ top: `${top}px`, left: `${left}px` }}
    >
      <div className="px-2 py-1.5 text-xs text-muted-foreground border-b border-border">
        {query ? `Matching "${query}"` : 'Team members'}
      </div>
      <ul ref={listRef} className="max-h-48 overflow-auto py-1">
        {filteredUsers.map((user, index) => (
          <li
            key={user.id}
            className={cn(
              'flex items-center gap-2 px-2 py-1.5 cursor-pointer rounded-sm mx-1 my-0.5',
              index === selectedIndex ? 'bg-accent' : 'hover:bg-accent/50'
            )}
            onClick={() => onSelect(user)}
            onMouseEnter={() => setSelectedIndex(index)}
          >
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium text-white"
              style={{ backgroundColor: user.avatar_color }}
            >
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{user.name}</div>
              <div className="text-xs text-muted-foreground truncate">@{user.username}</div>
            </div>
          </li>
        ))}
      </ul>
      <div className="px-2 py-1 text-xs text-muted-foreground border-t border-border flex items-center gap-1">
        <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">↑↓</kbd>
        <span>to navigate</span>
        <kbd className="px-1 py-0.5 bg-muted rounded text-[10px] ml-1">Enter</kbd>
        <span>to select</span>
      </div>
    </div>
  )
}
