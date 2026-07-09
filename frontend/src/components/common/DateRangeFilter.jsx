import React, { useState } from 'react'
import { Calendar, ChevronDown } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dropdown, DropdownLabel } from '../ui/Dropdown'
import { Icon } from '../ui/Icon'

// Common presets (shown in grid)
const COMMON_PRESETS = [
  { value: '1d', label: '1d', fullLabel: 'Last 1 day', days: 1 },
  { value: '7d', label: '7d', fullLabel: 'Last 7 days', days: 7 },
  { value: '30d', label: '30d', fullLabel: 'Last 30 days', days: 30 },
]

// More presets (shown as compact list)
const MORE_PRESETS = [
  { value: '3d', label: '3 days', days: 3 },
  { value: '5d', label: '5 days', days: 5 },
  { value: '14d', label: '14 days', days: 14 },
  { value: '90d', label: '90 days', days: 90 },
  { value: 'all', label: 'All time', days: null },
]

export function DateRangeFilter({ value, onChange }) {
  const getLabel = () => {
    if (!value) return 'Date range'
    if (value.preset) {
      const allPresets = [...COMMON_PRESETS, ...MORE_PRESETS]
      return allPresets.find(p => p.value === value.preset)?.label || 'Custom'
    }
    if (value.from && value.to) {
      return `${formatDateShort(value.from)} – ${formatDateShort(value.to)}`
    }
    return 'Date range'
  }

  const handlePresetClick = (preset) => {
    const allPresets = [...COMMON_PRESETS, ...MORE_PRESETS]
    const presetConfig = allPresets.find(p => p.value === preset)
    if (presetConfig?.value === 'all') {
      onChange({ preset: 'all', from: null, to: null })
    } else if (presetConfig?.days) {
      const to = new Date()
      const from = new Date()
      from.setDate(from.getDate() - presetConfig.days)
      onChange({
        preset: presetConfig.value,
        from: from.toISOString().split('T')[0],
        to: to.toISOString().split('T')[0],
      })
    }
  }

  const handleCustomChange = (from, to) => {
    onChange({ preset: null, from, to })
  }

  const isSelected = (presetValue) => value?.preset === presetValue

  return (
    <Dropdown
      width={240}
      trigger={
        <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-border bg-background hover:bg-muted text-[12px]">
          <Icon name="calendar" size={12} className="text-zinc-500" />
          <span className="text-zinc-500">Date:</span>
          <span className="font-medium text-zinc-800 dark:text-zinc-100">{getLabel()}</span>
          <Icon name="chevron-down" size={11} className="text-zinc-400" />
        </button>
      }
    >
      {({ close }) => (
        <div className="p-2">
          {/* Common presets grid */}
          <div className="grid grid-cols-3 gap-1 mb-2">
            {COMMON_PRESETS.map((preset) => (
              <button
                key={preset.value}
                onClick={() => {
                  handlePresetClick(preset.value)
                  close()
                }}
                className={cn(
                  "px-2 py-1.5 text-xs font-medium rounded-md transition-colors",
                  isSelected(preset.value)
                    ? "bg-blue-600 text-white"
                    : "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                )}
                title={preset.fullLabel}
              >
                {preset.label}
              </button>
            ))}
          </div>

          {/* Divider */}
          <div className="border-t border-zinc-200 dark:border-zinc-700 my-2" />

          {/* More presets - compact list */}
          <div className="space-y-0.5 mb-2">
            {MORE_PRESETS.map((preset) => (
              <button
                key={preset.value}
                onClick={() => {
                  handlePresetClick(preset.value)
                  close()
                }}
                className={cn(
                  "w-full px-2 py-1 text-xs text-left rounded-md transition-colors flex items-center justify-between",
                  isSelected(preset.value)
                    ? "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium"
                    : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                )}
              >
                <span>Last {preset.label}</span>
                {isSelected(preset.value) && (
                  <span className="text-blue-600 dark:text-blue-400">✓</span>
                )}
              </button>
            ))}
          </div>

          {/* Divider */}
          <div className="border-t border-zinc-200 dark:border-zinc-700 my-2" />

          {/* Custom range */}
          <CustomDateRange
            value={value}
            onChange={handleCustomChange}
            onClose={close}
          />
        </div>
      )}
    </Dropdown>
  )
}

function CustomDateRange({ value, onChange, onClose }) {
  const [from, setFrom] = useState(value?.from || '')
  const [to, setTo] = useState(value?.to || '')
  const [isExpanded, setIsExpanded] = useState(false)

  const handleApply = () => {
    if (from && to) {
      onChange(from, to)
      setIsExpanded(false)
    }
  }

  if (!isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        className="w-full px-2 py-1.5 text-xs text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors flex items-center gap-2"
      >
        <Calendar className="h-3.5 w-3.5" />
        <span>Custom range...</span>
      </button>
    )
  }

  return (
    <div className="space-y-2 pt-1">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-zinc-500 dark:text-zinc-400 mb-0.5 block">From</label>
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            className="w-full px-2 py-1 text-xs bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="text-[10px] text-zinc-500 dark:text-zinc-400 mb-0.5 block">To</label>
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="w-full px-2 py-1 text-xs bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>
      <div className="flex gap-1.5">
        <button
          onClick={handleApply}
          disabled={!from || !to}
          className={cn(
            "flex-1 px-2 py-1 text-xs font-medium rounded-md transition-colors",
            from && to
              ? "bg-blue-600 text-white hover:bg-blue-700"
              : "bg-zinc-100 dark:bg-zinc-800 text-zinc-400 cursor-not-allowed"
          )}
        >
          Apply
        </button>
        <button
          onClick={() => {
            setIsExpanded(false)
            setFrom('')
            setTo('')
          }}
          className="px-2 py-1 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

function formatDateShort(dateStr) {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
