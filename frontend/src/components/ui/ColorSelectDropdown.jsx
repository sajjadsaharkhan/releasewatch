import React from 'react'
import { ChevronDown, Check, Circle } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Dropdown, DropdownItem, DropdownLabel } from './Dropdown'
import { Icon } from './Icon'

/**
 * ColorSelectDropdown - A reusable dropdown with color indicators
 *
 * @param {Object} props
 * @param {Array} props.items - Array of { value, label, color } objects
 * @param {string} props.value - Currently selected value
 * @param {Function} props.onChange - Callback when selection changes
 * @param {string} props.placeholder - Placeholder text when nothing selected
 * @param {string} props.label - Optional label for the dropdown section
 * @param {string} props.className - Additional CSS classes
 * @param {number} props.width - Dropdown width in pixels
 * @param {boolean} props.compact - Smaller size for inline use
 * @param {string} props.icon - Optional icon name for the trigger button
 */
export function ColorSelectDropdown({
  items = [],
  value,
  onChange,
  placeholder = 'Select...',
  label,
  className,
  width = 200,
  compact = false,
  icon,
}) {
  const selectedItem = items.find((item) => item.value === value)

  return (
    <Dropdown
      width={width}
      trigger={
        <button
          className={cn(
            'flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-sm font-medium',
            'hover:bg-accent transition-colors',
            compact ? 'h-8' : 'w-full',
            !selectedItem && 'text-muted-foreground',
            className
          )}
        >
          {icon && <Icon name={icon} size={14} className="shrink-0" />}
          {selectedItem?.color && (
            <span
              className="h-2.5 w-2.5 rounded-full shrink-0 border border-border"
              style={{ backgroundColor: selectedItem.color }}
            />
          )}
          <span className={cn('truncate', compact ? 'max-w-[120px]' : 'flex-1 text-left')}>
            {selectedItem?.label || placeholder}
          </span>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground ml-auto" />
        </button>
      }
    >
      {({ close }) => (
        <>
          {label && <DropdownLabel>{label}</DropdownLabel>}
          {items.map((item) => (
            <DropdownItem
              key={item.value}
              onClick={() => {
                onChange?.(item.value)
                close()
              }}
            >
              <span className="flex items-center gap-2 min-w-0">
                {item.value === value ? (
                  <Check className="h-4 w-4 shrink-0" />
                ) : (
                  <Circle className="h-4 w-4 shrink-0 opacity-70" />
                )}
                {item.color && (
                  <span
                    className="h-2.5 w-2.5 rounded-full shrink-0 border border-border"
                    style={{ backgroundColor: item.color }}
                  />
                )}
                <span className="truncate">{item.label}</span>
              </span>
            </DropdownItem>
          ))}
        </>
      )}
    </Dropdown>
  )
}
