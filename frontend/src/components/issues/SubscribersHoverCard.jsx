import React, { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { Avatar } from '../ui/Avatar'
import { RoleBadge } from '../ui/Badge'
import { issuesApi } from '../../lib/api'
import { relTime } from '../../lib/relTime'

const WIDTH = 288
const REASON = {
  reporter: 'Reporter',
  recurrence: 'Reported again',
  duplicate: 'Merged duplicate',
  manual: null,
}

/**
 * Wraps the Subscribe button: hovering (or focusing) it lists everyone who is
 * subscribed. Refetched on every open — the list changes as people click.
 */
export function SubscribersHoverCard({ issueId, count, children }) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const [state, setState] = useState({ status: 'idle', items: [] })
  const triggerRef = useRef(null)
  const timer = useRef(null)

  const load = useCallback(() => {
    setState((s) => ({ status: s.items.length ? 'done' : 'loading', items: s.items }))
    issuesApi.subscribers(issueId)
      .then((res) => setState({ status: 'done', items: res.data || [] }))
      .catch(() => setState((s) => ({ status: 'error', items: s.items })))
  }, [issueId])

  const show = () => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      const r = triggerRef.current?.getBoundingClientRect()
      if (r) {
        setPos({
          top: r.bottom + 6,
          left: Math.max(12, Math.min(r.right - WIDTH, window.innerWidth - WIDTH - 12)),
        })
      }
      setOpen(true)
      load()
    }, 200)
  }
  const hide = () => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setOpen(false), 150)
  }

  useEffect(() => () => clearTimeout(timer.current), [])
  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  // The count changed (this user clicked) while the card is open — refresh it.
  useEffect(() => { if (open) load() }, [count]) // eslint-disable-line react-hooks/exhaustive-deps

  const { status, items } = state

  return (
    <span
      ref={triggerRef}
      className="inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {open && createPortal(
        <div
          role="tooltip"
          className="fixed z-[9999] overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-lg dark:border-zinc-700 dark:bg-zinc-900"
          style={{ top: pos.top, left: pos.left, width: WIDTH }}
          onMouseEnter={() => clearTimeout(timer.current)}
          onMouseLeave={hide}
        >
          <div className="border-b border-zinc-200 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-500 dark:border-zinc-700">
            Subscribers{items.length ? ` · ${items.length}` : ''}
          </div>
          <div className="max-h-64 overflow-y-auto py-1">
            {status === 'loading' && (
              <div className="space-y-2 px-3 py-2">
                {[0, 1].map((i) => (
                  <div key={i} className="h-6 animate-pulse rounded bg-zinc-200 dark:bg-zinc-700" />
                ))}
              </div>
            )}
            {status === 'error' && (
              <p className="px-3 py-3 text-[12px] text-zinc-500">Couldn’t load subscribers.</p>
            )}
            {status === 'done' && items.length === 0 && (
              <p className="px-3 py-3 text-[12px] text-zinc-500">No one is subscribed yet.</p>
            )}
            {items.map(({ user, reason, subscribed_at }) => (
              <div key={user.id} className="flex items-center gap-2.5 px-3 py-1.5">
                <Avatar user={user} size={24} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13px] font-medium text-zinc-900 dark:text-zinc-100">{user.name}</div>
                  <div className="truncate text-[11px] text-zinc-500">
                    {REASON[reason] ? `${REASON[reason]} · ` : ''}{relTime(subscribed_at)}
                  </div>
                </div>
                <RoleBadge role={user.role} />
              </div>
            ))}
          </div>
        </div>,
        document.body,
      )}
    </span>
  )
}
