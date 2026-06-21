import React from 'react'
import { AlignLeft, AlignRight } from 'lucide-react'
import { cn } from '../../lib/cn'

export function DirectionControl({ value = 'ltr', onChange }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-muted-foreground select-none">Direction</span>
      <div className="flex items-center rounded-md border border-border overflow-hidden text-[11px] font-semibold">
        <button
          type="button"
          onClick={() => onChange?.('ltr')}
          className={cn(
            'flex items-center gap-1 px-2 py-1 transition-colors',
            value === 'ltr'
              ? 'bg-foreground text-background'
              : 'text-muted-foreground hover:text-foreground hover:bg-accent'
          )}
        >
          <AlignLeft className="h-3 w-3" />
          LTR
        </button>
        <div className="w-px self-stretch bg-border" />
        <button
          type="button"
          onClick={() => onChange?.('rtl')}
          className={cn(
            'flex items-center gap-1 px-2 py-1 transition-colors',
            value === 'rtl'
              ? 'bg-foreground text-background'
              : 'text-muted-foreground hover:text-foreground hover:bg-accent'
          )}
        >
          RTL
          <AlignRight className="h-3 w-3" />
        </button>
      </div>
    </div>
  )
}
