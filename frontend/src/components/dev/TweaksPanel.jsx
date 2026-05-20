import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Settings2, GripHorizontal, X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Segmented } from '../ui/Segmented'
import { Switch } from '../ui/Switch'
import { useApp } from '../../hooks/useApp'
import { useTweaks } from '../../hooks/useTweaks'

const PROJECT_LOCATION_OPTIONS = [
  { value: 'sidebar', label: 'Sidebar' },
  { value: 'header', label: 'Header pill' },
  { value: 'hero', label: 'Hero' },
]

export function TweaksPanel() {
  const [open, setOpen] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const { theme, toggleTheme } = useApp()
  const [tweaks, setTweak] = useTweaks()
  const panelRef = useRef(null)
  const dragRef = useRef({ dragging: false, startX: 0, startY: 0, origX: 0, origY: 0 })
  const [pos, setPos] = useState({ x: null, y: null })

  // Listen for activate/deactivate edit mode messages
  useEffect(() => {
    function onMessage(e) {
      if (e.data === '__activate_edit_mode') setEditMode(true)
      if (e.data === '__deactivate_edit_mode') setEditMode(false)
    }
    window.addEventListener('message', onMessage)
    window.postMessage('__edit_mode_available', '*')
    return () => window.removeEventListener('message', onMessage)
  }, [])

  // Drag logic
  function onDragStart(e) {
    const panel = panelRef.current
    if (!panel) return
    const rect = panel.getBoundingClientRect()
    dragRef.current = {
      dragging: true,
      startX: e.clientX,
      startY: e.clientY,
      origX: rect.left,
      origY: rect.top,
    }
    window.addEventListener('mousemove', onDragMove)
    window.addEventListener('mouseup', onDragEnd)
    e.preventDefault()
  }

  function onDragMove(e) {
    if (!dragRef.current.dragging) return
    const dx = e.clientX - dragRef.current.startX
    const dy = e.clientY - dragRef.current.startY
    setPos({
      x: Math.max(0, Math.min(window.innerWidth - 280, dragRef.current.origX + dx)),
      y: Math.max(0, Math.min(window.innerHeight - 200, dragRef.current.origY + dy)),
    })
  }

  function onDragEnd() {
    dragRef.current.dragging = false
    window.removeEventListener('mousemove', onDragMove)
    window.removeEventListener('mouseup', onDragEnd)
  }

  const style = pos.x !== null
    ? { position: 'fixed', left: pos.x, top: pos.y, bottom: 'auto', right: 'auto' }
    : {}

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-[90] flex h-10 w-10 items-center justify-center rounded-full border border-border bg-card shadow-lg text-muted-foreground hover:text-foreground transition-colors"
        title="Open Tweaks Panel"
      >
        <Settings2 className="h-4 w-4" />
      </button>
    )
  }

  return (
    <div
      ref={panelRef}
      style={style}
      className={cn(
        !pos.x ? 'fixed bottom-4 right-4' : '',
        'z-[90] w-64 rounded-xl border border-border bg-card shadow-2xl overflow-hidden'
      )}
    >
      {/* Title bar (drag handle) */}
      <div
        onMouseDown={onDragStart}
        className="flex items-center gap-2 border-b border-border px-3 py-2.5 cursor-grab active:cursor-grabbing select-none"
      >
        <GripHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="flex-1 text-xs font-semibold">Tweaks</span>
        {editMode && (
          <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-xs text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
            Edit mode
          </span>
        )}
        <button
          onClick={() => setOpen(false)}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="p-3 space-y-4">
        {/* Project location */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
            Project selector location
          </p>
          <Segmented
            value={tweaks.projectLocation}
            onValueChange={(v) => setTweak('projectLocation', v)}
            options={PROJECT_LOCATION_OPTIONS}
            className="w-full"
          />
        </div>

        {/* Theme toggle */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Theme</p>
            <p className="text-xs text-muted-foreground mt-0.5 capitalize">{theme}</p>
          </div>
          <Switch
            checked={theme === 'dark'}
            onCheckedChange={() => toggleTheme()}
          />
        </div>
      </div>
    </div>
  )
}
