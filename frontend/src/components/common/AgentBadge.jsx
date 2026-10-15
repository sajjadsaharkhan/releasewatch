import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'
import { AGENT } from '../../lib/constants'

/**
 * The Agent badge (slice 17, FR-M29): this content was written through MCP by
 * its owner's coding agent. It sits next to the owner's name and says nothing
 * else — no client, device, model or token. Renders nothing unless `show`.
 * A pastel sky → violet → fuchsia tint with a hairline ring, the word in the
 * agent gradient — chosen from a prototype round (variant D, 2026-10-15). The
 * gradient sits still and sweeps only while hovered (`agent-sheen`, off under
 * reduced motion). `compact` is the icon alone.
 */
export function AgentBadge({ show, compact = false, className }) {
  if (!show) return null
  return (
    <Tooltip content={AGENT.tooltip}>
      <span
        className={cn(
          'group/agent inline-flex shrink-0 items-center gap-1 rounded-full align-middle text-[10.5px] font-medium leading-none',
          compact ? 'h-[18px] w-[18px] justify-center' : 'h-[18px] px-1.5',
          AGENT.chip,
          className
        )}
      >
        <Icon name={AGENT.icon} size={11} aria-hidden="true" className={AGENT.iconClass} />
        {!compact && (
          <span aria-hidden="true" className={cn('agent-sheen bg-clip-text font-semibold text-transparent', AGENT.gradient)}>
            {AGENT.label}
          </span>
        )}
        <span className="sr-only">{AGENT.tooltip}</span>
      </span>
    </Tooltip>
  )
}
