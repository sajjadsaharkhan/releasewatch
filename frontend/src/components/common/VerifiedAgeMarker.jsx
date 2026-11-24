import React from 'react'
import { cn } from '../../lib/cn'
import { VERIFIED_AGE_DAYS } from '../../lib/constants'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'
import { useWorkContext } from './WorkContext'

const DAY_MS = 86400000

/** Whole days since the item was first verified, or null when it isn't waiting on production. */
export function verifiedDays(item, now = Date.now()) {
  if (item?.status !== 'verified' || !item.verified_at) return null
  return Math.floor((now - new Date(item.verified_at).getTime()) / DAY_MS)
}

/**
 * FR-42, BR-75: a Stream item that has been Verified for 3 days or more and is
 * still not on production. A small zinc `clock-alert` on cards and rows; never
 * on release items — a release ships them.
 */
export function VerifiedAgeMarker({ item, className }) {
  const { containerKind } = useWorkContext()
  const kind = item.container?.kind ?? item.container_kind ?? containerKind
  const days = kind === 'stream' ? verifiedDays(item) : null
  if (days == null || days < VERIFIED_AGE_DAYS) return null
  const label = `Verified ${days} days ago — not on production yet`
  return (
    <Tooltip content={label}>
      <span
        data-testid="verified-age-marker"
        className={cn('inline-flex shrink-0 items-center text-zinc-500 dark:text-zinc-400', className)}
      >
        <Icon name="clock-alert" size={12} strokeWidth={2.4} aria-hidden="true" />
        <span className="sr-only">{label}</span>
      </span>
    </Tooltip>
  )
}
