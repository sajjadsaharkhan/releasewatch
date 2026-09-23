import React from 'react'
import { cn } from '../../lib/cn'
import { Input } from '../ui/Input'
import { Textarea } from '../ui/Textarea'
import { Select, SelectItem } from '../ui/Select'
import { DatePicker } from '../ui/DatePicker'
import { Icon } from '../ui/Icon'

// A support template's fields as Support fills them in (slice 05). One component
// for both the New report modal and the template editor's live preview, so the
// preview is exactly what Support will see.

export const FIELD_TYPES = {
  short_text: { label: 'Short text', icon: 'type', hint: 'A name, ID, or one line of text' },
  long_text: { label: 'Long text', icon: 'align-left', hint: 'Several lines — steps, what the customer said' },
  number: { label: 'Number', icon: 'hash', hint: 'An amount, count, or numeric ID' },
  date: { label: 'Date', icon: 'calendar', hint: 'A day, like when an order was placed' },
  datetime: { label: 'Date and time', icon: 'calendar-clock', hint: 'When something happened, to the minute' },
  single_select: { label: 'Single select', icon: 'list', hint: 'One choice from a list you define' },
  url: { label: 'Link', icon: 'link', hint: 'A full web address' },
}

/** Field types that take a full row; the rest share a two-column grid. */
const WIDE = new Set(['long_text', 'datetime'])

const pad = (n) => String(n).padStart(2, '0')
const toIsoDate = (d) => (d ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` : '')
const fromIsoDate = (s) => {
  if (!s) return null
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export const isBlank = (v) => v == null || (typeof v === 'string' && v.trim() === '')

/** Client-side check mirroring backend/app/support_report.py. Returns a message or null. */
export function checkFieldValue(field, raw) {
  if (isBlank(raw)) return field.is_required ? 'This field is required.' : null
  switch (field.field_type) {
    case 'number':
      return Number.isFinite(Number(raw)) ? null : 'Enter a number.'
    case 'datetime':
      return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(raw) ? null : 'Pick a date and a time.'
    case 'url':
      return /^https?:\/\/\S+\.\S+/.test(String(raw).trim())
        ? null
        : 'Enter a full link starting with http:// or https://.'
    default:
      return null
  }
}

export function FieldShell({ id, label, required, optional, help, error, className, children }) {
  return (
    <div className={className} data-invalid={error ? 'true' : undefined}>
      <label htmlFor={id} className="flex items-baseline gap-1 text-xs font-medium text-muted-foreground mb-1.5">
        {label}
        {required && <span className="text-destructive" aria-hidden>*</span>}
        {optional && <span className="font-normal text-muted-foreground/70">(optional)</span>}
      </label>
      {children}
      {error ? (
        <p id={id ? `${id}-error` : undefined} className="mt-1 flex items-center gap-1 text-[12px] text-destructive" role="alert">
          <Icon name="circle-alert" size={12} aria-hidden />
          {error}
        </p>
      ) : help ? (
        <p className="mt-1 text-[12px] text-muted-foreground">{help}</p>
      ) : null}
    </div>
  )
}

/**
 * Renders ``fields`` in template order. ``onChange(fieldId, value)`` and
 * ``onBlur(fieldId)`` are optional — the editor preview passes neither.
 */
export function TemplateFields({ fields, values = {}, errors = {}, onChange, onBlur, idPrefix = 'field' }) {
  if (!fields?.length) return null
  return (
    <div className="grid gap-x-4 gap-y-4 sm:grid-cols-2">
      {fields.map((f, i) => {
        const id = `${idPrefix}-${f.id ?? i}`
        const key = f.id ?? f.key ?? i
        return (
          <FieldShell
            key={key}
            id={id}
            label={f.label || 'Untitled field'}
            required={f.is_required}
            help={f.help_text}
            error={errors[f.id]}
            className={cn(WIDE.has(f.field_type) && 'sm:col-span-2')}
          >
            <FieldInput
              id={id}
              field={f}
              value={values[f.id]}
              error={!!errors[f.id]}
              onChange={(v) => onChange?.(f.id, v)}
              onBlur={() => onBlur?.(f.id)}
            />
          </FieldShell>
        )
      })}
    </div>
  )
}

function FieldInput({ id, field, value, error, onChange, onBlur }) {
  const a11y = {
    'aria-required': field.is_required || undefined,
    'aria-invalid': error || undefined,
    'aria-describedby': error ? `${id}-error` : undefined,
  }
  const text = (props) => (
    <Input id={id} {...a11y} value={value ?? ''} error={error} onBlur={onBlur}
      onChange={(e) => onChange(e.target.value)} {...props} />
  )

  switch (field.field_type) {
    case 'long_text':
      return (
        <Textarea id={id} {...a11y} value={value ?? ''} error={error} rows={3} onBlur={onBlur}
          onChange={(e) => onChange(e.target.value)} />
      )
    case 'number':
      return text({ type: 'number', inputMode: 'decimal' })
    case 'url':
      return text({ type: 'url', placeholder: 'https://' })
    case 'date':
      return (
        <DatePicker
          value={fromIsoDate(value)}
          onChange={(d) => { onChange(toIsoDate(d)); onBlur() }}
          className={cn(error && 'border-destructive')}
        />
      )
    case 'datetime': {
      const [datePart = '', timePart = ''] = (value ?? '').split('T')
      const combine = (d, t) => onChange(d || t ? `${d}T${t}` : '')
      return (
        <div className="flex gap-2">
          <DatePicker
            value={fromIsoDate(datePart)}
            onChange={(d) => combine(toIsoDate(d), timePart)}
            placeholder="Date"
            className={cn('flex-1 min-w-0', error && 'border-destructive')}
          />
          <Input
            id={id}
            {...a11y}
            type="time"
            aria-label={`${field.label} time`}
            value={timePart}
            error={error}
            className="w-[7.5rem] shrink-0 dark:[color-scheme:dark]"
            onBlur={onBlur}
            onChange={(e) => combine(datePart, e.target.value)}
          />
        </div>
      )
    }
    case 'single_select':
      return (
        <Select
          value={value ?? ''}
          onChange={(v) => { onChange(v); onBlur() }}
          placeholder="Pick one…"
          className={cn(error && 'border-destructive')}
        >
          {(field.options ?? []).filter((o) => o.label?.trim()).map((o, idx) => (
            <SelectItem key={o.value || o.key || idx} value={o.value || o.label}>{o.label}</SelectItem>
          ))}
        </Select>
      )
    default:
      return text({ maxLength: 500 })
  }
}
