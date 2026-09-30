import React, { useEffect, useState } from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Popover, PopoverTrigger, PopoverContent } from '../ui/Popover'
import { formatDay as fmt } from '../../lib/relTime'

// The Stream board's Done-column range (FR-47, AC-63), in the style of a
// log-search time picker: relative presets on the left, an absolute range on
// the right. The range lives in the URL: `?done=7d` (relative) or
// `?done_from=YYYY-MM-DD&done_to=YYYY-MM-DD` (absolute). 7 days is the default.

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

// { days } | { from, to } → URL search params (mutates and returns a copy).
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

// → the board endpoint's `done_from` / `done_to` (ISO). Dates are local days:
// `from` is the start of its day, `to` the end of its day.
export function doneRangeToApi(range, now = new Date()) {
  if (range.days != null) {
    return { done_from: new Date(now.getTime() - range.days * 86400000).toISOString() }
  }
  const params = {}
  if (range.from) params.done_from = new Date(`${range.from}T00:00:00`).toISOString()
  if (range.to) params.done_to = new Date(`${range.to}T23:59:59.999`).toISOString()
  return params
}

export function doneRangeLabel(range) {
  if (range.days != null) return `Last ${range.days} days`
  if (range.from && range.to) return `${fmt(range.from)} – ${fmt(range.to)}`
  if (range.from) return `Since ${fmt(range.from)}`
  if (range.to) return `Until ${fmt(range.to)}`
  return 'All time'
}

export function DoneRangePicker({ value, onChange, className }) {
  const [open, setOpen] = useState(false)
  const [custom, setCustom] = useState('')
  const [from, setFrom] = useState(value.from ?? '')
  const [to, setTo] = useState(value.to ?? '')

  useEffect(() => {
    if (!open) return
    setFrom(value.from ?? '')
    setTo(value.to ?? '')
    setCustom(value.days != null && !PRESETS.includes(value.days) ? String(value.days) : '')
  }, [open, value])

  const pick = (range) => { onChange(range); setOpen(false) }
  const customDays = Number(custom)
  const customValid = Number.isInteger(customDays) && customDays >= 1 && customDays <= MAX_DAYS
  const rangeInvalid = from && to && from > to

  return (
    <Popover open={open} onOpenChange={setOpen} align="end">
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-haspopup="dialog"
          aria-expanded={open}
          className={cn(
            'inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-border bg-background',
            'hover:bg-accent text-[12px] transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            className,
          )}
        >
          <Icon name="calendar-clock" size={13} className="text-muted-foreground" />
          <span className="text-muted-foreground">Done:</span>
          <span className="font-medium text-foreground">{doneRangeLabel(value)}</span>
          <Icon name="chevron-down" size={12} className="text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent width={470}>
        <div role="dialog" aria-label="Done column range" className="flex text-[12px]">
          {/* Relative */}
          <div className="w-[196px] shrink-0 border-r border-border p-2 space-y-0.5">
            <p className="px-2 pb-1 text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">Relative</p>
            {PRESETS.map((d) => {
              const active = value.days === d
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => pick({ days: d })}
                  className={cn(
                    'w-full flex items-center justify-between rounded-md px-2 py-1.5 text-left transition-colors',
                    active ? 'bg-accent font-medium text-foreground' : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                  )}
                >
                  Last {d} days
                  {active && <Icon name="check" size={12} />}
                </button>
              )
            })}
            <form
              className="flex items-center gap-1 px-2 pt-1.5"
              onSubmit={(e) => { e.preventDefault(); if (customValid) pick({ days: customDays }) }}
            >
              <span className="text-muted-foreground">Last</span>
              <Input
                type="number"
                min={1}
                max={MAX_DAYS}
                inputMode="numeric"
                aria-label="Number of days"
                value={custom}
                onChange={(e) => setCustom(e.target.value)}
                placeholder="N"
                className="h-7 w-14 px-1.5 text-[12px]"
              />
              <span className="text-muted-foreground">days</span>
              <Button type="submit" size="sm" variant="outline" className="h-7 px-2" disabled={!customValid}>
                Go
              </Button>
            </form>
          </div>

          {/* Absolute */}
          <form
            className="flex-1 p-3 space-y-2"
            onSubmit={(e) => {
              e.preventDefault()
              if (!rangeInvalid && (from || to)) pick({ from: from || null, to: to || null })
            }}
          >
            <p className="text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">Absolute range</p>
            <label className="block">
              <span className="block mb-1 text-muted-foreground">From</span>
              <Input type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} className="h-8 text-[12px]" />
            </label>
            <label className="block">
              <span className="block mb-1 text-muted-foreground">To</span>
              <Input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} className="h-8 text-[12px]" />
            </label>
            {rangeInvalid && <p className="text-red-600 dark:text-red-400">“From” must be on or before “To”.</p>}
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" size="sm" variant="ghost" onClick={() => pick({ days: DEFAULT_DONE_DAYS })}>
                Reset
              </Button>
              <Button type="submit" size="sm" disabled={rangeInvalid || (!from && !to)}>
                Apply range
              </Button>
            </div>
          </form>
        </div>
      </PopoverContent>
    </Popover>
  )
}
