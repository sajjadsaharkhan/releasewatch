import React, { useState, useRef, useEffect, useLayoutEffect, useCallback, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronDown, Search } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Avatar } from '../ui/Avatar'

const MENU_MAX_HEIGHT = 300

/**
 * Single-select user picker with search by full name or username.
 * Follows the overlay convention (docs/design.md §7): portaled, `position:
 * fixed` from the trigger rect, 12px viewport clamp, closes on outside
 * mousedown and Escape, follows the trigger on scroll.
 *
 * `value` is a user id or null; `onChange(id | null)`. `emptyLabel` names the
 * "no user" option (omit it to make a choice required).
 */
export function UserPicker({ users = [], value, onChange, emptyLabel = 'Unassigned', placeholder = 'Choose a person…', className }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [position, setPosition] = useState({ top: 0, left: 0, width: 0 })
  const triggerRef = useRef(null)
  const menuRef = useRef(null)
  const inputRef = useRef(null)

  const selected = users.find(u => String(u.id) === String(value)) ?? null

  const options = useMemo(() => {
    const q = query.trim().toLowerCase()
    const matches = q
      ? users.filter(u => u.name?.toLowerCase().includes(q) || u.username?.toLowerCase().includes(q))
      : users
    const list = matches.map(u => ({ id: u.id, user: u }))
    return emptyLabel && !q ? [{ id: null, user: null }, ...list] : list
  }, [users, query, emptyLabel])

  const close = useCallback(() => {
    setOpen(false)
    setQuery('')
  }, [])

  const place = useCallback(() => {
    if (!triggerRef.current) return false
    const rect = triggerRef.current.getBoundingClientRect()
    if (rect.bottom < 0 || rect.top > window.innerHeight) return false
    const padding = 12
    const width = Math.max(rect.width, 240)
    const left = Math.max(padding, Math.min(rect.left, window.innerWidth - width - padding))
    const spaceBelow = window.innerHeight - rect.bottom
    const flip = spaceBelow < MENU_MAX_HEIGHT + 8 && rect.top > spaceBelow
    setPosition(flip
      ? { bottom: window.innerHeight - rect.top + 4, left, width }
      : { top: rect.bottom + 4, left, width })
    return true
  }, [])

  useLayoutEffect(() => {
    if (!open) return
    place()
    inputRef.current?.focus()
    const current = options.findIndex(o => String(o.id) === String(value ?? null))
    setActive(current >= 0 ? current : 0)
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { setActive(0) }, [query])

  useEffect(() => {
    if (!open) return
    function follow(e) {
      if (e?.target && menuRef.current?.contains(e.target)) return
      if (!place()) close()
    }
    function outside(e) {
      if (triggerRef.current?.contains(e.target) || menuRef.current?.contains(e.target)) return
      close()
    }
    window.addEventListener('scroll', follow, true)
    window.addEventListener('resize', follow)
    document.addEventListener('mousedown', outside)
    return () => {
      window.removeEventListener('scroll', follow, true)
      window.removeEventListener('resize', follow)
      document.removeEventListener('mousedown', outside)
    }
  }, [open, place, close])

  useEffect(() => {
    menuRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [active])

  function choose(option) {
    onChange?.(option.id)
    close()
    triggerRef.current?.focus()
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive(i => Math.min(i + 1, options.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (options[active]) choose(options[active])
    } else if (e.key === 'Escape') {
      e.preventDefault()
      close()
      triggerRef.current?.focus()
    }
  }

  const menu = open ? (
    <div
      ref={menuRef}
      className="fixed z-[100] rounded-lg border border-border bg-card shadow-lg text-sm"
      style={{ top: position.top, bottom: position.bottom, left: position.left, width: position.width }}
    >
      <div className="flex items-center gap-2 border-b border-border px-3">
        <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <input
          ref={inputRef}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Search by name or username…"
          aria-label="Search people"
          aria-controls="user-picker-options"
          aria-activedescendant={options[active] ? `user-picker-option-${active}` : undefined}
          className="h-9 w-full bg-transparent text-sm placeholder:text-muted-foreground focus:outline-none"
        />
      </div>
      <ul id="user-picker-options" role="listbox" className="max-h-60 overflow-y-auto py-1" style={{ maxHeight: MENU_MAX_HEIGHT - 40 }}>
        {options.length === 0 && (
          <li className="px-3 py-3 text-center text-[12px] text-muted-foreground">No one matches “{query.trim()}”.</li>
        )}
        {options.map((o, index) => {
          const isSelected = String(o.id) === String(value ?? null)
          return (
            <li
              key={o.id ?? 'none'}
              id={`user-picker-option-${index}`}
              data-index={index}
              role="option"
              aria-selected={isSelected}
              onMouseEnter={() => setActive(index)}
              onMouseDown={e => e.preventDefault()}
              onClick={() => choose(o)}
              className={cn(
                'flex cursor-pointer items-center gap-2 px-3 py-1.5',
                index === active ? 'bg-accent' : 'hover:bg-accent/50',
              )}
            >
              {o.user ? (
                <>
                  <Avatar user={o.user} size={20} />
                  <span className="truncate text-foreground">{o.user.name}</span>
                  <span className="truncate font-mono text-[11px] text-muted-foreground">@{o.user.username}</span>
                </>
              ) : (
                <span className="italic text-muted-foreground">{emptyLabel}</span>
              )}
              {isSelected && <Check className="ml-auto h-3.5 w-3.5 shrink-0 text-foreground" aria-hidden="true" />}
            </li>
          )
        })}
      </ul>
    </div>
  ) : null

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => (open ? close() : setOpen(true))}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={cn(
          'flex h-9 w-full items-center justify-between gap-2 px-3 py-1 text-left text-sm',
          'rounded-[var(--radius)] border border-input bg-transparent transition-colors hover:bg-accent/50',
          'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
          className,
        )}
      >
        {selected ? (
          <span className="flex min-w-0 items-center gap-2">
            <Avatar user={selected} size={18} />
            <span className="truncate text-foreground">{selected.name}</span>
            <span className="truncate font-mono text-[11px] text-muted-foreground">@{selected.username}</span>
          </span>
        ) : (
          <span className={cn('flex-1', emptyLabel ? 'italic text-muted-foreground' : 'text-muted-foreground')}>
            {emptyLabel || placeholder}
          </span>
        )}
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      </button>
      {menu && createPortal(menu, document.body)}
    </>
  )
}
