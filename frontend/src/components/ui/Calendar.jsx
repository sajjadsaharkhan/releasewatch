import React, { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '../../lib/cn'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]

function getDaysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfMonth(year, month) {
  return new Date(year, month, 1).getDay()
}

function isSameDay(date1, date2) {
  return date1 &&
    date2 &&
    date1.getFullYear() === date2.getFullYear() &&
    date1.getMonth() === date2.getMonth() &&
    date1.getDate() === date2.getDate()
}

function isToday(date) {
  const today = new Date()
  return isSameDay(date, today)
}

export function Calendar({
  mode = 'single',
  selected,
  onSelect,
  defaultMonth,
  disabled,
  className,
}) {
  const [currentMonth, setCurrentMonth] = useState(
    (selected || defaultMonth || new Date()).getMonth()
  )
  const [currentYear, setCurrentYear] = useState(
    (selected || defaultMonth || new Date()).getFullYear()
  )

  const daysInMonth = useMemo(() => getDaysInMonth(currentYear, currentMonth), [currentYear, currentMonth])
  const firstDayOfMonth = useMemo(() => getFirstDayOfMonth(currentYear, currentMonth), [currentYear, currentMonth])

  const prevMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11)
      setCurrentYear(currentYear - 1)
    } else {
      setCurrentMonth(currentMonth - 1)
    }
  }

  const nextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0)
      setCurrentYear(currentYear + 1)
    } else {
      setCurrentMonth(currentMonth + 1)
    }
  }

  const handleDayClick = (day) => {
    const date = new Date(currentYear, currentMonth, day)
    onSelect?.(date)
  }

  const isDateDisabled = (day) => {
    if (!disabled) return false
    const date = new Date(currentYear, currentMonth, day)
    if (typeof disabled === 'function') {
      return disabled(date)
    }
    if (disabled.before && date < disabled.before) return true
    if (disabled.after && date > disabled.after) return true
    return false
  }

  const renderDays = () => {
    const days = []

    // Empty cells for days before the first day of the month
    for (let i = 0; i < firstDayOfMonth; i++) {
      days.push(<div key={`empty-${i}`} className="h-9" />)
    }

    // Days of the month
    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(currentYear, currentMonth, day)
      const isSelected = isSameDay(date, selected)
      const isDisabled = isDateDisabled(day)
      const isDayToday = isToday(date)

      days.push(
        <button
          key={day}
          type="button"
          onClick={() => handleDayClick(day)}
          disabled={isDisabled}
          className={cn(
            'h-9 w-9 rounded-md text-sm font-medium transition-colors',
            'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
            'hover:bg-accent hover:text-accent-foreground',
            isSelected && 'bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground',
            isDayToday && !isSelected && 'bg-accent text-accent-foreground',
            isDisabled && 'pointer-events-none opacity-50'
          )}
        >
          {day}
        </button>
      )
    }

    return days
  }

  return (
    <div className={cn('p-3 space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={prevMonth}
          className="inline-flex items-center justify-center rounded-md h-8 w-8 transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="text-sm font-medium">
          {MONTHS[currentMonth]} {currentYear}
        </div>
        <button
          type="button"
          onClick={nextMonth}
          className="inline-flex items-center justify-center rounded-md h-8 w-8 transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* Weekday headers */}
      <div className="grid grid-cols-7 gap-1 text-center text-xs text-muted-foreground">
        {WEEKDAYS.map((day) => (
          <div key={day} className="font-medium">
            {day}
          </div>
        ))}
      </div>

      {/* Days grid */}
      <div className="grid grid-cols-7 gap-1">
        {renderDays()}
      </div>
    </div>
  )
}
