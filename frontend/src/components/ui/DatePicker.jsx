import React from 'react'
import { Calendar as CalendarIcon } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from './Button'
import { Calendar } from './Calendar'
import { Popover, PopoverTrigger, PopoverContent } from './Popover'

// Format date using native JavaScript
function formatDate(date) {
  if (!date) return ''
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

export function DatePicker({
  value,
  onChange,
  placeholder = "Pick a date",
  disabled,
  className,
  align = 'start',
  minDate,
  maxDate,
}) {
  const handleSelect = (date) => {
    onChange?.(date)
  }

  const disabledProp = React.useMemo(() => {
    if (minDate || maxDate) {
      return {
        before: minDate,
        after: maxDate,
      }
    }
    return undefined
  }, [minDate, maxDate])

  return (
    <Popover align={align}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          className={cn(
            'justify-start text-left font-normal h-9 w-full',
            !value && 'text-muted-foreground',
            className
          )}
          disabled={disabled}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {value ? formatDate(value) : <span>{placeholder}</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={value}
          onSelect={handleSelect}
          defaultMonth={value}
          disabled={disabledProp}
        />
      </PopoverContent>
    </Popover>
  )
}
