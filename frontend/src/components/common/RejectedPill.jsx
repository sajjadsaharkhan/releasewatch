import React, { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '../../lib/cn'
import { timelineApi } from '../../lib/api'
import { CYCLE_REASON } from '../../lib/constants'
import { Icon } from '../ui/Icon'

/**
 * The Rejected status pill (09a, ADR 0004): "Rejected" in the hue and icon of
 * where the problem was caught (`item.reject_reason` — review, release QA,
 * production). Hovering or focusing it for 250 ms opens a card with the full
 * label and the reason comment, fetched once on demand by
 * `item.reject_comment_id`. Renders nothing unless the item is Rejected.
 */
export function RejectedPill({ item, className }) {
  const [open, setOpen] = useState(false)
  const timer = useRef(null)

  const commentId = item?.reject_comment_id
  const { data: comment, isLoading } = useQuery({
    queryKey: ['timeline-event', item?.id, commentId],
    queryFn: () => timelineApi.get(item.id, commentId).then((res) => res.data),
    enabled: open && !!commentId,
    staleTime: Infinity,
  })

  if (item?.status !== 'rejected') return null
  const reason = CYCLE_REASON[item.reject_reason] ?? CYCLE_REASON.review

  const show = () => { timer.current = setTimeout(() => setOpen(true), 250) }
  const hide = () => { clearTimeout(timer.current); setOpen(false) }

  return (
    <span
      className={cn('relative inline-flex shrink-0', className)}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      <span
        tabIndex={0}
        aria-label={`Rejected — ${reason.label}`}
        className={cn(
          'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          reason.pill,
        )}
      >
        <Icon name={reason.icon} size={11} aria-hidden="true" />
        <span aria-hidden="true">Rejected</span>
      </span>
      {open && (
        <span
          role="tooltip"
          className={cn(
            'pointer-events-none absolute left-0 top-full z-50 mt-1.5 w-72 rounded-md border border-border',
            // Solid fill — `bg-popover` isn't in the Tailwind config (see ReactionPicker).
            'bg-card text-card-foreground p-2.5 text-[12px] leading-snug shadow-lg whitespace-normal',
          )}
        >
          <span className="block font-semibold text-foreground">{reason.label}</span>
          <span className="mt-1 block text-muted-foreground line-clamp-4">
            {!commentId ? 'No reason comment.' : isLoading ? 'Loading…' : (comment?.body || 'The comment was removed.')}
          </span>
        </span>
      )}
    </span>
  )
}
