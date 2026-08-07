import React, { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { SmilePlus } from 'lucide-react'
import { cn } from '../../lib/cn'
import { REACTIONS } from '../../lib/reactions'

const COLS = 4
const GRID_W = 188   // px — 4 cells + padding
// 10 emoji over 4 columns = 3 rows. Keep in sync with REACTIONS or the flip
// calculation below will misjudge the space it needs and open the wrong way.
const GRID_H = 152

/**
 * Emoji picker popover for comment reactions.
 *
 * Deliberately does NOT use the shared `Popover`/`Dropdown` primitives: both
 * hardcode `top: triggerRect.bottom + 4` with no upward flip, so on a comment
 * low in a long timeline the grid would open below the fold. This follows the
 * portal + measure + flip approach `UserMentionSelector` already established.
 */
export function ReactionPicker({ onSelect, activeKeys = [], className }) {
  const [isOpen, setIsOpen] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const [focusIdx, setFocusIdx] = useState(0)

  const triggerRef = useRef(null)
  const gridRef = useRef(null)
  const btnRefs = useRef([])

  const updatePosition = useCallback(() => {
    const el = triggerRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const spaceBelow = window.innerHeight - rect.bottom
    // Flip above when there isn't room below — the whole reason for this component.
    const openUp = spaceBelow < GRID_H + 12 && rect.top > GRID_H + 12

    let left = rect.right + window.scrollX - GRID_W
    const pad = 12
    if (left < pad + window.scrollX) left = pad + window.scrollX
    const maxLeft = window.innerWidth - GRID_W - pad + window.scrollX
    if (left > maxLeft) left = maxLeft

    setPos({
      top: openUp
        ? rect.top + window.scrollY - GRID_H - 6
        : rect.bottom + window.scrollY + 6,
      left,
    })
  }, [])

  const open = () => {
    updatePosition()
    setFocusIdx(0)
    setIsOpen(true)
  }

  const close = useCallback(({ restoreFocus = true } = {}) => {
    setIsOpen(false)
    if (restoreFocus) triggerRef.current?.focus()
  }, [])

  // Move DOM focus into the grid whenever the highlighted cell changes.
  useEffect(() => {
    if (isOpen) btnRefs.current[focusIdx]?.focus()
  }, [isOpen, focusIdx])

  useEffect(() => {
    if (!isOpen) return
    const onDown = (e) => {
      if (gridRef.current?.contains(e.target) || triggerRef.current?.contains(e.target)) return
      close({ restoreFocus: false })
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [isOpen, close])

  useEffect(() => {
    if (!isOpen) return
    window.addEventListener('scroll', updatePosition, true)
    window.addEventListener('resize', updatePosition)
    return () => {
      window.removeEventListener('scroll', updatePosition, true)
      window.removeEventListener('resize', updatePosition)
    }
  }, [isOpen, updatePosition])

  const handleGridKey = (e) => {
    const last = REACTIONS.length - 1
    if (e.key === 'Escape') { e.preventDefault(); close(); return }
    if (e.key === 'Tab') { close({ restoreFocus: false }); return }

    let next = null
    if (e.key === 'ArrowRight') next = Math.min(focusIdx + 1, last)
    else if (e.key === 'ArrowLeft') next = Math.max(focusIdx - 1, 0)
    else if (e.key === 'ArrowDown') next = Math.min(focusIdx + COLS, last)
    else if (e.key === 'ArrowUp') next = Math.max(focusIdx - COLS, 0)
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = last

    if (next !== null) {
      e.preventDefault()
      setFocusIdx(next)
    }
  }

  const pick = (key) => {
    onSelect?.(key)
    close()
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        aria-label="Add reaction"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        title="Add reaction"
        onClick={() => (isOpen ? close() : open())}
        className={cn(
          // Permanently visible — it used to be hover-only, which made it
          // undiscoverable and unusable on touch, where there is no hover.
          // Sized to match the reaction pills so it reads as "add one".
          'inline-flex items-center justify-center h-6 min-w-[28px] px-1.5 rounded-full',
          'border border-dashed border-border text-muted-foreground',
          'transition-colors hover:bg-accent hover:text-foreground hover:border-solid',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          isOpen && 'bg-accent text-foreground border-solid',
          className,
        )}
      >
        <SmilePlus size={13} />
      </button>

      {isOpen && createPortal(
        <div
          ref={gridRef}
          role="menu"
          aria-label="Pick a reaction"
          onKeyDown={handleGridKey}
          style={{ top: pos.top, left: pos.left, width: GRID_W }}
          className={cn(
            // Solid fill is required, not cosmetic: this floats over comment
            // text. (`bg-popover` was used here originally and is defined
            // nowhere in the Tailwind config, so the panel rendered transparent.)
            'absolute rounded-xl border border-border bg-white dark:bg-zinc-900',
            // Above Dropdown panels, which sit at z-[100].
            'z-[110] shadow-xl p-1.5 grid grid-cols-4 gap-0.5',
          )}
        >
          {REACTIONS.map((r, i) => {
            const active = activeKeys.includes(r.key)
            return (
              <button
                key={r.key}
                ref={(el) => { btnRefs.current[i] = el }}
                type="button"
                role="menuitem"
                title={r.label}
                aria-label={r.label}
                aria-pressed={active}
                tabIndex={i === focusIdx ? 0 : -1}
                onClick={() => pick(r.key)}
                onMouseEnter={() => setFocusIdx(i)}
                className={cn(
                  'h-10 w-10 flex items-center justify-center rounded-lg text-xl leading-none',
                  'transition-transform hover:scale-110 focus:outline-none',
                  'focus-visible:ring-2 focus-visible:ring-ring',
                  active
                    ? 'bg-blue-50 dark:bg-blue-900/30 ring-1 ring-blue-200 dark:ring-blue-800'
                    : 'hover:bg-accent',
                )}
              >
                <span aria-hidden="true">{r.emoji}</span>
              </button>
            )
          })}
        </div>,
        document.body,
      )}
    </>
  )
}
