import React, { useState } from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dropdown, DropdownItem, DropdownLabel } from '../ui/Dropdown'
import { Icon } from '../ui/Icon'

export function MultiSelectFilterDropdown({ icon, label, selected = [], options = [], onChange, width = 220 }) {
  const getDisplayValue = () => {
    if (selected.length === 0) return 'Any'
    if (selected.length === 1) {
      const opt = options.find(o => o.value === selected[0])
      return opt?.label || 'Any'
    }
    return `${selected.length} selected`
  }

  const isSelected = (value) => selected.includes(value)

  const handleToggle = (value) => {
    if (isSelected(value)) {
      onChange(selected.filter(v => v !== value))
    } else {
      onChange([...selected, value])
    }
  }

  return (
    <Dropdown
      width={width}
      trigger={
        <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-border bg-background hover:bg-muted text-[12px]">
          <Icon name={icon} size={12} className="text-zinc-500" />
          <span className="text-zinc-500">{label}:</span>
          <span className="font-medium text-zinc-800 dark:text-zinc-100">{getDisplayValue()}</span>
          <Icon name="chevron-down" size={11} className="text-zinc-400" />
        </button>
      }
    >
      {({ close }) => (
        <>
          {options.length > 0 && (
            <DropdownItem onClick={() => { onChange([]); close(); }} className={cn(selected.length === 0 && 'bg-zinc-50 dark:bg-zinc-800')}>
              <div className="flex items-center justify-between w-full">
                <span>Any</span>
                {selected.length === 0 && <Check className="h-3.5 w-3.5 text-zinc-600 dark:text-zinc-400" />}
              </div>
            </DropdownItem>
          )}
          {options.map((opt) => (
            <DropdownItem key={opt.value} onClick={() => handleToggle(opt.value)}>
              <div className="flex items-center justify-between w-full">
                <span>{opt.label}</span>
                {isSelected(opt.value) && <Check className="h-3.5 w-3.5 text-zinc-600 dark:text-zinc-400" />}
              </div>
            </DropdownItem>
          ))}
        </>
      )}
    </Dropdown>
  )
}
