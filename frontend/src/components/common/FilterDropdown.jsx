import React from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dropdown, DropdownItem, DropdownLabel } from '../ui/Dropdown'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'

export function FilterDropdown({ icon, label, value, options = [], onChange, width = 200 }) {
  return (
    <Dropdown
      width={width}
      trigger={
        <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 hover:bg-zinc-50 dark:hover:bg-zinc-900 text-[12px]">
          <Icon name={icon} size={12} className="text-zinc-500" />
          <span className="text-zinc-500">{label}:</span>
          <span className="font-medium text-zinc-800 dark:text-zinc-100">{value}</span>
          <Icon name="chevron-down" size={11} className="text-zinc-400" />
        </button>
      }
    >
      {({ close }) => (
        <>
          {options.map((opt) => (
            <DropdownItem key={opt.value} onClick={() => { onChange(opt.value); close(); }}>
              {opt.label}
            </DropdownItem>
          ))}
        </>
      )}
    </Dropdown>
  )
}
