import React from 'react'
import { DateRangeFilter } from './DateRangeFilter'
import { ColorSelectDropdown } from '../ui/ColorSelectDropdown'
import { cn } from '../../lib/cn'

export function RegressionFilters({ filters, onFiltersChange, labels, className }) {
  const handleDateRangeChange = (value) => {
    onFiltersChange({ ...filters, dateRange: value })
  }

  const handleLabelChange = (value) => {
    onFiltersChange({ ...filters, selectedLabel: value === 'all' ? null : value })
  }

  // Prepend "All Labels" option to the items list
  const labelItems = labels ? [
    { value: 'all', label: 'All Labels', color: null },
    ...labels
  ] : []

  return (
    <div className={cn("flex flex-wrap items-center gap-3", className)}>
      <DateRangeFilter value={filters.dateRange} onChange={handleDateRangeChange} />
      {labels && (
        <ColorSelectDropdown
          items={labelItems}
          value={filters.selectedLabel || 'all'}
          onChange={handleLabelChange}
          placeholder="All Labels"
          compact
          width={180}
        />
      )}
    </div>
  )
}
