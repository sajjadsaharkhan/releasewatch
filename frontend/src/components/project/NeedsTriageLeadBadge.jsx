import React from 'react'
import { AlertTriangle } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Tooltip } from '../ui/Tooltip'

/** AC-23 — flags a project whose triage lead is unset or deactivated (`needs_triage_lead`). */
export function NeedsTriageLeadBadge({ className }) {
  return (
    <Tooltip content="Triage notifications go to admins until a lead is set" className="whitespace-normal w-56 text-center">
      <Badge tone="amber" className={className ? `gap-1 ${className}` : 'gap-1'}>
        <AlertTriangle size={10} aria-hidden="true" />
        Needs triage lead
      </Badge>
    </Tooltip>
  )
}
