import React, { useState } from 'react'
import { cn } from '../../lib/cn'
import { Icon } from './Icon'
import { Button } from './Button'
import { Input } from './Input'
import { Popover, PopoverTrigger, PopoverContent } from './Popover'
import { RangeCalendar, TimeField } from './RangeCalendar'

// Kibana-style time filter, ported from llmeter's DateTimeRangePicker
// (frontend/components/ui/index.tsx) onto Releasewatch's Popover, tokens and
// icons. Two views in one popover: **Quick select** (relative presets, plus an
// optional "Last N days" row) and **Custom time range** — our own
// RangeCalendar (click the start day, then the end day) and two 24-hour time
// fields, never the browser's native date-time control.
//
// `value` is `{ days }` (relative) or `{ from, to }` — local `YYYY-MM-DDTHH:mm`
// strings (a plain `YYYY-MM-DD` is accepted and read as that whole day).
// `onChange` receives the same shapes. `presets` is a list of day counts.

const pad = (n) => String(n).padStart(2, '0')
const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

// 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:mm' → { day: Date, time: 'HH:mm' }
function splitPoint(value, fallbackTime) {
  if (!value) return { day: null, time: fallbackTime }
  const [date, time] = value.split('T')
  const [y, m, d] = date.split('-').map(Number)
  return { day: new Date(y, m - 1, d), time: time ? time.slice(0, 5) : fallbackTime }
}

export function toLocalInput(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// "2026-09-30 14:05" — fixed-width, so the trigger doesn't jump between ranges.
export function fmtRangePoint(value) {
  if (!value) return null
  return value.length === 10 ? value : value.replace('T', ' ').slice(0, 16)
}

export function rangeLabel(value) {
  if (value?.days != null) return `Last ${value.days} day${value.days === 1 ? '' : 's'}`
  const from = fmtRangePoint(value?.from)
  const to = fmtRangePoint(value?.to)
  if (from && to) return `${from} → ${to}`
  if (from) return `${from} → now`
  if (to) return `… → ${to}`
  return 'All time'
}

export function DateTimeRangePicker({
  value,
  onChange,
  presets = [7, 30, 90],
  allowCustomDays = true,
  maxDays = 3650,
  prefix = null,
  align = 'end',
  className,
}) {
  const [open, setOpen] = useState(false)
  const [view, setView] = useState('quick') // 'quick' | 'custom'
  const [days, setDays] = useState('')
  // Custom view: the chosen days and times.
  const [range, setRange] = useState({ start: null, end: null })
  const [startTime, setStartTime] = useState('00:00')
  const [endTime, setEndTime] = useState('23:59')

  const onOpenChange = (next) => {
    setOpen(next)
    if (next) {
      setView('quick')
      setDays(value?.days != null && !presets.includes(value.days) ? String(value.days) : '')
    }
  }

  const apply = (range) => {
    onChange(range)
    setOpen(false)
  }

  const openCustom = () => {
    // Start from the current range, like llmeter: a relative range is turned
    // into its concrete start and end so the user can nudge it.
    const now = new Date()
    let from, to
    if (value?.days != null) {
      from = toLocalInput(new Date(now.getTime() - value.days * 86400000))
      to = toLocalInput(now)
    } else {
      from = value?.from ?? null
      to = value?.to ?? null
    }
    const a = splitPoint(from, '00:00')
    const b = splitPoint(to, '23:59')
    setRange({ start: a.day, end: b.day })
    setStartTime(a.time)
    setEndTime(b.time)
    setView('custom')
  }

  const n = Number(days)
  const daysValid = Number.isInteger(n) && n >= 1 && n <= maxDays
  const startValue = range.start ? `${ymd(range.start)}T${startTime}` : null
  const endValue = range.end ? `${ymd(range.end)}T${endTime}` : null
  const customInvalid = Boolean(startValue && endValue && startValue >= endValue)
  const customReady = Boolean(startValue) && !customInvalid
  const fmtDay = (d) => d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })

  const isCustom = value?.days == null

  return (
    <Popover open={open} onOpenChange={onOpenChange} align={align}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-haspopup="dialog"
          aria-expanded={open}
          className={cn(
            'inline-flex items-center gap-2 h-8 px-3 rounded-md border border-border bg-background',
            'text-[12px] font-medium hover:bg-accent transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            className,
          )}
        >
          <Icon name="calendar" size={13} className="text-muted-foreground" aria-hidden />
          {prefix && <span className="text-muted-foreground">{prefix}</span>}
          <span className={cn('tabular-nums', isCustom && 'font-mono text-[11px]')}>{rangeLabel(value)}</span>
          <Icon name="chevron-down" size={13} className="opacity-50" aria-hidden />
        </button>
      </PopoverTrigger>

      <PopoverContent width={view === 'custom' ? 292 : 260} className="p-0">
        {view === 'quick' ? (
          <div role="dialog" aria-label="Quick select" className="p-1">
            <div className="px-3 py-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Quick select
            </div>
            {presets.map((d) => {
              const active = value?.days === d
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => apply({ days: d })}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium text-left transition-colors',
                    active
                      ? 'bg-accent text-foreground'
                      : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                  )}
                  aria-pressed={active}
                >
                  <Icon name="calendar" size={14} aria-hidden />
                  Last {d} days
                  {active && <Icon name="check" size={13} className="ml-auto" aria-hidden />}
                </button>
              )
            })}
            {allowCustomDays && (
              <form
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium',
                  value?.days != null && !presets.includes(value.days) ? 'bg-accent text-foreground' : 'text-muted-foreground',
                )}
                onSubmit={(e) => { e.preventDefault(); if (daysValid) apply({ days: n }) }}
              >
                <Icon name="calendar-range" size={14} aria-hidden />
                <span>Last</span>
                <Input
                  type="number"
                  min={1}
                  max={maxDays}
                  inputMode="numeric"
                  aria-label="Number of days"
                  value={days}
                  onChange={(e) => setDays(e.target.value)}
                  placeholder="N"
                  className="h-7 w-14 px-1.5 text-xs font-mono"
                />
                <span>days</span>
                <Button type="submit" size="sm" variant="outline" className="ml-auto h-7 px-2 text-xs" disabled={!daysValid}>
                  Apply
                </Button>
              </form>
            )}
            <div className="border-t border-border my-1" />
            <button
              type="button"
              onClick={openCustom}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium text-left transition-colors',
                isCustom ? 'bg-accent text-foreground' : 'text-muted-foreground hover:bg-accent hover:text-foreground',
              )}
            >
              <Icon name="clock" size={14} aria-hidden />
              Custom time range
              <Icon name="chevron-right" size={13} className="ml-auto opacity-60" aria-hidden />
            </button>
          </div>
        ) : (
          <form
            role="dialog"
            aria-label="Custom time range"
            className="p-3"
            onSubmit={(e) => { e.preventDefault(); if (customReady) apply({ from: startValue, to: endValue }) }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-semibold">Custom time range</div>
              <button
                type="button"
                onClick={() => setView('quick')}
                aria-label="Back to quick select"
                className="h-6 w-6 inline-flex items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Icon name="x" size={14} />
              </button>
            </div>

            {/* What's chosen so far — and which end the next click sets. */}
            <div className="grid grid-cols-2 gap-2 mb-3 text-[11px]" aria-live="polite">
              {[['Start', range.start, !range.start || Boolean(range.end)], ['End', range.end, Boolean(range.start) && !range.end]].map(([name, d, next]) => (
                <div
                  key={name}
                  className={cn(
                    'rounded-md border px-2 py-1.5',
                    next ? 'border-primary/60 bg-accent/60' : 'border-border',
                  )}
                >
                  <div className="text-muted-foreground">{name}</div>
                  <div className={cn('font-medium tabular-nums', !d && 'text-muted-foreground font-normal')}>
                    {d ? fmtDay(d) : next ? 'Pick a day' : '—'}
                  </div>
                </div>
              ))}
            </div>

            <RangeCalendar start={range.start} end={range.end} onChange={setRange} />

            <div className="grid grid-cols-2 gap-2 mt-3">
              <TimeField id="range-start-time" label="Start time" value={startTime} onChange={setStartTime} />
              <TimeField id="range-end-time" label="End time" value={endTime} onChange={setEndTime} />
            </div>
            {customInvalid && (
              <p className="mt-2 text-[11px] text-red-600 dark:text-red-400" role="alert">The start must be before the end.</p>
            )}
            {range.start && !range.end && (
              <p className="mt-2 text-[11px] text-muted-foreground">No end day — the range runs until now.</p>
            )}

            {/* Sticky: Apply stays in view when a short window makes the popover scroll. */}
            <div className="sticky bottom-0 -mx-3 -mb-3 mt-3 flex items-center justify-end gap-2 border-t border-border bg-card px-3 py-3">
              <Button type="button" size="sm" variant="ghost" onClick={() => setView('quick')}>Cancel</Button>
              <Button type="submit" size="sm" disabled={!customReady}>Apply</Button>
            </div>
          </form>
        )}
      </PopoverContent>
    </Popover>
  )
}
