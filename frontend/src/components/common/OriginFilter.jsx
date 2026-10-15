import React from 'react'
import { FilterDropdown } from './FilterDropdown'
import { ORIGIN_OPTIONS } from '../../lib/constants'

/**
 * Origin filter (slice 17, FR-M30): All · Agent · People — whether an item was
 * filed through MCP. `value` is the API's `origin` ('' for all).
 */
export function OriginFilter({ value = '', onChange }) {
  return (
    <FilterDropdown
      icon="filter"
      label="Origin"
      value={ORIGIN_OPTIONS.find((o) => o.value === (value || ''))?.label ?? 'All'}
      options={ORIGIN_OPTIONS}
      onChange={onChange}
      width={140}
    />
  )
}
