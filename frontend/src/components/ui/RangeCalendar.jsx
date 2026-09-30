import React, { useEffect, useMemo, useState } from 'react'
import { cn } from '../../lib/cn'
import { Icon } from './Icon'

// A one-month calendar that picks a day range: the first click sets the start,
// the second the end (a day before the start restarts the range). Days between
// are tinted; while only the start is set, hovering previews the range.
// `start` / `end` are Dates (the day part is used) or null.

const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']

const dayKey = (d) => d.getFullYear() * 10000 + d.getMonth() * 100 + d.getDate()
const sameDay = (a, b) => Boolean(a && b) && dayKey(a) === dayKey(b)

export function RangeCalendar({ start, end, onChange, maxDate = null, className }) {
  const anchor = end ?? start ?? new Date()
  const [month, setMonth] = useState(() => new Date(anchor.getFullYear(), anchor.getMonth(), 1))
  const [hover, setHover] = useState(null)

  useEffect(() => {
    const a = end ?? start
    if (a) setMonth(new Date(a.getFullYear(), a.getMonth(), 1))
  }, [start?.getTime?.(), end?.getTime?.()]) // eslint-disable-line react-hooks/exhaustive-deps

  const days = useMemo(() => {
    const first = month.getDay()
    const count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
    return [
      ...Array.from({ length: first }, () => null),
      ...Array.from({ length: count }, (_, i) => new Date(month.getFullYear(), month.getMonth(), i + 1)),
    ]
  }, [month])

  const pick = (d) => {
    if (!start || end || dayKey(d) < dayKey(start)) onChange({ start: d, end: null })
    else onChange({ start, end: d })
  }

  // The range to tint: the chosen one, or start → hovered day while choosing.
  const lo = start ? dayKey(start) : null
  const hi = end ? dayKey(end) : start && hover && dayKey(hover) >= lo ? dayKey(hover) : null
  const today = new Date()
  const label = month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  const shift = (n) => setMonth(new Date(month.getFullYear(), month.getMonth() + n, 1))
  const nextDisabled = maxDate && new Date(month.getFullYear(), month.getMonth() + 1, 1) > maxDate

  return (
    <div className={cn('select-none', className)} onMouseLeave={() => setHover(null)}>
      <div className="flex items-center justify-between mb-2">
        <button
          type="button"
          onClick={() => shift(-1)}
          aria-label="Previous month"
          className="h-7 w-7 inline-flex items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Icon name="chevron-left" size={14} />
        </button>
        <div className="text-[13px] font-semibold" aria-live="polite">{label}</div>
        <button
          type="button"
          onClick={() => shift(1)}
          disabled={nextDisabled}
          aria-label="Next month"
          className="h-7 w-7 inline-flex items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-30 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Icon name="chevron-right" size={14} />
        </button>
      </div>
      <div className="grid grid-cols-7 text-center text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground mb-1">
        {WEEKDAYS.map((w) => <div key={w} className="py-1">{w}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-y-0.5" role="grid" aria-label={label}>
        {days.map((d, i) => {
          if (!d) return <div key={`e${i}`} />
          const k = dayKey(d)
          const isStart = lo != null && k === lo
          const isEnd = hi != null && k === hi
          const inRange = lo != null && hi != null && k > lo && k < hi
          const disabled = Boolean(maxDate && k > dayKey(maxDate))
          return (
            <div
              key={k}
              className={cn(
                'flex justify-center',
                (inRange || (isStart && hi != null && hi !== lo)) && 'bg-accent',
                isStart && hi != null && hi !== lo && 'rounded-l-md',
                (inRange || isEnd) && 'bg-accent',
                isEnd && 'rounded-r-md',
              )}
            >
              <button
                type="button"
                disabled={disabled}
                onClick={() => pick(d)}
                onMouseEnter={() => setHover(d)}
                onFocus={() => setHover(d)}
                aria-pressed={isStart || isEnd}
                aria-label={d.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
                className={cn(
                  'h-8 w-8 rounded-md text-[12px] font-medium tabular-nums transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isStart || isEnd
                    ? 'bg-primary text-primary-foreground'
                    : 'text-foreground hover:bg-zinc-200/70 dark:hover:bg-zinc-700/60',
                  !isStart && !isEnd && sameDay(d, today) && 'ring-1 ring-inset ring-border font-semibold',
                  disabled && 'opacity-30 pointer-events-none',
                )}
              >
                {d.getDate()}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// A 24-hour HH:mm field: type freely ("9", "930", "9:30"), normalized on blur;
// ↑ / ↓ step 15 minutes.
const clampTime = (h, m) => `${String(Math.min(23, Math.max(0, h))).padStart(2, '0')}:${String(Math.min(59, Math.max(0, m))).padStart(2, '0')}`

export function parseTime(text) {
  const digits = String(text).replace(/[^\d]/g, '')
  if (!digits) return null
  let h, m
  if (String(text).includes(':')) {
    const [a, b = '0'] = String(text).split(':')
    h = Number(a); m = Number(b || 0)
  } else if (digits.length <= 2) {
    h = Number(digits); m = 0
  } else {
    h = Number(digits.slice(0, digits.length - 2)); m = Number(digits.slice(-2))
  }
  if (Number.isNaN(h) || Number.isNaN(m) || h > 23 || m > 59) return null
  return clampTime(h, m)
}

export function TimeField({ value, onChange, label, id }) {
  const [text, setText] = useState(value)
  useEffect(() => setText(value), [value])
  const invalid = text !== '' && parseTime(text) == null

  const step = (delta) => {
    const [h, m] = (parseTime(text) ?? value).split(':').map(Number)
    const total = (h * 60 + m + delta + 1440) % 1440
    const next = clampTime(Math.floor(total / 60), total % 60)
    setText(next); onChange(next)
  }

  return (
    <label className="block" htmlFor={id}>
      <span className="block mb-1 text-[11px] font-medium text-muted-foreground">{label}</span>
      <div className={cn(
        'flex items-center gap-1.5 h-8 rounded-md border bg-background px-2',
        invalid ? 'border-red-500' : 'border-input focus-within:ring-2 focus-within:ring-ring',
      )}>
        <Icon name="clock" size={13} className="text-muted-foreground" aria-hidden />
        <input
          id={id}
          inputMode="numeric"
          autoComplete="off"
          placeholder="HH:mm"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => { const t = parseTime(text); if (t) { setText(t); onChange(t) } }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowUp') { e.preventDefault(); step(15) }
            if (e.key === 'ArrowDown') { e.preventDefault(); step(-15) }
          }}
          aria-invalid={invalid}
          className="w-full bg-transparent text-xs font-mono tabular-nums outline-none"
        />
      </div>
    </label>
  )
}
