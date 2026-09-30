import React, { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '../../lib/cn'
import { timelineApi } from '../../lib/api'
import { CYCLE_REASON } from '../../lib/constants'
import { Icon } from '../ui/Icon'

/**
 * The returned marker (08a, FR-63, CY-11): an item whose work came back and
 * hasn't been sent to review again. Shows where it was caught and how many
 * times it has come back ("returned N"); hovering or focusing loads the reason
 * comment (lazily, once). There is no Returned status — this sits next to the
 * title on rows and cards. Renders nothing when `item.returned` is null.
 */
export function ReturnedMarker({ item, compact = false, className }) {
  const returned = item?.returned
  const [open, setOpen] = useState(false)
  const timer = useRef(null)

  const commentId = returned?.comment_id
  const { data: comment, isLoading } = useQuery({
    queryKey: ['timeline-event', item?.id, commentId],
    queryFn: () => timelineApi.get(item.id, commentId).then((res) => res.data),
    enabled: open && !!commentId,
    staleTime: Infinity,
  })

  if (!returned) return null
  const reason = CYCLE_REASON[returned.reason] ?? CYCLE_REASON.review
  const label = `${reason.label} · returned ${returned.number}×`

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
        aria-label={label}
        className={cn(
          'inline-flex items-center gap-1 rounded-full h-[18px] text-[10.5px] font-semibold leading-none',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          compact ? 'px-1.5' : 'px-2',
          reason.pill,
        )}
      >
        <Icon name={reason.icon} size={11} aria-hidden="true" />
        <span aria-hidden="true">{compact ? returned.number : `${reason.short} · returned ${returned.number}`}</span>
      </span>
      {open && (
        <span
          role="tooltip"
          className={cn(
            'pointer-events-none absolute left-0 top-full z-50 mt-1.5 w-72 rounded-md border border-border',
            'bg-popover text-popover-foreground p-2.5 text-[12px] leading-snug shadow-lg whitespace-normal',
          )}
        >
          <span className="block font-semibold text-foreground">{label}</span>
          <span className="mt-1 block text-muted-foreground line-clamp-4">
            {!commentId ? 'No reason comment.' : isLoading ? 'Loading…' : (comment?.body || 'The comment was removed.')}
          </span>
        </span>
      )}
    </span>
  )
}
