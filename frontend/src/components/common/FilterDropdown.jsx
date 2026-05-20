import React from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dropdown, DropdownLabel } from '../ui/Dropdown'
import { Button } from '../ui/Button'

export function FilterDropdown({ label, options = [], selected = [], onChange, className }) {
  const count = selected.length

  function toggle(value) {
    if (selected.includes(value)) {
      onChange?.(selected.filter((v) => v !== value))
    } else {
      onChange?.([...selected, value])
    }
  }

  return (
    <Dropdown
      className={className}
      trigger={
        <Button variant="outline" size="sm" className="gap-1.5">
          {label}
          {count > 0 && (
            <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-xs text-primary-foreground">
              {count}
            </span>
          )}
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        </Button>
      }
    >
      <DropdownLabel>{label}</DropdownLabel>
      {options.map((opt) => {
        const isSelected = selected.includes(opt.value)
        return (
          <button
            key={opt.value}
            onClick={() => toggle(opt.value)}
            className={cn(
              'flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm transition-colors',
              'hover:bg-accent',
              isSelected ? 'text-foreground font-medium' : 'text-muted-foreground'
            )}
          >
            <span className={cn('flex h-4 w-4 shrink-0 items-center justify-center rounded border border-border', isSelected && 'bg-primary border-primary')}>
              {isSelected && <Check className="h-2.5 w-2.5 text-primary-foreground" />}
            </span>
            {opt.label}
          </button>
        )
      })}
      {count > 0 && (
        <>
          <div className="my-1 h-px bg-border" />
          <button
            onClick={() => onChange?.([])}
            className="w-full px-3 py-1.5 text-left text-xs text-muted-foreground hover:text-destructive hover:bg-accent transition-colors"
          >
            Clear filters
          </button>
        </>
      )}
    </Dropdown>
  )
}
