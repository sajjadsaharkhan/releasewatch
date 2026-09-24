import React, { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { issuesApi } from '../../lib/api'
import { issueKey, issueSlug } from '../../lib/issueSlug'
import { relTime } from '../../lib/relTime'
import { Avatar } from '../ui/Avatar'
import { PriorityBadge, StatusBadge } from '../ui/Badge'
import { Icon } from '../ui/Icon'
import { SourceBadge } from './SourceBadge'
import { TYPE } from '../../lib/constants'

const CARD_WIDTH = 300
const CARD_HEIGHT = 170

// Type hue per docs/design.md §3 (bug red, task violet).
const TYPE_ICON_CLASS = {
  bug: 'text-red-500 dark:text-red-400',
  task: 'text-violet-500 dark:text-violet-400',
}

/** `BUG-14` → `bug`, so the chip shows the right icon before the item loads. */
function typeFromKey(key) {
  return String(key ?? '').toLowerCase().startsWith('task-') ? 'task' : 'bug'
}

function Skeleton({ className }) {
  return <div className={cn('animate-pulse rounded bg-zinc-200 dark:bg-zinc-700', className)} />
}

/**
 * A link to a work item that shows its card on hover — the item-side twin of
 * `UserHoverCard`. The item is fetched on first hover (it may not be loaded
 * on the page at all, e.g. the original a bug was merged into).
 *
 * `issueId` is required; `label` is shown until the item loads (usually its key).
 */
export function IssueHoverCard({ issueId, label, className }) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const [issue, setIssue] = useState(null)
  const [state, setState] = useState('idle') // idle | loading | done | error
  const triggerRef = useRef(null)
  const timeoutRef = useRef(null)

  const place = useCallback(() => {
    if (!triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    const padding = 12
    const gap = 6
    const left = Math.max(padding, Math.min(rect.left, window.innerWidth - CARD_WIDTH - padding))
    const below = window.innerHeight - rect.bottom - padding >= CARD_HEIGHT
    const top = below ? rect.bottom + gap : Math.max(padding, rect.top - CARD_HEIGHT - gap)
    setPosition({ top, left })
  }, [])

  const load = useCallback(() => {
    if (state !== 'idle') return
    setState('loading')
    issuesApi.get(issueId)
      .then(res => { setIssue(res.data); setState('done') })
      .catch(() => setState('error'))
  }, [issueId, state])

  function show() {
    clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => { place(); setOpen(true); load() }, 200)
  }

  function hide() {
    clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => setOpen(false), 150)
  }

  useEffect(() => { setIssue(null); setState('idle') }, [issueId])
  useEffect(() => () => clearTimeout(timeoutRef.current), [])
  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  const text = issue ? issueKey(issue) : label
  const type = issue?.type ?? typeFromKey(label)
  const to = issue ? `/issue/${issueSlug(issue)}` : `/issue/${String(label).toLowerCase()}`

  const card = open ? (
    <div
      role="tooltip"
      className="fixed z-[9999] rounded-lg border border-border bg-card shadow-lg p-3.5"
      style={{ top: position.top, left: position.left, width: CARD_WIDTH }}
      onMouseEnter={() => clearTimeout(timeoutRef.current)}
      onMouseLeave={hide}
    >
      {state === 'error' ? (
        <p className="text-[12px] text-muted-foreground">Failed to load {label}.</p>
      ) : !issue ? (
        <div className="space-y-2" aria-hidden="true">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-3 w-40" />
        </div>
      ) : (
        <>
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="inline-flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
              <Icon name={TYPE[type].icon} size={11} className={TYPE_ICON_CLASS[type]} aria-hidden="true" />
              {issueKey(issue)}
            </span>
            <StatusBadge status={issue.status} />
            <PriorityBadge priority={issue.priority} />
            <SourceBadge source={issue.source} />
          </div>
          <p className="mt-1.5 text-[13px] font-medium leading-snug text-foreground line-clamp-2">{issue.title}</p>
          <div className="mt-2 flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
            {issue.assignee_user
              ? <><Avatar user={issue.assignee_user} size={14} /><span className="truncate">{issue.assignee_user.name}</span></>
              : <span className="italic">unassigned</span>}
            <span aria-hidden="true">·</span>
            <span className="truncate">{issue.project_name}</span>
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
            {issue.recurrence_count > 1 && (
              <>
                <Icon name="repeat" size={10} aria-hidden="true" />
                <span>Reported {issue.recurrence_count} times</span>
                <span aria-hidden="true">·</span>
              </>
            )}
            <span>Updated {relTime(issue.updated_at)}</span>
          </div>
        </>
      )}
    </div>
  ) : null

  return (
    <>
      <Link
        ref={triggerRef}
        to={to}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onClick={(e) => e.stopPropagation()}
        aria-label={`${TYPE[type].label} ${text}`}
        className={cn(
          'inline-flex items-center gap-1 rounded-md border border-border bg-muted/60 px-1.5 py-0.5 align-middle',
          'font-mono text-[11px] font-medium text-foreground transition-colors hover:bg-muted',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          className,
        )}
      >
        <Icon name={TYPE[type].icon} size={11} className={TYPE_ICON_CLASS[type]} aria-hidden="true" />
        {text}
      </Link>
      {card && createPortal(card, document.body)}
    </>
  )
}
