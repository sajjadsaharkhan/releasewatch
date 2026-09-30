import React from 'react'
import { DateTimeRangePicker, rangeLabel } from '../ui/DateTimeRangePicker'

// The Stream board's Done-column range (FR-47, AC-63) on the shared
// `DateTimeRangePicker` (quick select: last 7 / 30 / 90 / N days; or a custom
// start–end, date and time). The range lives in the URL: `?done=30d`
// (relative) or `?done_from=YYYY-MM-DDTHH:mm&done_to=…` (custom, local time).
// 7 days is the default.

export const DEFAULT_DONE_DAYS = 7
const PRESETS = [7, 30, 90]
const MAX_DAYS = 3650

// URL search params → { days } | { from, to }
export function readDoneRange(searchParams) {
  const from = searchParams.get('done_from')
  const to = searchParams.get('done_to')
  if (from || to) return { from: from || null, to: to || null }
  const m = /^(\d{1,4})d$/.exec(searchParams.get('done') || '')
  const days = m ? Math.min(MAX_DAYS, Math.max(1, Number(m[1]))) : DEFAULT_DONE_DAYS
  return { days }
}

// { days } | { from, to } → a copy of the URL search params.
export function writeDoneRange(searchParams, range) {
  const next = new URLSearchParams(searchParams)
  next.delete('done'); next.delete('done_from'); next.delete('done_to')
  if (range.days != null) {
    if (range.days !== DEFAULT_DONE_DAYS) next.set('done', `${range.days}d`)
  } else {
    if (range.from) next.set('done_from', range.from)
    if (range.to) next.set('done_to', range.to)
  }
  return next
}

// A local point → ISO. A plain date is the start (`from`) or end (`to`) of that day.
function toIso(value, edge) {
  if (value.length === 10) return new Date(`${value}T${edge === 'to' ? '23:59:59.999' : '00:00:00'}`).toISOString()
  return new Date(value).toISOString()
}

// → the board endpoint's `done_from` / `done_to`.
export function doneRangeToApi(range, now = new Date()) {
  if (range.days != null) {
    return { done_from: new Date(now.getTime() - range.days * 86400000).toISOString() }
  }
  const params = {}
  if (range.from) params.done_from = toIso(range.from, 'from')
  if (range.to) params.done_to = toIso(range.to, 'to')
  return params
}

export const doneRangeLabel = rangeLabel

export function DoneRangePicker({ value, onChange, className }) {
  return (
    <DateTimeRangePicker
      value={value}
      onChange={onChange}
      presets={PRESETS}
      maxDays={MAX_DAYS}
      prefix="Done:"
      className={className}
    />
  )
}
