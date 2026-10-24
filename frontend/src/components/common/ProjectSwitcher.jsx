import React, { useState, useRef, useEffect, useLayoutEffect, useCallback, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronDown, Search } from 'lucide-react'
import { NeedsTriageLeadBadge } from '../project'
import { cn } from '../../lib/cn'
import { getContrastColor } from '../../lib/colors'

const MENU_MAX_HEIGHT = 340
// Recently picked project ids, newest first, shared by every switcher (BUG-574).
const RECENT_KEY = 'rw.recentProjects'
const RECENT_SHOWN = 3

function readRecent() {
  try {
    const ids = JSON.parse(localStorage.getItem(RECENT_KEY))
    return Array.isArray(ids) ? ids : []
  } catch {
    return []
  }
}

function rememberRecent(id) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify([id, ...readRecent().filter((x) => x !== id)].slice(0, 10)))
  } catch {
    // Storage blocked (private window) — the Recent group just stays empty.
  }
}

function ProjectTile({ project, size }) {
  return (
    <span
      aria-hidden="true"
      className="flex shrink-0 items-center justify-center rounded font-bold"
      style={{ width: size, height: size, fontSize: size * 0.46, backgroundColor: project.color, color: getContrastColor(project.color) }}
    >
      {project.name?.[0] || '?'}
    </span>
  )
}

/**
 * The project picker: the topbar switcher and the Project field of New issue
 * and New support report. Searchable by name, slug or description (BUG-574);
 * with more than a handful of projects the last ones picked sit under "Recent".
 * Same overlay convention as UserPicker (docs/design.md §7).
 */
export function ProjectSwitcher({ projects = [], activeProjectId, onChange, compact = false, width = null }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [position, setPosition] = useState({ top: 0, left: 0, width: 0 })
  const triggerRef = useRef(null)
  const menuRef = useRef(null)
  const inputRef = useRef(null)

  const selected = projects.find((p) => p.id === activeProjectId) ?? projects[0]

  // Groups to render; `options` is the keyboard order across them. Rebuilt on
  // open so Recent reflects the last pick.
  const { groups, options } = useMemo(() => {
    const sorted = [...projects].sort((a, b) => a.name.localeCompare(b.name))
    const q = query.trim().toLowerCase()
    if (q) {
      const hit = (s) => s?.toLowerCase().includes(q)
      const matches = sorted
        .filter((p) => hit(p.name) || hit(p.slug) || hit(p.description ?? p.desc))
        .sort((a, b) => Number(!a.name.toLowerCase().startsWith(q)) - Number(!b.name.toLowerCase().startsWith(q)))
      return { groups: [{ label: null, items: matches }], options: matches }
    }
    const recent = projects.length > RECENT_SHOWN + 2
      ? readRecent().map((id) => projects.find((p) => p.id === id)).filter(Boolean).slice(0, RECENT_SHOWN)
      : []
    if (recent.length === 0) return { groups: [{ label: null, items: sorted }], options: sorted }
    const rest = sorted.filter((p) => !recent.includes(p))
    return { groups: [{ label: 'Recent', items: recent }, { label: 'All projects', items: rest }], options: [...recent, ...rest] }
  }, [projects, query, open]) // eslint-disable-line react-hooks/exhaustive-deps

  const close = useCallback(() => {
    setOpen(false)
    setQuery('')
  }, [])

  const place = useCallback(() => {
    if (!triggerRef.current) return false
    const rect = triggerRef.current.getBoundingClientRect()
    if (rect.bottom < 0 || rect.top > window.innerHeight) return false
    const padding = 12
    const menuWidth = width || Math.max(rect.width, 280)
    const left = Math.max(padding, Math.min(rect.left, window.innerWidth - menuWidth - padding))
    const spaceBelow = window.innerHeight - rect.bottom
    const flip = spaceBelow < MENU_MAX_HEIGHT + 8 && rect.top > spaceBelow
    setPosition(flip
      ? { bottom: window.innerHeight - rect.top + 4, left, width: menuWidth }
      : { top: rect.bottom + 4, left, width: menuWidth })
    return true
  }, [width])

  useLayoutEffect(() => {
    if (!open) return
    place()
    inputRef.current?.focus()
    const current = options.findIndex((p) => p.id === selected?.id)
    setActive(current >= 0 ? current : 0)
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { setActive(0) }, [query])

  useEffect(() => {
    if (!open) return
    function follow(e) {
      if (e?.target instanceof Node && menuRef.current?.contains(e.target)) return
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

  function choose(project) {
    rememberRecent(project.id)
    onChange?.(project.id)
    close()
    triggerRef.current?.focus()
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => Math.min(i + 1, options.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (options[active]) choose(options[active])
    } else if (e.key === 'Escape') {
      // Close the menu only, not the dialog it sits in.
      e.preventDefault()
      e.stopPropagation()
      close()
      triggerRef.current?.focus()
    }
  }

  let index = -1
  const menu = open ? (
    <div
      ref={menuRef}
      className="fixed z-[100] rounded-lg border border-border bg-card text-sm shadow-lg"
      style={{ top: position.top, bottom: position.bottom, left: position.left, width: position.width }}
    >
      <div className="flex items-center gap-2 border-b border-border px-3">
        <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Search projects…"
          aria-label="Search projects"
          aria-controls="project-switcher-options"
          aria-activedescendant={options[active] ? `project-switcher-option-${active}` : undefined}
          className="h-9 w-full bg-transparent text-sm placeholder:text-muted-foreground focus:outline-none"
        />
      </div>
      <div
        id="project-switcher-options"
        role="listbox"
        aria-label="Projects"
        className="overflow-y-auto py-1 scrollbar-thin"
        style={{ maxHeight: MENU_MAX_HEIGHT - 40 }}
      >
        {options.length === 0 && (
          <p className="px-3 py-3 text-center text-[12px] text-muted-foreground">No project matches “{query.trim()}”.</p>
        )}
        {groups.map((g) => (
          <div key={g.label ?? 'all'} role="group" aria-label={g.label ?? undefined}>
            {g.label && g.items.length > 0 && (
              <div className="px-3 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{g.label}</div>
            )}
            {g.items.map((p) => {
              index += 1
              const i = index
              const isSelected = p.id === selected?.id
              return (
                <div
                  key={p.id}
                  id={`project-switcher-option-${i}`}
                  data-index={i}
                  role="option"
                  aria-selected={isSelected}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => choose(p)}
                  className={cn('flex cursor-pointer items-center gap-2 px-3 py-1.5', i === active ? 'bg-accent' : 'hover:bg-accent/50')}
                >
                  <ProjectTile project={p} size={18} />
                  <span className="truncate text-foreground">{p.name}</span>
                  <span className="truncate font-mono text-[11px] text-muted-foreground">{p.slug}</span>
                  {p.needs_triage_lead && <NeedsTriageLeadBadge className="shrink-0 px-1.5 text-[10px]" />}
                  {isSelected && <Check className="ml-auto h-3.5 w-3.5 shrink-0 text-foreground" aria-hidden="true" />}
                </div>
              )
            })}
          </div>
        ))}
      </div>
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
          'flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-sm font-medium',
          'transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
          compact ? 'h-8' : 'w-full'
        )}
      >
        {selected && <ProjectTile project={selected} size={24} />}
        <span className={cn('truncate', compact ? 'max-w-[120px]' : 'flex-1 text-left')}>
          {selected?.name ?? 'Select project'}
        </span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      </button>
      {menu && createPortal(menu, document.body)}
    </>
  )
}
